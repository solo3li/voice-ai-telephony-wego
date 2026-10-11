import os
import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from google import genai
from google.genai import types
from pgvector.django import CosineDistance

from .models import Document, DocumentChunk
from .rag_utils import extract_text_from_file, chunk_text, get_embeddings_batch
from agents.models import SystemSetting
from common.auth import verify_internal_api_key

import inngest
from asgiref.sync import async_to_sync
from common.inngest_client import inngest_client
import hashlib
import redis

logger = logging.getLogger(__name__)


def get_redis_client():
    """Retrieve Redis client for L1 knowledge caching."""
    redis_url = getattr(settings, 'REDIS_URL', 'redis://redis:6379/0')
    return redis.from_url(redis_url, decode_responses=True)


def get_rag_cache_key(user_id: int, query: str) -> str:
    """Generate deterministic, normalized multi-tenant cache key for RAG queries."""
    clean_q = " ".join(
        str(query or '').lower()
        .replace('؟', ' ').replace('?', ' ')
        .replace('،', ' ').replace(',', ' ')
        .replace('!', ' ').replace('.', ' ')
        .split()
    )
    q_hash = hashlib.sha256(clean_q.encode('utf-8')).hexdigest()[:16]
    return f"rag:tenant:{user_id}:cache:{q_hash}"


def invalidate_tenant_rag_cache(user_id: int):
    """Purge all L1 Redis RAG cache entries for a specific tenant upon document mutation."""
    try:
        r = get_redis_client()
        pattern = f"rag:tenant:{user_id}:*"
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
            logger.info(f"Invalidated {len(keys)} Redis RAG cache keys for tenant {user_id}")
    except Exception as ex:
        logger.warning(f"Failed to invalidate Redis RAG cache for tenant {user_id}: {ex}")

@login_required(login_url='/login/')
def list_documents(request):
    """List all documents uploaded by the current user."""
    docs = Document.objects.filter(user=request.user).order_by('-created_at')
    data = []
    for d in docs:
        data.append({
            "id": d.id,
            "title": d.title,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "status": getattr(d, 'status', 'ready'),
            "error_message": getattr(d, 'error_message', ''),
            "chunks_count": d.chunks.count(),
            "created_at": d.created_at.strftime("%Y-%m-%d %H:%M"),
        })
    return JsonResponse({"status": "success", "documents": data})

