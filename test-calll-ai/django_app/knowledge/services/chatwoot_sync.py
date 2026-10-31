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
    Chatwoot Captain AI (captain_documents & captain_assistant_responses)
    using the tenant's dynamic account_id and assistant_id.
    """
    try:
        chunks = list(document.chunks.order_by('chunk_index'))
        if not chunks:
            logger.info(f"[ChatwootSync] Document {document.id} has no chunks yet, skipping.")
            return

        from voice_assistant.chatwoot_service import get_or_create_tenant_chatwoot, get_chatwoot_db_conn
        cfg = get_or_create_tenant_chatwoot(document.user)
        account_id = cfg.account_id if cfg else 2
        assistant_id = cfg.assistant_id if cfg else 1

        full_content = "\n\n".join([c.content for c in chunks])
        conn = get_chatwoot_db_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT id FROM captain_documents 
            WHERE (name = %s OR metadata->>'django_doc_id' = %s) 
              AND assistant_id = %s AND account_id = %s
        """, (document.title, str(document.id), assistant_id, account_id))
        row = cur.fetchone()

        if row:
            doc_id = row[0]
            cur.execute("""
                UPDATE captain_documents
                SET name = %s, content = %s, status = 1, sync_status = 1, updated_at = NOW(),
                    metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{django_doc_id}', %s::jsonb, true)
                WHERE id = %s AND account_id = %s
            """, (document.title, full_content, str(document.id), doc_id, account_id))
        else:
            cur.execute("""
                INSERT INTO captain_documents (
                    assistant_id, account_id, name, external_link, content, status, sync_status,
                    metadata, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, 1, 1,
                    %s, NOW(), NOW()
                ) RETURNING id
            """, (
                assistant_id,
                account_id,
                document.title,
                f"MARKDOWN: doc_{document.id}.md",
                full_content,
                f'{{"source": "django_rag_sync", "django_doc_id": {document.id}}}'
            ))
            doc_id = cur.fetchone()[0]

        # Refresh assistant responses
        cur.execute("DELETE FROM captain_assistant_responses WHERE documentable_id = %s AND documentable_type = 'Captain::Document' AND account_id = %s", (doc_id, account_id))

        for idx, chunk in enumerate(chunks[:25]):
            question = f"معلومات مستند {document.title} - مقطع {idx+1}:"
            answer = chunk.content
            cur.execute("""
                INSERT INTO captain_assistant_responses (
                    assistant_id, account_id, question, answer, status,
                    documentable_type, documentable_id, edited, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, 1,
                    'Captain::Document', %s, false, NOW(), NOW()
                )
            """, (assistant_id, account_id, question, answer, doc_id))

        conn.commit()
        conn.close()
        logger.info(f"[ChatwootSync] Successfully synced document {document.id} ('{document.title}') to Chatwoot Captain AI (Account {account_id}, Assistant {assistant_id}, Doc {doc_id}).")
    except Exception as e:
        logger.error(f"[ChatwootSync] Failed to sync document {document.id} to Chatwoot: {e}")


def delete_document_from_chatwoot(doc_title: str, django_doc_id: int = None, user=None):
    """
    Remove document and responses from Chatwoot when deleted from Django.
    Optionally scoped to tenant user's account_id.
    """
    try:
        from voice_assistant.chatwoot_service import get_or_create_tenant_chatwoot, get_chatwoot_db_conn
        account_id = None
        if user:
            cfg = get_or_create_tenant_chatwoot(user)
            if cfg:
                account_id = cfg.account_id

        conn = get_chatwoot_db_conn()
        cur = conn.cursor()

        where_parts = []
        params = []
        if django_doc_id:
            where_parts.append("(metadata->>'django_doc_id' = %s OR name = %s)")
            params.extend([str(django_doc_id), doc_title])
        else:
            where_parts.append("name = %s")
            params.append(doc_title)

        if account_id:
            where_parts.append("account_id = %s")
            params.append(account_id)

        where_sql = " AND ".join(where_parts)
        cur.execute(f"SELECT id, account_id FROM captain_documents WHERE {where_sql}", tuple(params))
        rows = cur.fetchall()
        for (c_id, a_id) in rows:
            cur.execute("DELETE FROM captain_assistant_responses WHERE documentable_id = %s AND documentable_type = 'Captain::Document'", (c_id,))
            cur.execute("DELETE FROM captain_documents WHERE id = %s", (c_id,))
            logger.info(f"[ChatwootSync] Deleted Chatwoot captain_document #{c_id} ('{doc_title}') for Account {a_id}")

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[ChatwootSync] Error deleting document '{doc_title}' from Chatwoot: {e}")
