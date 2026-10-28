import logging
import psycopg2

logger = logging.getLogger(__name__)

CHATWOOT_DB_CONFIG = {
    "dbname": "chatwoot_production",
    "user": "postgres",
    "password": "ChatwootDbPassword2026",
    "host": "omni_postgres",
    "port": 5432
}

def sync_document_to_chatwoot(document):
    """
    Sync a Django Knowledge Document and its chunks directly into
    Chatwoot Captain AI (captain_documents & captain_assistant_responses).
    """
    try:
        chunks = list(document.chunks.order_by('chunk_index'))
        if not chunks:
            logger.info(f"[ChatwootSync] Document {document.id} has no chunks yet, skipping.")
            return

        full_content = "\n\n".join([c.content for c in chunks])
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor()

        # Check existing captain document
        cur.execute("SELECT id FROM captain_documents WHERE name = %s AND assistant_id = 1", (document.title,))
        row = cur.fetchone()

        if row:
            doc_id = row[0]
            cur.execute("""
                UPDATE captain_documents
                SET content = %s, status = 1, sync_status = 1, updated_at = NOW(),
                    metadata = %s
                WHERE id = %s
            """, (full_content, f'{{"source": "django_rag_sync", "doc_id": {document.id}}}', doc_id))
        else:
            cur.execute("""
                INSERT INTO captain_documents (
                    assistant_id, account_id, name, external_link, content, status, sync_status,
                    metadata, created_at, updated_at
                ) VALUES (
                    1, 2, %s, %s, %s, 1, 1,
                    %s, NOW(), NOW()
                ) RETURNING id
            """, (document.title, f"MARKDOWN: doc_{document.id}.md", full_content, f'{{"source": "django_rag_sync", "doc_id": {document.id}}}'))
            doc_id = cur.fetchone()[0]

        # Refresh assistant responses
        cur.execute("DELETE FROM captain_assistant_responses WHERE documentable_id = %s AND documentable_type = 'Captain::Document'", (doc_id,))

        for idx, chunk in enumerate(chunks):
            question = f"معلومات مستند {document.title} - مقطع {idx+1}:"
            answer = chunk.content
            cur.execute("""
                INSERT INTO captain_assistant_responses (
                    assistant_id, account_id, question, answer, status,
                    documentable_type, documentable_id, edited, created_at, updated_at
                ) VALUES (
                    1, 2, %s, %s, 1,
                    'Captain::Document', %s, false, NOW(), NOW()
                )
            """, (question, answer, doc_id))

        conn.commit()
        conn.close()
        logger.info(f"[ChatwootSync] Successfully synced document {document.id} ('{document.title}') to Chatwoot Captain AI (ID {doc_id}).")
    except Exception as e:
        logger.error(f"[ChatwootSync] Failed to sync document {document.id} to Chatwoot: {e}")