@login_required(login_url='/login/')
def upload_document(request):
    """
    Handle document upload. Dispatches background extraction and embedding
    to Inngest with graceful synchronous fallback if Inngest is offline.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    file_obj = request.FILES.get('file')
    if not file_obj:
        return JsonResponse({"status": "error", "message": "لم يتم تحديد أي ملف للرفع"}, status=400)

    filename = file_obj.name
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = ['.pdf', '.docx', '.doc', '.txt', '.md']
    if ext not in allowed_exts:
        return JsonResponse({
            "status": "error",
            "message": f"صيغة الملف غير مدعومة ({ext}). الصيغ المدعومة هي: PDF, DOCX, TXT, MD"
        }, status=400)

    try:
        # Create Document record initially in 'pending' status
        doc = Document.objects.create(
            user=request.user,
            title=filename,
            file=file_obj,
            file_type=ext.lstrip('.'),
            file_size=file_obj.size,
            status='pending',
            error_message='',
        )

        # Attempt to dispatch to Inngest for asynchronous background processing
        dispatched_to_inngest = False
        try:
            async_to_sync(inngest_client.send)(
                inngest.Event(
                    name="knowledge/document.uploaded",
                    data={
                        "document_id": doc.id,
                        "user_id": request.user.id,
                        "filename": filename,
                    }
                )
            )
            dispatched_to_inngest = True
            logger.info(f"Dispatched document {doc.id} ({filename}) to Inngest background job.")
        except Exception as inngest_err:
            logger.warning(f"Inngest dispatch failed ({inngest_err}), falling back to synchronous processing.")

        if dispatched_to_inngest:
            return JsonResponse({
                "status": "success",
                "message": f"تم استلام المستند '{filename}' بنجاح وجارٍ استخراج النصوص وفهرسته في الخلفية.",
                "document": {
                    "id": doc.id,
                    "title": doc.title,
                    "status": "pending",
                    "chunks_count": 0,
                    "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M"),
                }
            })

        # Fallback: Synchronous processing if Inngest is unreachable
        text = extract_text_from_file(doc.file, filename)
        if not text:
            doc.status = 'failed'
            doc.error_message = "الملف فارغ أو يتعذر استخراج نص منه."
            doc.save(update_fields=['status', 'error_message'])
            return JsonResponse({"status": "error", "message": doc.error_message}, status=400)

        chunks = chunk_text(text, chunk_size=500, overlap=50)
        if not chunks:
            doc.status = 'failed'
            doc.error_message = "لم يتم العثور على محتوى صالح للتقطيع."
            doc.save(update_fields=['status', 'error_message'])
            return JsonResponse({"status": "error", "message": doc.error_message}, status=400)

        api_key = SystemSetting.get_gemini_api_key()
        if not api_key or api_key.startswith("your_"):
            doc.status = 'failed'
            doc.error_message = "لم يتم ضبط مفتاح Google Gemini API في لوحة تحكم النظام."
            doc.save(update_fields=['status', 'error_message'])
            return JsonResponse({"status": "error", "message": doc.error_message}, status=400)

        client = genai.Client(api_key=api_key)
        embeddings = get_embeddings_batch(client, chunks, batch_size=50)

        chunk_objects = []
        for i, (chunk_text_content, emb) in enumerate(zip(chunks, embeddings)):
            chunk_objects.append(DocumentChunk(
                document=doc,
                user=request.user,
                chunk_index=i,
                content=chunk_text_content,
                embedding=emb,
            ))
        DocumentChunk.objects.bulk_create(chunk_objects)

        doc.status = 'ready'
        doc.error_message = ''
        doc.save(update_fields=['status', 'error_message'])

        logger.info(f"Synchronously processed document '{filename}' for user {request.user.username}: {len(chunks)} chunks embedded.")

        invalidate_tenant_rag_cache(request.user.id)
        return JsonResponse({
            "status": "success",
            "message": f"تمت معالجة المستند '{filename}' بنجاح وفهرسة {len(chunks)} مقطعاً دلالياً.",
            "document": {
                "id": doc.id,
                "title": doc.title,
                "status": "ready",
                "chunks_count": len(chunks),
                "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        })

    except Exception as e:
        logger.error(f"Error processing document upload: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": f"حدث خطأ أثناء معالجة المستند: {str(e)}"}, status=500)

@login_required(login_url='/login/')
def delete_document(request, doc_id):
    """Delete a document and all its chunks for the authenticated user."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    doc = get_object_or_404(Document, id=doc_id, user=request.user)
    title = doc.title
    doc.delete()
    invalidate_tenant_rag_cache(request.user.id)
    logger.info(f"Deleted document '{title}' (id={doc_id}) for user {request.user.username}")
    return JsonResponse({"status": "success", "message": f"تم حذف المستند '{title}' بنجاح."})

