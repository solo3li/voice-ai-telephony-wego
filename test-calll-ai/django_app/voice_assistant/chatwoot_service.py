# SPDX-License-Identifier: Apache-2.0
import json
import logging
import secrets
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from django.conf import settings

logger = logging.getLogger(__name__)

CHATWOOT_DB_CONFIG = {
    "dbname": "chatwoot_production",
    "user": "postgres",
    "password": "ChatwootDbPassword2026",
    "host": "omni_postgres",
    "port": 5432
}

CHATWOOT_REDIS_CONFIG = {
    "host": "omni_redis",
    "port": 6379,
    "password": "ChatwootRedisPassword2026",
    "db": 0
}

CHATWOOT_BASE_URL = getattr(settings, 'CHATWOOT_BASE_URL', 'https://chatwoot.169.58.32.179.nip.io')


def generate_chatwoot_sso_url(user=None, account_id=2):
    """
    Generate a direct SSO login link for Chatwoot that logs the user in
    silently without asking for credentials, using Chatwoot's Redis Alfred SSO token.
    """
    try:
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor()

        chatwoot_user = None
        if user and getattr(user, 'email', None):
            cur.execute("SELECT id, email FROM users WHERE email = %s LIMIT 1", (user.email,))
            chatwoot_user = cur.fetchone()

        if not chatwoot_user:
            # Fallback to SuperAdmin user fps60y@gmail.com (id: 2) or first SuperAdmin
            cur.execute("SELECT id, email FROM users WHERE type = 'SuperAdmin' ORDER BY id ASC LIMIT 1")
            chatwoot_user = cur.fetchone()

        if not chatwoot_user:
            cur.execute("SELECT id, email FROM users ORDER BY id ASC LIMIT 1")
            chatwoot_user = cur.fetchone()

        conn.close()

        if not chatwoot_user:
            logger.warning("[ChatwootSSO] No Chatwoot user found in database.")
            return f"{CHATWOOT_BASE_URL}/app/accounts/{account_id}"

        user_id, email = chatwoot_user[0], chatwoot_user[1]
        token = secrets.token_hex(32)

        # Store in Chatwoot's Redis
        r = redis.Redis(**CHATWOOT_REDIS_CONFIG)
        sso_key = f"alfred:USER_SSO_AUTH_TOKEN::{user_id}::{token}"
        r.set(sso_key, 'normal', ex=3600)  # 1 hour expiration

        encoded_email = urllib.parse.quote(email)
        redirect_target = f"/app/accounts/{account_id}"
        sso_url = f"{CHATWOOT_BASE_URL}/app/login?email={encoded_email}&sso_auth_token={token}&redirect_url={urllib.parse.quote(redirect_target)}"
        logger.info(f"[ChatwootSSO] Generated silent SSO link for user {email} (ID {user_id})")
        return sso_url
    except Exception as e:
        logger.error(f"[ChatwootSSO] Error generating SSO URL: {e}", exc_info=True)
        return f"{CHATWOOT_BASE_URL}/app/accounts/{account_id}"


