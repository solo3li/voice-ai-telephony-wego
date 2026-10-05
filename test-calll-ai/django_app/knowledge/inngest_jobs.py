import logging
import inngest
from google import genai
from asgiref.sync import sync_to_async

from common.inngest_client import inngest_client
from common.centrifugo import publish_to_centrifugo
from .models import Document, DocumentChunk
from .rag_utils import extract_text_from_file, chunk_text, get_embeddings_batch
from agents.models import SystemSetting

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="process-document-rag",
    name="Process Document RAG Ingestion",
    trigger=inngest.TriggerEvent(event="knowledge/document.uploaded"),
    concurrency=[inngest.Concurrency(limit=2, key="event.data.user_id")],
)
async def fn_process_document_rag(ctx: inngest.Context) -> dict:
    doc_id = ctx.event.data.get("document_id")
    user_id = ctx.event.data.get("user_id")

    logger.info(f"[Inngest RAG] Starting processing for document {doc_id} (user {user_id})")

    def _get_doc():
        try:
            return Document.objects.select_related('user').get(id=doc_id)
        except Document.DoesNotExist:
            return None

    doc = await sync_to_async(_get_doc)()
    if not doc:
        logger.warning(f"[Inngest RAG] Document {doc_id} not found.")
        return {"status": "not_found", "document_id": doc_id}

    def _mark_failed(err_msg: str):
        doc.status = 'failed'
        doc.error_message = err_msg[:500]
        doc.save(update_fields=['status', 'error_message'])
        publish_to_centrifugo(f"knowledge:{user_id}", {
            "type": "document_status",
            "document_id": doc_id,
            "status": "failed",
            "error": err_msg
        })

    def _extract_and_chunk():
        with doc.file.open('rb') as f:
            text = extract_text_from_file(f, doc.title)
        if not text:
            raise ValueError("الملف فارغ أو يتعذر استخراج نص منه.")
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        if not chunks:
            raise ValueError("لم يتم العثور على محتوى صالح للتقطيع.")
        return chunks

    try:
        chunks = await sync_to_async(_extract_and_chunk)()
    except Exception as e:
        logger.error(f"[Inngest RAG] Extraction error for doc {doc_id}: {e}")
        await sync_to_async(_mark_failed)(str(e))
        return {"status": "failed", "error": str(e)}

    # Fetch Gemini API Key
    api_key = await sync_to_async(SystemSetting.get_gemini_api_key)()
    if not api_key or api_key.startswith("your_"):
        err = "لم يتم ضبط مفتاح Google Gemini API في لوحة التحكم."
        await sync_to_async(_mark_failed)(err)
        return {"status": "failed", "error": err}

    def _generate_and_save_chunks():
        client = genai.Client(api_key=api_key)
        embeddings = get_embeddings_batch(client, chunks, batch_size=50)

        chunk_objects = []
        for i, (chunk_text_content, emb) in enumerate(zip(chunks, embeddings)):
            chunk_objects.append(DocumentChunk(
                document=doc,
                user=doc.user,
                chunk_index=i,
                content=chunk_text_content,
                embedding=emb,
            ))
        DocumentChunk.objects.filter(document=doc).delete()
        DocumentChunk.objects.bulk_create(chunk_objects)

        doc.status = 'ready'
        doc.error_message = ''
        doc.save(update_fields=['status', 'error_message'])

        publish_to_centrifugo(f"knowledge:{user_id}", {
            "type": "document_status",
            "document_id": doc_id,
            "status": "ready",
            "chunks_count": len(chunks)
        })
        return len(chunks)

    try:
        count = await sync_to_async(_generate_and_save_chunks)()
        logger.info(f"[Inngest RAG] Finished doc {doc_id}: {count} chunks embedded successfully.")
        return {"status": "success", "document_id": doc_id, "chunks_count": count}
    except Exception as e:
        logger.error(f"[Inngest RAG] Embedding/Save error for doc {doc_id}: {e}", exc_info=True)
        await sync_to_async(_mark_failed)(str(e))
        return {"status": "failed", "error": str(e)}


all_knowledge_inngest_functions = [fn_process_document_rag]
