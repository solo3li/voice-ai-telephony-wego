# SPDX-License-Identifier: Apache-2.0
import json
import logging
import re
import secrets
import urllib.parse
import psycopg2
import psycopg2.pool
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

_CHATWOOT_DB_POOL = None

def get_chatwoot_db_pool():
    global _CHATWOOT_DB_POOL
    if _CHATWOOT_DB_POOL is None or _CHATWOOT_DB_POOL.closed:
        try:
            _CHATWOOT_DB_POOL = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                **CHATWOOT_DB_CONFIG
            )
            logger.info("[ChatwootService] Initialized ThreadedConnectionPool (minconn=1, maxconn=20)")
        except Exception as e:
            logger.error(f"[ChatwootService] Failed to initialize ThreadedConnectionPool: {e}", exc_info=True)
            raise
    return _CHATWOOT_DB_POOL

class PooledChatwootConnection:
    """
    Wrapper around a pooled psycopg2 connection that returns the connection
    to the ThreadedConnectionPool on close(), rather than closing the underlying socket.
    Supports both context manager (with get_chatwoot_db_conn() as conn:) and standard conn.close() pattern.
    """
    def __init__(self, conn, pool_inst):
        self._conn = conn
        self._pool = pool_inst
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                if self._conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                    self._conn.rollback()
            except Exception:
                pass
            try:
                self._pool.putconn(self._conn)
            except Exception as e:
                logger.warning(f"[ChatwootService] Error returning connection to pool: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_chatwoot_db_conn():
    """
    Acquires a pooled connection from the ThreadedConnectionPool.
    Returns a PooledChatwootConnection wrapper.
    """
    p = get_chatwoot_db_pool()
    raw_conn = p.getconn()
    return PooledChatwootConnection(raw_conn, p)

CHATWOOT_REDIS_CONFIG = {
    "host": "omni_redis",
    "port": 6379,
    "password": "ChatwootRedisPassword2026",
    "db": 0
}

CHATWOOT_BASE_URL = getattr(settings, 'CHATWOOT_BASE_URL', 'https://chatwoot.169.58.32.179.nip.io')


def get_or_create_tenant_chatwoot(user):
    """
    Resolve or auto-provision Chatwoot Account, User, and Captain Assistant
    for multi-tenancy isolation.
    - Superuser / Platform Admin maps to Account 2.
    - Employee maps to their employer's tenant config.
    - Regular tenant auto-provisions dedicated Account, User, and Assistant in Chatwoot DB.
    Guarantees concurrency safety via Django row locking and atomic PostgreSQL statements.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    from voice_assistant.models import TenantChatwootConfig
    from django.db import transaction

    # 1. If user is an employee, map to their employer's tenant config
    effective_user = user
    if hasattr(user, 'employee_profile') and user.employee_profile and user.employee_profile.employer:
        effective_user = user.employee_profile.employer

    # 2. Superuser / Platform Admin maps to Account 2
    if effective_user.is_superuser:
        config, _ = TenantChatwootConfig.objects.update_or_create(
            user=effective_user,
            defaults={
                'account_id': 2,
                'chatwoot_user_id': 2,
                'assistant_id': 1,
                'is_provisioned': True,
            }
        )
        return config

    # 3. Fast check existing config in Django
    config = TenantChatwootConfig.objects.filter(user=effective_user).first()
    if config and config.is_provisioned and config.account_id:
        return config

    # 4. Atomic lock to prevent duplicate concurrent provisioning
    with transaction.atomic():
        # Lock user row in Django DB
        from django.contrib.auth.models import User
        User.objects.select_for_update().get(id=effective_user.id)
        config = TenantChatwootConfig.objects.filter(user=effective_user).first()
        if config and config.is_provisioned and config.account_id:
            return config

        # Auto-provision in Chatwoot database (atomic SQL)
        conn = get_chatwoot_db_conn()
        try:
            cur = conn.cursor()

            # 4.1 Insert account
            acc_name = getattr(effective_user, 'first_name', '') or effective_user.username
            cur.execute("""
                INSERT INTO accounts (name, locale, created_at, updated_at, feature_flags, internal_attributes, feature_flags_ext_1)
                VALUES (%s, 1, NOW(), NOW(), 6338816368015572959, '{}'::jsonb, 15615)
                RETURNING id;
            """, (acc_name,))
            acc_id = cur.fetchone()[0]

            # 4.2 Insert or update user atomically
            email = effective_user.email or f"{effective_user.username}@tenant.local"
            name = effective_user.get_full_name() or effective_user.username
            pubsub_token = secrets.token_urlsafe(18)
            dummy_pwd = "$2a$11$620BW0C5baV6LeIlL1jNOuNAqoJ9dMmXSbR.2BAxlPmk8FZcs/cUG"

            cur.execute("""
                INSERT INTO users (name, email, uid, provider, encrypted_password, pubsub_token, confirmed_at, created_at, updated_at, ui_settings)
                VALUES (%s, %s, %s, 'email', %s, %s, NOW(), NOW(), NOW(), '{"locale": "ar"}'::jsonb)
                ON CONFLICT (uid, provider) DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email, updated_at = NOW()
                RETURNING id;
            """, (name, email, email, dummy_pwd, pubsub_token))
            cw_user_id = cur.fetchone()[0]

            # 4.3 Add user to account as admin (role: 1)
            cur.execute("""
                INSERT INTO account_users (account_id, user_id, role, availability, auto_offline, created_at, updated_at)
                VALUES (%s, %s, 1, 0, true, NOW(), NOW())
                ON CONFLICT (account_id, user_id) DO UPDATE SET role = EXCLUDED.role;
            """, (acc_id, cw_user_id))

            # 4.4 Add SuperAdmin user 2 as co-admin so backend API token can manage inboxes
            cur.execute("""
                INSERT INTO account_users (account_id, user_id, role, availability, auto_offline, created_at, updated_at)
                VALUES (%s, 2, 1, 0, true, NOW(), NOW())
                ON CONFLICT (account_id, user_id) DO UPDATE SET role = EXCLUDED.role;
            """, (acc_id,))

            # 4.5 Insert Captain AI assistant
            cur.execute("""
                INSERT INTO captain_assistants (account_id, name, config, response_guidelines, guardrails, created_at, updated_at)
                VALUES (%s, 'المساعد الذكي', '{"product_name": "", "temperature": 0.5, "feature_faq": true}'::jsonb, '[]'::jsonb, '[]'::jsonb, NOW(), NOW())
                RETURNING id;
            """, (acc_id,))
            assistant_id = cur.fetchone()[0]

            conn.commit()

            # 4.6 Save TenantChatwootConfig in Django
            config, _ = TenantChatwootConfig.objects.update_or_create(
                user=effective_user,
                defaults={
                    'account_id': acc_id,
                    'chatwoot_user_id': cw_user_id,
                    'assistant_id': assistant_id,
                    'is_provisioned': True,
                }
            )
            logger.info(f"[ChatwootMultiTenancy] Provisioned Chatwoot Account #{acc_id} (User #{cw_user_id}, Assistant #{assistant_id}) for {effective_user.username}")
            return config
        except Exception as e:
            conn.rollback()
            logger.error(f"[ChatwootMultiTenancy] Failed to provision tenant account for {effective_user.username}: {e}", exc_info=True)
            raise
        finally:
            conn.close()


def generate_chatwoot_sso_url(user=None, account_id=None, locale=None):
    """
    Generate a direct SSO login link for Chatwoot that logs the user in
    silently without asking for credentials, using Chatwoot's Redis Alfred SSO token.
    Supports setting the user's and account's active locale ('ar' or 'en').
    Automatically resolves tenant's account_id and user's Chatwoot identity:
    - If user is an employee, auto-provisions their distinct agent user in the tenant's account.
    - Adds user to account_users and all existing inboxes for immediate visibility.
    """
    try:
        cfg = None
        if user and getattr(user, 'is_authenticated', False):
            cfg = get_or_create_tenant_chatwoot(user)
            if cfg and (account_id is None or account_id == 2):
                account_id = cfg.account_id

        if account_id is None:
            account_id = 2

        conn = get_chatwoot_db_conn()
        cur = conn.cursor()

        chatwoot_user = None
        user_email = None
        if user and getattr(user, 'is_authenticated', False):
            user_email = getattr(user, 'email', None) or f"{user.username}@tenant.local"

        # 1. Try finding Chatwoot user by user_email
        if user_email:
            cur.execute("SELECT id, email FROM users WHERE email = %s LIMIT 1", (user_email,))
            chatwoot_user = cur.fetchone()

        # 2. If user is authenticated in Django but doesn't exist in Chatwoot users table yet, auto-provision them!
        if not chatwoot_user and user and getattr(user, 'is_authenticated', False):
            display_name = user.get_full_name() or getattr(getattr(user, 'employee_profile', None), 'display_name', None) or user.username
            pubsub_token = secrets.token_urlsafe(18)
            dummy_pwd = "$2a$11$620BW0C5baV6LeIlL1jNOuNAqoJ9dMmXSbR.2BAxlPmk8FZcs/cUG"
            cur.execute("""
                INSERT INTO users (name, email, uid, provider, encrypted_password, pubsub_token, confirmed_at, created_at, updated_at, ui_settings)
                VALUES (%s, %s, %s, 'email', %s, %s, NOW(), NOW(), NOW(), '{"locale": "ar"}'::jsonb)
                ON CONFLICT (uid, provider) DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email, updated_at = NOW()
                RETURNING id, email;
            """, (display_name, user_email, user_email, dummy_pwd, pubsub_token))
            chatwoot_user = cur.fetchone()
            conn.commit()

        # 3. Try tenant config chatwoot_user_id (if user is employer)
        if not chatwoot_user and cfg and cfg.chatwoot_user_id and cfg.user_id == getattr(user, 'id', None):
            cur.execute("SELECT id, email FROM users WHERE id = %s LIMIT 1", (cfg.chatwoot_user_id,))
            chatwoot_user = cur.fetchone()

        # 4. If user is superuser, allow user 2
        if not chatwoot_user and user and getattr(user, 'is_superuser', False):
            cur.execute("SELECT id, email FROM users WHERE id = 2 LIMIT 1")
            chatwoot_user = cur.fetchone()

        # 5. If still no user, DO NOT fall back to SuperAdmin! Return account URL
        if not chatwoot_user:
            conn.close()
            logger.warning(f"[ChatwootSSO] No Chatwoot user found for user {getattr(user, 'username', 'anonymous')}")
            return f"{CHATWOOT_BASE_URL}/app/accounts/{account_id}"

        user_id, email = chatwoot_user[0], chatwoot_user[1]

        # Ensure user is linked in account_users for this account_id
        try:
            is_admin = bool(getattr(user, 'is_superuser', False) or (cfg and cfg.user_id == getattr(user, 'id', None)))
            role_to_set = 1 if is_admin else 0
            cur.execute("""
                INSERT INTO account_users (account_id, user_id, role, availability, auto_offline, created_at, updated_at)
                VALUES (%s, %s, %s, 0, true, NOW(), NOW())
                ON CONFLICT (account_id, user_id) DO NOTHING;
            """, (account_id, user_id, role_to_set))

            # Auto-assign user to all existing inboxes in this account
            cur.execute("""
                INSERT INTO inbox_members (user_id, inbox_id, created_at, updated_at)
                SELECT %s, id, NOW(), NOW()
                FROM inboxes
                WHERE account_id = %s
                ON CONFLICT (inbox_id, user_id) DO NOTHING;
            """, (user_id, account_id))
            conn.commit()
        except Exception as au_err:
            logger.warning(f"[ChatwootSSO] Warning ensuring account_users for user {user_id}: {au_err}")

        # Prevent Chatwoot 25-session limit (which causes HTTP 409 Conflict on /auth/sign_in)
        try:
            cur.execute("SELECT count(*) FROM user_sessions WHERE user_id = %s", (user_id,))
            sess_cnt = cur.fetchone()[0]
            if sess_cnt >= 10:
                cur.execute("""
                    DELETE FROM user_sessions 
                    WHERE user_id = %s AND id NOT IN (
                        SELECT id FROM user_sessions 
                        WHERE user_id = %s 
                        ORDER BY COALESCE(last_activity_at, created_at) DESC 
                        LIMIT 5
                    )
                """, (user_id, user_id))
                
                cur.execute("SELECT client_id FROM user_sessions WHERE user_id = %s", (user_id,))
                active_clients = {r[0] for r in cur.fetchall()}
                cur.execute("SELECT tokens FROM users WHERE id = %s", (user_id,))
                raw_tokens = cur.fetchone()[0]
                if raw_tokens:
                    tok_dict = raw_tokens if isinstance(raw_tokens, dict) else json.loads(raw_tokens)
                    pruned_dict = {k: v for k, v in tok_dict.items() if k in active_clients}
                    cur.execute("UPDATE users SET tokens = %s WHERE id = %s", (json.dumps(pruned_dict), user_id))
                conn.commit()
                logger.info(f"[ChatwootSSO] Pruned user {user_id} sessions from {sess_cnt} to prevent 409 Conflict.")
        except Exception as sess_err:
            logger.warning(f"[ChatwootSSO] Warning pruning old sessions: {sess_err}")

        # If locale is provided, synchronize with Chatwoot user & account
        norm_locale = 'en' if str(locale).lower().startswith('en') else 'ar' if locale else None
        if norm_locale:
            try:
                account_locale_int = 0 if norm_locale == 'en' else 1
                cur.execute("""
                    UPDATE users 
                    SET ui_settings = jsonb_set(COALESCE(ui_settings, '{}'), '{locale}', to_jsonb(%s::text))
                    WHERE id = %s
                """, (norm_locale, user_id))
                cur.execute("UPDATE accounts SET locale = %s WHERE id = %s", (account_locale_int, account_id))
                conn.commit()
                logger.info(f"[ChatwootSSO] Synchronized user {user_id} and account {account_id} locale to '{norm_locale}'")
            except Exception as loc_err:
                logger.warning(f"[ChatwootSSO] Could not update locale in DB: {loc_err}")

        conn.close()

        token = secrets.token_hex(32)

        # Store in Chatwoot's Redis
        r = redis.Redis(**CHATWOOT_REDIS_CONFIG)
        sso_key = f"alfred:USER_SSO_AUTH_TOKEN::{user_id}::{token}"
        r.set(sso_key, 'normal', ex=3600)  # 1 hour expiration

        encoded_email = urllib.parse.quote(email)
        redirect_target = f"/app/accounts/{account_id}"
        query_params = ["theme=light", "color_scheme=light"]
        if norm_locale:
            query_params.append(f"locale={norm_locale}")
        redirect_target += "?" + "&".join(query_params)

        sso_url = f"{CHATWOOT_BASE_URL}/app/login?email={encoded_email}&sso_auth_token={token}&redirect_url={urllib.parse.quote(redirect_target)}&theme=light&color_scheme=light"
        logger.info(f"[ChatwootSSO] Generated silent SSO link for user {email} (ID {user_id}) -> Account {account_id} [locale: {norm_locale}]")
        return sso_url
    except Exception as e:
        logger.error(f"[ChatwootSSO] Error generating SSO URL: {e}", exc_info=True)
        acc_fallback = account_id or 2
        return f"{CHATWOOT_BASE_URL}/app/accounts/{acc_fallback}"


def set_chatwoot_user_locale(user=None, account_id=None, locale='ar'):
    """
    Update Chatwoot user's ui_settings.locale and account.locale,
    and generate a fresh SSO URL matching the language.
    """
    norm_locale = 'en' if str(locale).lower().startswith('en') else 'ar'
    if account_id is None and user and getattr(user, 'is_authenticated', False):
        cfg = get_or_create_tenant_chatwoot(user)
        if cfg:
            account_id = cfg.account_id
    if account_id is None:
        account_id = 2
    sso_url = generate_chatwoot_sso_url(user=user, account_id=account_id, locale=norm_locale)
    return {
        "status": "success",
        "locale": norm_locale,
        "sso_url": sso_url
    }


def get_captain_settings(assistant_id=None, account_id=2):
    """
    Retrieve Captain AI assistant settings and linked inboxes from Chatwoot database.
    """
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        assistant = None
        if assistant_id:
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
            "account_id": account_id,
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


def update_captain_settings(data, assistant_id=None, account_id=2):
    """
    Update Captain AI assistant settings and linked inboxes in Chatwoot database.
    """
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor()

        if assistant_id:
            cur.execute("SELECT id, config FROM captain_assistants WHERE id = %s AND account_id = %s", (assistant_id, account_id))
            row = cur.fetchone()
        else:
            row = None

        if not row:
            cur.execute("SELECT id, config FROM captain_assistants WHERE account_id = %s ORDER BY id ASC LIMIT 1", (account_id,))
            row = cur.fetchone()

        if not row:
            conn.close()
            return False, "المساعد غير موجود"

        actual_assistant_id = row[0]
        config = row[1] or {}
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
            actual_assistant_id,
            account_id
        ))

        inbox_ids = data.get('inbox_ids')
        if inbox_ids is not None:
            target_ids = [int(i) for i in inbox_ids if str(i).isdigit()]

            # Enforce that inboxes belong to account_id
            if target_ids:
                cur.execute("SELECT id FROM inboxes WHERE account_id = %s AND id IN %s", (account_id, tuple(target_ids)))
                valid_ids = [r[0] for r in cur.fetchall()]
            else:
                valid_ids = []

            if valid_ids:
                cur.execute("""
                    DELETE FROM captain_inboxes
                    WHERE captain_assistant_id = %s AND inbox_id NOT IN %s
                """, (actual_assistant_id, tuple(valid_ids)))
            else:
                cur.execute("DELETE FROM captain_inboxes WHERE captain_assistant_id = %s", (actual_assistant_id,))

            for i_id in valid_ids:
                cur.execute("""
                    INSERT INTO captain_inboxes (captain_assistant_id, inbox_id, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    ON CONFLICT (captain_assistant_id, inbox_id) DO NOTHING
                """, (actual_assistant_id, i_id))

        conn.commit()
        conn.close()
        logger.info(f"[ChatwootCaptain] Updated assistant {actual_assistant_id} (account {account_id}) settings successfully.")
        return True, "تم حفظ إعدادات المساعد الذكي بنجاح"
    except Exception as e:
        logger.error(f"[ChatwootCaptain] Error updating settings: {e}", exc_info=True)
        return False, f"حدث خطأ أثناء حفظ الإعدادات: {str(e)}"



# ==============================================================================
# CHANNELS & INTEGRATIONS MANAGEMENT (WHATSAPP, META, TELEGRAM, FB, IG, WEB)
# ==============================================================================

CHATWOOT_INTERNAL_API = "http://omni_chatwoot_rails:3000/api/v1/accounts/2"
CHATWOOT_API_TOKEN = "jXAkbazr7faTZWeoNbVf8Lt2"
EVOLUTION_API_URL = "http://omni_evolution_api:8080"
EVOLUTION_API_KEY = "evolution_secret_key_123"


def _get_account_user_ids(account_id=2):
    """Fetch all user IDs belonging to a Chatwoot account."""
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM account_users WHERE account_id = %s", (account_id,))
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error fetching account user ids: {e}")
        return []


def _assign_all_agents_to_inbox(inbox_id, account_id=2):
    """
    Auto-assign all agents and administrators in the account to the inbox
    so it becomes visible immediately in Chatwoot UI and ActionCable streams.
    """
    user_ids = _get_account_user_ids(account_id)
    if not user_ids:
        return False

    import urllib.request
    # 1. Call Chatwoot API to trigger ActionCable broadcasts
    try:
        url = f"http://omni_chatwoot_rails:3000/api/v1/accounts/{account_id}/inbox_members"
        payload = {"inbox_id": inbox_id, "user_ids": user_ids}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "api_access_token": CHATWOOT_API_TOKEN,
                "X-Forwarded-Proto": "https",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            logger.info(f"[ChatwootChannels] Auto-assigned users {user_ids} to inbox {inbox_id} via API")
    except Exception as e:
        logger.warning(f"[ChatwootChannels] Warning auto-assigning inbox_members via API: {e}")

    # 2. Direct DB fallback to guarantee persistence
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor()
        for uid in user_ids:
            cur.execute("""
                INSERT INTO inbox_members (user_id, inbox_id, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                ON CONFLICT (inbox_id, user_id) DO NOTHING
            """, (uid, inbox_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error in DB fallback for inbox_members: {e}")

    return True


def _patch_chatwoot_inbox(inbox_id, payload, account_id=2):
    """
    Update inbox properties via Chatwoot Rails API so cache is cleared and
    ActionCable broadcasts update events to all active sessions.
    """
    import urllib.request
    url = f"http://omni_chatwoot_rails:3000/api/v1/accounts/{account_id}/inboxes/{inbox_id}"
    data_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "api_access_token": CHATWOOT_API_TOKEN,
            "X-Forwarded-Proto": "https",
            "Content-Type": "application/json"
        },
        method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        body = err.read().decode('utf-8', errors='ignore')
        logger.error(f"[ChatwootAPI] HTTPError patching inbox {inbox_id} ({err.code}): {body}")
        try:
            return json.loads(body)
        except Exception:
            return {"message": f"Chatwoot Error {err.code}: {body[:200]}"}
    except Exception as e:
        logger.error(f"[ChatwootAPI] Error patching inbox {inbox_id}: {e}")
        return {}


def get_all_channels_detailed(account_id=2, assistant_id=1):
    """
    Retrieve all inboxes/channels with their live status, configuration,
    grouped by platform, and whether Captain AI auto-reply is active.
    """
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch inboxes joined with active captain_inboxes
        cur.execute("""
            SELECT 
                i.id,
                i.name,
                i.channel_id,
                i.channel_type,
                i.created_at,
                CASE WHEN ci.id IS NOT NULL THEN true ELSE false END AS is_captain_enabled
            FROM inboxes i
            LEFT JOIN captain_inboxes ci 
                ON ci.inbox_id = i.id AND ci.captain_assistant_id = %s
            WHERE i.account_id = %s
            ORDER BY i.id ASC
        """, (assistant_id, account_id))
        inboxes = cur.fetchall()

        # Fetch all Evolution instances for real-time status mapping
        evolution_instances_map = {}
        try:
            import urllib.request
            req = urllib.request.Request(f"{EVOLUTION_API_URL}/instance/fetchInstances", headers={"apikey": EVOLUTION_API_KEY})
            with urllib.request.urlopen(req, timeout=4) as resp:
                inst_list = json.loads(resp.read().decode())
                for inst in inst_list:
                    evolution_instances_map[inst.get('name')] = inst
        except Exception as e:
            logger.warning(f"[EvolutionAPI] Failed to fetch instances: {e}")

        channels_list = []
        for ibx in inboxes:
            c_type = ibx['channel_type']
            c_id = ibx['channel_id']
            name = ibx['name'] or ''
            is_archived = name.startswith("[مؤرشف]") or name.startswith("[Archived]")
            details = {
                "id": ibx['id'],
                "name": name,
                "channel_type": c_type,
                "platform": "api",
                "is_captain_enabled": ibx['is_captain_enabled'],
                "is_archived": is_archived,
                "created_at": ibx['created_at'].strftime("%Y-%m-%d %H:%M") if ibx.get('created_at') else "",
                "status": "archived" if is_archived else "connected",
                "identifier": "",
                "instance_name": None,
                "extra": {}
            }

            if c_type == 'Channel::Telegram':
                details['platform'] = 'telegram'
                cur.execute("SELECT bot_name, bot_token FROM channel_telegram WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = f"@{row['bot_name']}" if row.get('bot_name') else "Telegram Bot"
                    details['status'] = "connected" if row.get('bot_token') else "disconnected"

            elif c_type == 'Channel::Whatsapp':
                details['platform'] = 'whatsapp_cloud'
                cur.execute("SELECT phone_number, provider, provider_config FROM channel_whatsapp WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('phone_number') or "WhatsApp Cloud"
                    details['extra']['provider'] = row.get('provider')
                    details['status'] = "connected"

            elif c_type == 'Channel::Api':
                cur.execute("SELECT webhook_url, identifier FROM channel_api WHERE id = %s", (c_id,))
                row = cur.fetchone()
                webhook_url = row.get('webhook_url') if row else ""
                details['identifier'] = row.get('identifier') or "API Channel"
                details['extra']['webhook_url'] = webhook_url

                # Check if this is an Evolution API WhatsApp instance
                if webhook_url and '/chatwoot/webhook/' in webhook_url:
                    details['platform'] = 'whatsapp_qr'
                    inst_name = webhook_url.split('/chatwoot/webhook/')[-1].strip('/')
                    details['instance_name'] = inst_name
                    details['channel_subtype'] = 'whatsapp_evolution'

                    # Map live status from Evolution
                    evo = evolution_instances_map.get(inst_name)
                    if evo:
                        details['status'] = evo.get('connectionStatus') or 'connecting'
                        if evo.get('ownerJid'):
                            details['identifier'] = evo.get('ownerJid').replace('@s.whatsapp.net', '')
                            details['extra']['phone'] = details['identifier']
                            details['extra']['profile_name'] = evo.get('profileName')
                        else:
                            details['identifier'] = inst_name
                    else:
                        details['status'] = 'disconnected'
                        details['identifier'] = inst_name
                elif 'whatsapp' in ibx['name'].lower():
                    details['platform'] = 'whatsapp_qr'
                    details['instance_name'] = ibx['name']
                    details['identifier'] = ibx['name']
                else:
                    details['platform'] = 'api'

            elif c_type == 'Channel::WebWidget':
                details['platform'] = 'web_widget'
                cur.execute("SELECT website_url, website_token, widget_color, welcome_title, welcome_tagline FROM channel_web_widgets WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('website_url') or "Web Chat Widget"
                    details['extra'] = {
                        "website_token": row.get('website_token'),
                        "widget_color": row.get('widget_color'),
                        "welcome_title": row.get('welcome_title'),
                        "welcome_tagline": row.get('welcome_tagline'),
                        "script": f"""<script>
  (function(d,t) {{
    var BASE_URL="{CHATWOOT_BASE_URL}";
    var g=d.createElement(t),s=d.getElementsByTagName(t)[0];
    g.src=BASE_URL+"/packs/js/sdk.js";
    g.async = true;
    s.parentNode.insertBefore(g,s);
    g.onload=function(){{
      window.chatwootSDK.run({{
        websiteToken: '{row.get("website_token")}',
        baseUrl: BASE_URL
      }})
    }}
  }})(document,"script");
</script>"""
                    }

            elif c_type == 'Channel::FacebookPage':
                details['platform'] = 'facebook'
                cur.execute("SELECT page_id FROM channel_facebook_pages WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = f"Page ID: {row.get('page_id')}"
                    details['status'] = "connected"

            elif c_type == 'Channel::Instagram':
                details['platform'] = 'instagram'
                cur.execute("SELECT instagram_id FROM channel_instagram WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = f"IG ID: {row.get('instagram_id')}"
                    details['status'] = "connected"

            elif c_type == 'Channel::Email':
                details['platform'] = 'email'
                cur.execute("SELECT email, imap_enabled, smtp_enabled FROM channel_email WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('email')
                    details['status'] = "connected"

            elif c_type in ('Channel::Sms', 'Channel::TwilioSms'):
                details['platform'] = 'sms'
                cur.execute("SELECT phone_number FROM channel_twilio_sms WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('phone_number')
                    details['status'] = "connected"

            channels_list.append(details)

        conn.close()

        # Group channels by platform for the UI
        grouped = {
            "whatsapp_qr": [],
            "whatsapp_cloud": [],
            "telegram": [],
            "facebook": [],
            "instagram": [],
            "web_widget": [],
            "email": [],
            "sms": [],
            "api": [],
            "archived": []
        }

        active_channels_list = []
        archived_channels_list = []

        for ch in channels_list:
            if ch.get('is_archived'):
                grouped['archived'].append(ch)
                archived_channels_list.append(ch)
            else:
                active_channels_list.append(ch)
                plt = ch.get('platform', 'api')
                if plt in grouped:
                    grouped[plt].append(ch)
                else:
                    grouped['api'].append(ch)

        # Scoped Evolution instances for this account (prevents cross-tenant leak)
        tenant_instance_names = {
            ch['instance_name'] for ch in channels_list if ch.get('instance_name')
        }
        if account_id == 2:
            tenant_instance_names.add('whatsapp_main')

        scoped_evo_instances = [
            inst for inst in evolution_instances_map.values()
            if inst.get('name') in tenant_instance_names or inst.get('name', '').startswith(f"acc{account_id}_")
        ]

        evolution_status = None
        if account_id == 2:
            evolution_status = get_evolution_instance_status('whatsapp_main')
        elif scoped_evo_instances:
            first_inst = scoped_evo_instances[0]
            evolution_status = {
                "instance_name": first_inst.get('name'),
                "connection_status": first_inst.get('connectionStatus', 'close'),
                "owner_jid": first_inst.get('ownerJid'),
                "profile_name": first_inst.get('profileName'),
                "profile_pic": first_inst.get('profilePicUrl')
            }
        else:
            evolution_status = {"instance_name": None, "connection_status": "disconnected"}

        return {
            "ok": True,
            "channels": active_channels_list,
            "archived_channels": archived_channels_list,
            "all_channels": channels_list,
            "grouped": grouped,
            "evolution": evolution_status,
            "evolution_instances": scoped_evo_instances
        }
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error listing channels: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "channels": [], "grouped": {}}


def toggle_channel_ai(inbox_id, enable=True, assistant_id=1, account_id=None):
    """
    Toggle Captain AI auto-reply on a specific inbox.
    """
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor()

        if account_id:
            cur.execute("SELECT id FROM inboxes WHERE id = %s AND account_id = %s", (inbox_id, account_id))
            if not cur.fetchone():
                conn.close()
                return False, "القناة غير موجودة أو غير تابعة لهذا الحساب"

        if enable:
            cur.execute("""
                INSERT INTO captain_inboxes (captain_assistant_id, inbox_id, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                ON CONFLICT (captain_assistant_id, inbox_id) DO NOTHING
            """, (assistant_id, inbox_id))
        else:
            cur.execute("""
                DELETE FROM captain_inboxes
                WHERE captain_assistant_id = %s AND inbox_id = %s
            """, (assistant_id, inbox_id))

        conn.commit()
        conn.close()
        return True, "تم تحديث حالة رد الذكاء الاصطناعي للقناة بنجاح"
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error toggling AI: {e}", exc_info=True)
        return False, f"فشل تحديث حالة الذكاء الاصطناعي: {str(e)}"


def update_channel_inbox(inbox_id, data, account_id=2, assistant_id=1):
    """
    Update channel inbox details (name, AI toggle, etc.).
    Synchronizes with Chatwoot API and Evolution API in real-time.
    Enforces tenant ownership.
    """
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Anti-IDOR: verify ownership first
        cur.execute("SELECT id, channel_id, channel_type, name FROM inboxes WHERE id = %s AND account_id = %s", (inbox_id, account_id))
        ibx = cur.fetchone()
        if not ibx:
            conn.close()
            return False, "القناة غير موجودة أو غير تابعة لهذا الحساب"

        new_name = data.get('name')
        if new_name:
            new_name = new_name.strip()
            # 1. Update via Chatwoot Rails API to invalidate cache and broadcast ActionCable event
            _patch_chatwoot_inbox(inbox_id, {"name": new_name}, account_id)

            # 2. Update database record
            cur.execute("""
                UPDATE inboxes
                SET name = %s, updated_at = NOW()
                WHERE id = %s AND account_id = %s
            """, (new_name, inbox_id, account_id))

            # 3. If WhatsApp QR (Evolution), update nameInbox in Evolution API
            if ibx['channel_type'] == 'Channel::Api':
                cur.execute("SELECT webhook_url FROM channel_api WHERE id = %s", (ibx['channel_id'],))
                ch_api = cur.fetchone()
                if ch_api and ch_api.get('webhook_url') and '/chatwoot/webhook/' in ch_api['webhook_url']:
                    inst_name = ch_api['webhook_url'].split('/chatwoot/webhook/')[-1].strip('/')
                    try:
                        import urllib.request
                        set_cw_url = f"{EVOLUTION_API_URL}/chatwoot/set/{inst_name}"
                        set_payload = json.dumps({
                            "enabled": True,
                            "nameInbox": new_name
                        }).encode('utf-8')
                        req = urllib.request.Request(
                            set_cw_url,
                            data=set_payload,
                            headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
                        )
                        urllib.request.urlopen(req, timeout=4)
                    except Exception as e:
                        logger.warning(f"[EvolutionAPI] Warning updating name on {inst_name}: {e}")

        conn.commit()
        conn.close()

        if 'enable_ai' in data:
            enable = bool(data.get('enable_ai'))
            toggle_channel_ai(inbox_id, enable=enable, assistant_id=assistant_id, account_id=account_id)

        return True, "تم تحديث بيانات القناة بنجاح ومزامنتها مع شات وت"
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error updating inbox {inbox_id}: {e}", exc_info=True)
        return False, f"فشل تحديث القناة: {str(e)}"



def delete_channel_inbox(inbox_id, account_id=2):
    """
    Archive channel inbox for read-only reference ("2+ للقراءة فقط"):
    - Disconnect Evolution API WhatsApp instance if applicable so phone session terminates.
    - Remove from Captain AI auto-response so bot never replies.
    - Prefix inbox name with [مؤرشف] in Chatwoot API & DB so agents see it as archived.
    - Set allow_messages_after_resolved = false.
    - Keep all previous conversations, messages, and contact links intact for read-only viewing in Chatwoot.
    """
    import urllib.request
    try:
        conn = get_chatwoot_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT channel_id, channel_type, name FROM inboxes WHERE id = %s AND account_id = %s", (inbox_id, account_id))
        ibx = cur.fetchone()
        if not ibx:
            conn.close()
            return False, "القناة غير موجودة"

        current_name = ibx['name']
        channel_id = ibx['channel_id']
        channel_type = ibx['channel_type']

        # 1. Disconnect Evolution WhatsApp instance if applicable
        if channel_type == 'Channel::Api':
            cur.execute("SELECT webhook_url FROM channel_api WHERE id = %s", (channel_id,))
            ch_api = cur.fetchone()
            if ch_api and ch_api.get('webhook_url') and '/chatwoot/webhook/' in ch_api['webhook_url']:
                inst_name = ch_api['webhook_url'].split('/chatwoot/webhook/')[-1].strip('/')
                try:
                    # Logout and delete instance in Evolution API to release WhatsApp connection
                    del_url = f"{EVOLUTION_API_URL}/instance/delete/{inst_name}"
                    req = urllib.request.Request(del_url, headers={"apikey": EVOLUTION_API_KEY}, method="DELETE")
                    urllib.request.urlopen(req, timeout=5)
                    logger.info(f"[EvolutionAPI] Deleted instance {inst_name} on channel archive")
                except Exception as ev_err:
                    logger.warning(f"[EvolutionAPI] Warning deleting instance {inst_name}: {ev_err}")

        # 2. Remove from Captain AI auto-response
        cur.execute("DELETE FROM captain_inboxes WHERE inbox_id = %s", (inbox_id,))

        # 3. Archive name: prefix with [مؤرشف]
        archived_name = current_name
        if not archived_name.startswith("[مؤرشف]"):
            archived_name = f"[مؤرشف] {current_name}"

        # 4. Sync with Chatwoot API so UI reflects archived state immediately
        _patch_chatwoot_inbox(inbox_id, {
            "name": archived_name,
            "allow_messages_after_resolved": False
        }, account_id)

        # 5. Update DB record to archived name
        cur.execute("""
            UPDATE inboxes 
            SET name = %s, updated_at = NOW() 
            WHERE id = %s AND account_id = %s
        """, (archived_name, inbox_id, account_id))

        conn.commit()
        conn.close()

        return True, "تم أرشفة القناة وقطع اتصالها بنجاح مع الاحتفاظ بكافة المحادثات للقراءة فقط في شات وت"
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error archiving inbox {inbox_id}: {e}", exc_info=True)
        return False, f"فشل أرشفة القناة: {str(e)}"


def get_evolution_instance_status(instance_name='whatsapp_main'):
    """
    Get WhatsApp instance connection status from Evolution API.
    """
    import urllib.request
    try:
        url = f"{EVOLUTION_API_URL}/instance/fetchInstances"
        req = urllib.request.Request(url, headers={"apikey": EVOLUTION_API_KEY})
        with urllib.request.urlopen(req, timeout=4) as resp:
            instances = json.loads(resp.read().decode())
            for inst in instances:
                if inst.get('name') == instance_name:
                    return {
                        "instance_name": instance_name,
                        "connection_status": inst.get('connectionStatus', 'close'),
                        "owner_jid": inst.get('ownerJid'),
                        "profile_name": inst.get('profileName'),
                        "profile_pic": inst.get('profilePicUrl')
                    }
        return {"instance_name": instance_name, "connection_status": "disconnected"}
    except Exception as e:
        logger.warning(f"[EvolutionAPI] Error fetching instance status: {e}")
        return {"instance_name": instance_name, "connection_status": "unknown"}


def disconnect_evolution_instance(instance_name):
    """
    Disconnect / logout a WhatsApp Evolution session.
    """
    import urllib.request
    try:
        url = f"{EVOLUTION_API_URL}/instance/logout/{instance_name}"
        req = urllib.request.Request(url, headers={"apikey": EVOLUTION_API_KEY}, method="DELETE")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True, "تم قطع الاتصال بنجاح"
    except Exception as e:
        logger.warning(f"[EvolutionAPI] Disconnect error: {e}")
        return False, f"فشل قطع الاتصال: {str(e)}"


def get_evolution_whatsapp_qr(instance_name='whatsapp_main'):
    """
    Fetch a real-time live WhatsApp QR code from Evolution API for any instance.
    """
    import urllib.request
    try:
        # Check if instance exists or create it
        status_info = get_evolution_instance_status(instance_name)
        if status_info.get('connection_status') == 'unknown':
            # Create instance
            create_url = f"{EVOLUTION_API_URL}/instance/create"
            payload = json.dumps({
                "instanceName": instance_name,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS"
            }).encode('utf-8')
            req = urllib.request.Request(
                create_url,
                data=payload,
                headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
            )
            try:
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

        # Request connect QR
        connect_url = f"{EVOLUTION_API_URL}/instance/connect/{instance_name}"
        req = urllib.request.Request(connect_url, headers={"apikey": EVOLUTION_API_KEY})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
            qrcode_data = data.get('base64') or data.get('qrcode', {}).get('base64')
            code = data.get('code') or data.get('qrcode', {}).get('code')
            pairing_code = data.get('pairingCode') or data.get('qrcode', {}).get('pairingCode')

            return {
                "ok": True,
                "instance_name": instance_name,
                "qrcode": qrcode_data,
                "code": code,
                "pairing_code": pairing_code,
                "connection_status": data.get('status') or data.get('instance', {}).get('status', 'connecting')
            }
    except Exception as e:
        logger.error(f"[EvolutionAPI] Error fetching QR code for {instance_name}: {e}", exc_info=True)
        return {"ok": False, "instance_name": instance_name, "error": f"فشل جلب كود QR: {str(e)}"}


def create_channel_inbox(data, account_id=2, assistant_id=1):
    """
    Create a new inbox across any supported channel with multi-account support:
    - whatsapp_qr (Evolution API instance + Chatwoot API Channel)
    - whatsapp_cloud (Meta Cloud API)
    - telegram (BotFather token)
    - web_widget (Website chat)
    - facebook (Page ID + Access Token)
    - instagram (Instagram ID + Access Token)
    - email (IMAP/SMTP)
    - sms (Twilio)
    - api (Custom Webhook)
    """
    import urllib.request
    import re
    channel_type = data.get('channel_type')
    enable_ai = data.get('enable_ai', True)

    try:
        inbox_id = None
        instance_name = None

        if channel_type == 'whatsapp_qr':
            # Multi-account WhatsApp QR via Evolution API
            name = (data.get('name') or '').strip()
            if not name:
                # Count existing whatsapp_qr channels to suggest auto-name
                existing = get_all_channels_detailed(account_id, assistant_id).get('grouped', {}).get('whatsapp_qr', [])
                name = f"واتساب {len(existing) + 1}"

            # Generate sanitized unique instance name for Evolution scoped to account_id
            clean_token = secrets.token_hex(4)
            safe_slug = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())[:12].strip('_') or "wa"
            instance_name = f"acc{account_id}_{safe_slug}_{clean_token}"

            # 1. Create instance in Evolution API
            create_url = f"{EVOLUTION_API_URL}/instance/create"
            payload = json.dumps({
                "instanceName": instance_name,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS"
            }).encode('utf-8')
            req = urllib.request.Request(
                create_url,
                data=payload,
                headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                pass

            # 2. Create Channel::Api inbox in Chatwoot with webhook pointing to this instance
            cw_payload = {
                "name": name,
                "channel": {
                    "type": "api",
                    "webhook_url": f"http://169.58.32.179:8085/chatwoot/webhook/{instance_name}"
                }
            }
            res = _post_chatwoot_inbox(cw_payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل إنشاء صندوق الوارد في Chatwoot"
            inbox_id = res['id']

            # 3. Configure Evolution Chatwoot integration
            set_cw_url = f"{EVOLUTION_API_URL}/chatwoot/set/{instance_name}"
            set_payload = json.dumps({
                "enabled": True,
                "url": "https://chatwoot.169.58.32.179.nip.io",
                "accountId": str(account_id),
                "token": CHATWOOT_API_TOKEN,
                "signMsg": False,
                "reopenConversation": True,
                "conversationPending": False,
                "nameInbox": name
            }).encode('utf-8')
            req = urllib.request.Request(
                set_cw_url,
                data=set_payload,
                headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
            )
            try:
                urllib.request.urlopen(req, timeout=6)
            except Exception as set_err:
                logger.warning(f"[EvolutionAPI] Warning setting chatwoot on {instance_name}: {set_err}")

        elif channel_type == 'whatsapp_cloud':
            payload = {
                "name": data.get('name') or f"WhatsApp ({data.get('phone_number')})",
                "channel": {
                    "type": "whatsapp",
                    "phone_number": data.get('phone_number'),
                    "provider": "whatsapp_cloud",
                    "provider_config": {
                        "phone_number_id": data.get('phone_number_id'),
                        "api_key": data.get('api_key'),
                        "business_account_id": data.get('business_account_id')
                    }
                }
            }
            res = _post_chatwoot_inbox(payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل إنشاء قناة واتساب السحابية"
            inbox_id = res['id']

        elif channel_type == 'telegram':
            payload = {
                "name": data.get('name') or "Telegram Bot",
                "channel": {
                    "type": "telegram",
                    "bot_token": data.get('bot_token')
                }
            }
            res = _post_chatwoot_inbox(payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل ربط بوت تيليجرام، يرجى التأكد من صحة التوكن"
            inbox_id = res['id']

        elif channel_type == 'web_widget':
            payload = {
                "name": data.get('name') or "محادثة الموقع",
                "channel": {
                    "type": "web_widget",
                    "website_url": data.get('website_url', 'https://example.com'),
                    "widget_color": data.get('widget_color', '#7c3aed'),
                    "welcome_title": data.get('welcome_title', 'مرحباً بك!'),
                    "welcome_tagline": data.get('welcome_tagline', 'كيف يمكننا مساعدتك اليوم؟')
                }
            }
            res = _post_chatwoot_inbox(payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل إنشاء ودجت الموقع"
            inbox_id = res['id']

        elif channel_type == 'facebook':
            page_id = data.get('page_id')
            page_token = data.get('page_access_token')
            user_token = data.get('user_access_token') or page_token
            name = data.get('name') or f"Facebook ({page_id})"

            conn = get_chatwoot_db_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO channel_facebook_pages (page_id, user_access_token, page_access_token, account_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (page_id, account_id) DO UPDATE SET page_access_token = EXCLUDED.page_access_token
                RETURNING id
            """, (page_id, user_token, page_token, account_id))
            channel_id = cur.fetchone()[0]

            cur.execute("""
                SELECT id FROM inboxes 
                WHERE channel_id = %s AND channel_type = 'Channel::FacebookPage' AND account_id = %s
                LIMIT 1
            """, (channel_id, account_id))
            ibx_row = cur.fetchone()
            if ibx_row:
                inbox_id = ibx_row[0]
                cur.execute("UPDATE inboxes SET name = %s, updated_at = NOW() WHERE id = %s", (name, inbox_id))
            else:
                cur.execute("""
                    INSERT INTO inboxes (name, channel_id, channel_type, account_id, created_at, updated_at)
                    VALUES (%s, %s, 'Channel::FacebookPage', %s, NOW(), NOW())
                    RETURNING id
                """, (name, channel_id, account_id))
                inbox_id = cur.fetchone()[0]
            conn.commit()
            conn.close()

        elif channel_type == 'instagram':
            instagram_id = data.get('instagram_id')
            access_token = data.get('access_token')
            name = data.get('name') or f"Instagram ({instagram_id})"

            conn = get_chatwoot_db_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO channel_instagram (instagram_id, access_token, expires_at, account_id, created_at, updated_at)
                VALUES (%s, %s, NOW() + INTERVAL '60 days', %s, NOW(), NOW())
                ON CONFLICT (instagram_id) DO UPDATE SET access_token = EXCLUDED.access_token
                RETURNING id
            """, (instagram_id, access_token, account_id))
            channel_id = cur.fetchone()[0]

            cur.execute("""
                SELECT id FROM inboxes 
                WHERE channel_id = %s AND channel_type = 'Channel::Instagram' AND account_id = %s
                LIMIT 1
            """, (channel_id, account_id))
            ibx_row = cur.fetchone()
            if ibx_row:
                inbox_id = ibx_row[0]
                cur.execute("UPDATE inboxes SET name = %s, updated_at = NOW() WHERE id = %s", (name, inbox_id))
            else:
                cur.execute("""
                    INSERT INTO inboxes (name, channel_id, channel_type, account_id, created_at, updated_at)
                    VALUES (%s, %s, 'Channel::Instagram', %s, NOW(), NOW())
                    RETURNING id
                """, (name, channel_id, account_id))
                inbox_id = cur.fetchone()[0]
            conn.commit()
            conn.close()

        elif channel_type == 'email':
            payload = {
                "name": data.get('name') or data.get('email'),
                "channel": {
                    "type": "email",
                    "email": data.get('email')
                }
            }
            res = _post_chatwoot_inbox(payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل إنشاء قناة البريد الإلكتروني"
            inbox_id = res['id']

        elif channel_type == 'sms':
            payload = {
                "name": data.get('name') or data.get('phone_number'),
                "channel": {
                    "type": "sms",
                    "phone_number": data.get('phone_number'),
                    "account_sid": data.get('account_sid'),
                    "auth_token": data.get('auth_token')
                }
            }
            res = _post_chatwoot_inbox(payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل إعداد رسائل SMS"
            inbox_id = res['id']

        elif channel_type == 'api':
            payload = {
                "name": data.get('name') or "قناة برمجية (API)",
                "channel": {
                    "type": "api",
                    "webhook_url": data.get('webhook_url') or ""
                }
            }
            res = _post_chatwoot_inbox(payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل إنشاء القناة البرمجية"
            inbox_id = res['id']

        else:
            return False, f"نوع القناة غير مدعوم: {channel_type}"

        # Auto-assign all agents & administrators in this account so the inbox appears immediately in Chatwoot UI
        if inbox_id:
            _assign_all_agents_to_inbox(inbox_id, account_id=account_id)

        # If enable_ai is checked, auto-link to Captain AI
        if inbox_id and enable_ai:
            toggle_channel_ai(inbox_id, enable=True, assistant_id=assistant_id, account_id=account_id)

        msg = "تم ربط القناة بنجاح!"
        if channel_type == 'whatsapp_qr':
            msg = f"تم إنشاء حساب واتساب جديد ({instance_name}) وجاري تجهيز كود QR للمسح!"

        return True, msg, {"inbox_id": inbox_id, "instance_name": instance_name}
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error creating channel: {e}", exc_info=True)
        return False, f"حدث خطأ أثناء ربط القناة: {str(e)}", {}


def _post_chatwoot_inbox(payload, account_id=2):
    import urllib.request
    url = f"http://omni_chatwoot_rails:3000/api/v1/accounts/{account_id}/inboxes"
    data_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "api_access_token": CHATWOOT_API_TOKEN,
            "X-Forwarded-Proto": "https",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        body = err.read().decode('utf-8', errors='ignore')
        logger.error(f"[ChatwootAPI] HTTPError {err.code}: {body}")
        try:
            return json.loads(body)
        except Exception:
            return {"message": f"Chatwoot Error {err.code}: {body[:200]}"}


def create_website_channel(data, account_id=2, assistant_id=1):
    """
    Convenience function to create a Website Chat Widget channel with dynamic account_id.
    """
    payload = dict(data)
    payload['channel_type'] = 'web_widget'
    return create_channel_inbox(payload, account_id=account_id, assistant_id=assistant_id)


def create_telegram_channel(data, account_id=2, assistant_id=1):
    """
    Convenience function to create a Telegram Bot channel with dynamic account_id.
    """
    payload = dict(data)
    payload['channel_type'] = 'telegram'
    return create_channel_inbox(payload, account_id=account_id, assistant_id=assistant_id)


def sync_tenant_mcp_to_chatwoot(user):
    """
    Synchronizes all active MCP tools for a tenant into Chatwoot Captain AI
    (`captain_custom_tools` table in chatwoot_production).
    
    1. Fetches TenantChatwootConfig(user) to obtain tenant's account_id and assistant_id.
    2. Synchronizes all active tools into captain_custom_tools under that tenant's account only (never hardcoding Account 2).
    3. Injects endpoint: https://app.169.58.32.179.nip.io/api/mcp/execute/{user.id}/{tool.name}/ with headers: {"Authorization": "Bearer {secret}"}.
    4. Handles tool slug consistency (e.g. mcp_{user.id}_{tool.name}) to prevent tool duplication.
    5. Cleans up any stale tools for this tenant that are no longer active.
    """
    if isinstance(user, int):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(id=user).first()

    if not user or not getattr(user, 'is_authenticated', False):
        return {"status": "error", "message": "Invalid or unauthenticated user", "synced": 0}

    # If user is an employee, map to their employer's tenant config
    effective_user = user
    if hasattr(user, 'employee_profile') and user.employee_profile and user.employee_profile.employer:
        effective_user = user.employee_profile.employer

    from django.contrib.auth import get_user_model
    UserModel = get_user_model()
    if not effective_user or not getattr(effective_user, 'id', None) or not UserModel.objects.filter(id=effective_user.id).exists():
        return {"status": "error", "message": "User does not exist or is being deleted", "synced": 0}

    from voice_assistant.models import TenantChatwootConfig
    config = TenantChatwootConfig.objects.filter(user=effective_user).first()
    if not config or not config.account_id or not config.assistant_id:
        try:
            config = get_or_create_tenant_chatwoot(effective_user)
        except Exception as prov_err:
            logger.warning(f"[MCP-ChatwootSync] Failed to auto-provision Chatwoot for tenant #{effective_user.id}: {prov_err}")
            return {"status": "error", "message": f"Chatwoot config not found or could not be provisioned: {prov_err}", "synced": 0}

    from voice_assistant.models import generate_mcp_webhook_secret
    if not config.mcp_webhook_secret:
        config.mcp_webhook_secret = generate_mcp_webhook_secret()
        config.save(update_fields=['mcp_webhook_secret'])

    from agents.models import UserMCPServer
    active_servers = UserMCPServer.objects.filter(user=effective_user, is_active=True).order_by('-updated_at')

    active_tools = []
    seen_tool_names = set()
    for s in active_servers:
        for t in (s.cached_tools or []):
            t_name = t.get('name')
            if not t_name or t_name in seen_tool_names:
                continue
            seen_tool_names.add(t_name)
            active_tools.append((t, s))

    account_id = config.account_id
    assistant_id = config.assistant_id
    secret = config.mcp_webhook_secret
    base_url = getattr(settings, 'APP_BASE_URL', 'https://app.169.58.32.179.nip.io').rstrip('/')

    active_slugs = []
    with get_chatwoot_db_conn() as conn:
        try:
            cur = conn.cursor()
            for tool, server in active_tools:
                t_name = tool.get('name', '')
                t_desc = tool.get('description', '') or f"Tool {t_name} from {server.name}"
                slug = f"mcp_{effective_user.id}_{t_name}"
                active_slugs.append(slug)

                endpoint_url = f"{base_url}/api/mcp/execute/{effective_user.id}/{t_name}/"
                headers_json = json.dumps({"Authorization": f"Bearer {secret}"})
                auth_config_json = json.dumps({"token": secret})

                schema = tool.get('parameters') or tool.get('inputSchema') or {}
                props = schema.get('properties', {}) if isinstance(schema, dict) else {}
                required_fields = schema.get('required', []) if isinstance(schema, dict) else []
                param_schema = []
                template_parts = []
                for p_name, p_def in props.items():
                    p_type = p_def.get('type', 'string') if isinstance(p_def, dict) else 'string'
                    p_desc = p_def.get('description', '') if isinstance(p_def, dict) else ''
                    param_schema.append({
                        "name": p_name,
                        "type": p_type,
                        "required": p_name in required_fields,
                        "description": p_desc
                    })
                    if p_type in ('integer', 'number', 'boolean'):
                        template_parts.append(f'"{p_name}": {{{{ {p_name} | default: 0 }}}}')
                    else:
                        template_parts.append(f'"{p_name}": "{{{{ {p_name} }}}}"')

                request_template = "{" + ", ".join(template_parts) + "}" if template_parts else "{}"
                param_schema_json = json.dumps(param_schema)
                title = f"{t_name} ({server.name})"

                cur.execute("""
                    INSERT INTO captain_custom_tools (
                        account_id, assistant_id, slug, title, description,
                        http_method, endpoint_url, headers, param_schema,
                        request_template, auth_type, auth_config, enabled,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, 'POST', %s, %s::jsonb, %s::jsonb, %s, 'bearer', %s::jsonb, true, NOW(), NOW())
                    ON CONFLICT (assistant_id, slug) DO UPDATE SET
                        account_id = EXCLUDED.account_id,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        http_method = EXCLUDED.http_method,
                        endpoint_url = EXCLUDED.endpoint_url,
                        headers = EXCLUDED.headers,
                        param_schema = EXCLUDED.param_schema,
                        request_template = EXCLUDED.request_template,
                        auth_type = EXCLUDED.auth_type,
                        auth_config = EXCLUDED.auth_config,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW();
                """, (
                    account_id, assistant_id, slug, title, t_desc,
                    endpoint_url, headers_json, param_schema_json,
                    request_template, auth_config_json
                ))

            tenant_prefix = f"mcp_{effective_user.id}_%"
            if active_slugs:
                cur.execute("""
                    DELETE FROM captain_custom_tools
                    WHERE assistant_id = %s
                      AND slug LIKE %s
                      AND slug NOT IN %s;
                """, (assistant_id, tenant_prefix, tuple(active_slugs)))
            else:
                cur.execute("""
                    DELETE FROM captain_custom_tools
                    WHERE assistant_id = %s
                      AND slug LIKE %s;
                """, (assistant_id, tenant_prefix))

            conn.commit()
            logger.info(f"[MCP-ChatwootSync] Synced {len(active_tools)} tools for tenant {effective_user.username} (Account #{account_id}, Assistant #{assistant_id})")
            return {
                "status": "success",
                "synced": len(active_tools),
                "account_id": account_id,
                "assistant_id": assistant_id,
                "tools": [t[0].get('name') for t in active_tools]
            }
        except Exception as e:
            conn.rollback()
            logger.error(f"[MCP-ChatwootSync] Failed to sync tools for tenant {effective_user.username}: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "synced": 0}


