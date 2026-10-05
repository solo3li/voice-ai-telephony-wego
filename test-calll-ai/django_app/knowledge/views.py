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

logger = logging.getLogger(__name__)

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
        user_id = data.get('user_id')
        query = str(data.get('query', '')).strip()
        top_k = int(data.get('top_k', 3))

        if not query:
            return JsonResponse({"status": "error", "message": "query is required"}, status=400)

        api_key = SystemSetting.get_gemini_api_key()
        if not api_key or api_key.startswith("your_"):
            return JsonResponse({
                "status": "success",
                "text": "لم يتم ضبط مفتاح Google Gemini API في لوحة تحكم النظام بعد.",
                "matches": []
            })

        # 1. Generate query embedding with Gemini
        client = genai.Client(api_key=api_key)
        embed_res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=query,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        if not embed_res or not embed_res.embeddings:
            return JsonResponse({"status": "error", "message": "Failed to generate query embedding"}, status=500)

        query_vec = embed_res.embeddings[0].values

        # 2. Similarity search using pgvector CosineDistance
        chunks = DocumentChunk.objects.filter(user_id=user_id) \
            .annotate(distance=CosineDistance('embedding', query_vec)) \
            .filter(distance__lte=0.50) \
            .order_by('distance')[:top_k]

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

        return JsonResponse({
            "status": "success",
            "text": formatted_text,
            "matches": matches
        })

    except Exception as e:
        logger.error(f"Internal RAG search error: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