def get_captain_settings(assistant_id=1, account_id=2):
    """
    Retrieve Captain AI assistant settings and linked inboxes from Chatwoot database.
    """
    try:
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT id, name, description, config, response_guidelines, guardrails
            FROM captain_assistants
            WHERE id = %s AND account_id = %s
        """, (assistant_id, account_id))
        assistant = cur.fetchone()

        if not assistant:
            cur.execute("""
                SELECT id, name, description, config, response_guidelines, guardrails
                FROM captain_assistants
                WHERE account_id = %s
                ORDER BY id ASC LIMIT 1
            """, (account_id,))
            assistant = cur.fetchone()

        if not assistant:
            conn.close()
            return None

        cur.execute("""
            SELECT i.id, i.name, i.channel_type, (ci.id IS NOT NULL) AS is_linked
            FROM inboxes i
            LEFT JOIN captain_inboxes ci ON ci.inbox_id = i.id AND ci.captain_assistant_id = %s
            WHERE i.account_id = %s
            ORDER BY i.id ASC
        """, (assistant['id'], account_id))
        inboxes = cur.fetchall()

        conn.close()

        config = assistant.get('config') or {}
        guidelines = assistant.get('response_guidelines') or []
        guardrails = assistant.get('guardrails') or []

        return {
            "assistant_id": assistant['id'],
            "name": assistant.get('name') or '',
            "product_name": config.get('product_name') or '',
            "description": assistant.get('description') or '',
            "response_guidelines": guidelines if isinstance(guidelines, list) else [],
            "guardrails": guardrails if isinstance(guardrails, list) else [],
            "temperature": float(config.get('temperature', 0.5) or 0.5),
            "feature_faq": bool(config.get('feature_faq', True)),
            "inboxes": [
                {
                    "id": row['id'],
                    "name": row['name'],
                    "channel_type": row['channel_type'],
                    "is_linked": bool(row['is_linked'])
                }
                for row in inboxes
            ]
        }
    except Exception as e:
        logger.error(f"[ChatwootCaptain] Error retrieving settings: {e}", exc_info=True)
        return None


def update_captain_settings(data, assistant_id=1, account_id=2):
    """
    Update Captain AI assistant settings and linked inboxes in Chatwoot database.
    """
    try:
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor()

        cur.execute("SELECT config FROM captain_assistants WHERE id = %s AND account_id = %s", (assistant_id, account_id))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False, "المساعد غير موجود"

        config = row[0] or {}
        if not isinstance(config, dict):
            config = {}

        if 'product_name' in data:
            config['product_name'] = str(data['product_name']).strip()
        if 'temperature' in data:
            try:
                config['temperature'] = float(data['temperature'])
            except (ValueError, TypeError):
                config['temperature'] = 0.5
        if 'feature_faq' in data:
            config['feature_faq'] = bool(data['feature_faq'])

        name = str(data.get('name', 'المساعد الذكي')).strip() or 'المساعد الذكي'
        description = str(data.get('description', '')).strip()

        guidelines = data.get('response_guidelines', [])
        if isinstance(guidelines, str):
            guidelines = [line.strip() for line in guidelines.split('\n') if line.strip()]

        guardrails = data.get('guardrails', [])
        if isinstance(guardrails, str):
            guardrails = [line.strip() for line in guardrails.split('\n') if line.strip()]

        cur.execute("""
            UPDATE captain_assistants
            SET name = %s,
                description = %s,
                config = %s,
                response_guidelines = %s,
                guardrails = %s,
                updated_at = NOW()
            WHERE id = %s AND account_id = %s
        """, (
            name,
            description,
            json.dumps(config, ensure_ascii=False),
            json.dumps(guidelines, ensure_ascii=False),
            json.dumps(guardrails, ensure_ascii=False),
            assistant_id,
            account_id
        ))

        inbox_ids = data.get('inbox_ids')
        if inbox_ids is not None:
            target_ids = [int(i) for i in inbox_ids if str(i).isdigit()]

            if target_ids:
                cur.execute("""
                    DELETE FROM captain_inboxes
                    WHERE captain_assistant_id = %s AND inbox_id NOT IN %s
                """, (assistant_id, tuple(target_ids)))
            else:
                cur.execute("DELETE FROM captain_inboxes WHERE captain_assistant_id = %s", (assistant_id,))

            for i_id in target_ids:
                cur.execute("""
                    INSERT INTO captain_inboxes (captain_assistant_id, inbox_id, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    ON CONFLICT (captain_assistant_id, inbox_id) DO NOTHING
                """, (assistant_id, i_id))

        conn.commit()
        conn.close()
        logger.info(f"[ChatwootCaptain] Updated assistant {assistant_id} settings successfully.")
        return True, "تم حفظ إعدادات المساعد الذكي بنجاح"
    except Exception as e:
        logger.error(f"[ChatwootCaptain] Error updating settings: {e}", exc_info=True)
        return False, f"حدث خطأ أثناء حفظ الإعدادات: {str(e)}"