@csrf_exempt
def api_internal_rag_search(request):
    """
    Internal RAG semantic similarity search API for the AI Agent.
    Accepts: { user_id: int, query: str, top_k: int }
    Returns: { status: 'success', text: str, matches: list }
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not verify_internal_api_key(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        user_id_raw = data.get('user_id')
        query_raw = data.get('query', '')
        top_k = int(data.get('top_k', 3))

        # Auto-detect if parameters were passed inverted
        if isinstance(user_id_raw, str) and not user_id_raw.isdigit() and str(query_raw).strip().isdigit():
            user_id_raw, query_raw = query_raw, user_id_raw

        try:
            user_id = int(user_id_raw) if user_id_raw is not None else None
        except (ValueError, TypeError):
            user_id = None

        query = str(query_raw or '').strip()

        if not user_id:
            return JsonResponse({"status": "error", "message": "Valid numeric user_id is required"}, status=400)

        if not query:
            return JsonResponse({"status": "error", "message": "query is required"}, status=400)

        # 0. Check L1 Redis Cache (Multi-Tenant Isolated)
        cache_key = get_rag_cache_key(user_id, query)
        try:
            r = get_redis_client()
            cached_raw = r.get(cache_key)
            if cached_raw:
                cached_data = json.loads(cached_raw)
                logger.info(f"[RAG L1 Cache Hit] Instant lookup for tenant {user_id}: '{query[:40]}'")
                return JsonResponse({
                    "status": "success",
                    "text": cached_data.get("text", ""),
                    "matches": cached_data.get("matches", []),
                    "source": "redis_l1_cache"
                })
        except Exception as cache_check_err:
            logger.debug(f"Redis cache check skipped: {cache_check_err}")

        api_key = SystemSetting.get_gemini_api_key()
        chunks = []

        # 1. Generate query embedding with Gemini (if API key is valid)
        if api_key and not api_key.startswith("your_"):
            try:
                client = genai.Client(api_key=api_key)
                embed_res = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=query,
                    config=types.EmbedContentConfig(output_dimensionality=768)
                )
                if embed_res and embed_res.embeddings:
                    query_vec = embed_res.embeddings[0].values
                    # 2. Similarity search using pgvector CosineDistance (relaxed threshold: 0.65)
                    chunks = list(
                        DocumentChunk.objects.filter(user_id=user_id)
                        .annotate(distance=CosineDistance('embedding', query_vec))
                        .filter(distance__lte=0.65)
                        .order_by('distance')[:top_k]
                    )
            except Exception as embed_err:
                logger.warning(f"Embedding search failed, falling back to keyword search: {embed_err}")

        # 3. Hybrid Search: Keyword fallback if semantic distance yielded no chunks or embedding failed
        if not chunks:
            from django.db.models import Q
            stopwords = {'ما', 'هو', 'هي', 'هل', 'من', 'عن', 'في', 'إلى', 'على', 'مع', 'لو', 'عندكم', 'أنا', 'عاوز', 'عايز', 'إيه', 'ليه', 'كام', 'فين'}
            clean_words = [w for w in query.replace('؟', ' ').replace('،', ' ').split() if len(w) >= 3 and w.lower() not in stopwords]
            if clean_words:
                kw_q = Q()
                for word in clean_words[:5]:
                    kw_q |= Q(content__icontains=word)
                chunks = list(DocumentChunk.objects.filter(user_id=user_id).filter(kw_q)[:top_k])
            if not chunks:
                chunks = list(DocumentChunk.objects.filter(user_id=user_id, content__icontains=query[:50])[:top_k])

        if not chunks:
            has_any = DocumentChunk.objects.filter(user_id=user_id).exists()
            msg = "لا توجد أي مستندات مرفوعة في قاعدة المعرفة الخاصة بك." if not has_any else "لم يتم العثور على أي معلومات متعلقة بهذا السؤال في المستندات المرفوعة الخاصة بك."
            return JsonResponse({
                "status": "success",
                "text": msg,
                "matches": []
            })

        matches = [c.content for c in chunks]
        formatted_text = "المعلومات الموثقة المستخرجة من مستنداتك:\n" + "\n---\n".join(matches)

        # 4. Save to L1 Redis Cache for this tenant (7-day TTL)
        try:
            r = get_redis_client()
            r.set(
                cache_key,
                json.dumps({"text": formatted_text, "matches": matches}, ensure_ascii=False),
                ex=86400 * 7
            )
            logger.info(f"[RAG L1 Cached] Stored result for tenant {user_id}")
        except Exception as cache_save_err:
            logger.debug(f"Redis cache save skipped: {cache_save_err}")

        return JsonResponse({
            "status": "success",
            "text": formatted_text,
            "matches": matches,
            "source": "database_l2"
        })

    except Exception as e:
        logger.error(f"Internal RAG search error: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
