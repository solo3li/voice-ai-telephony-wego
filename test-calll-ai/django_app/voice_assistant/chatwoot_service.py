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


# ==============================================================================
# CHANNELS & INTEGRATIONS MANAGEMENT (WHATSAPP, META, TELEGRAM, FB, IG, WEB)
# ==============================================================================

CHATWOOT_INTERNAL_API = "http://omni_chatwoot_rails:3000/api/v1/accounts/2"
CHATWOOT_API_TOKEN = "jXAkbazr7faTZWeoNbVf8Lt2"
EVOLUTION_API_URL = "http://omni_evolution_api:8080"
EVOLUTION_API_KEY = "evolution_secret_key_123"


def get_all_channels_detailed(account_id=2, assistant_id=1):
    """
    Retrieve all inboxes/channels with their live status, configuration,
    and whether Captain AI auto-reply is active.
    """
    try:
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
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

        channels_list = []
        for ibx in inboxes:
            c_type = ibx['channel_type']
            c_id = ibx['channel_id']
            details = {
                "id": ibx['id'],
                "name": ibx['name'],
                "channel_type": c_type,
                "is_captain_enabled": ibx['is_captain_enabled'],
                "created_at": ibx['created_at'].strftime("%Y-%m-%d %H:%M") if ibx.get('created_at') else "",
                "status": "connected",
                "identifier": "",
                "extra": {}
            }

            if c_type == 'Channel::Telegram':
                cur.execute("SELECT bot_name, bot_token FROM channel_telegram WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = f"@{row['bot_name']}" if row.get('bot_name') else "Telegram Bot"
                    details['status'] = "connected" if row.get('bot_token') else "disconnected"

            elif c_type == 'Channel::Whatsapp':
                cur.execute("SELECT phone_number, provider, provider_config FROM channel_whatsapp WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('phone_number') or "WhatsApp Cloud"
                    details['extra']['provider'] = row.get('provider')
                    details['status'] = "connected"

            elif c_type == 'Channel::Api':
                cur.execute("SELECT webhook_url, identifier FROM channel_api WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('identifier') or "API Channel"
                    details['extra']['webhook_url'] = row.get('webhook_url')
                    # If this is Evolution API WhatsApp
                    if 'whatsapp' in ibx['name'].lower() or 'evolution' in (row.get('webhook_url') or ''):
                        details['channel_subtype'] = 'whatsapp_evolution'

            elif c_type == 'Channel::WebWidget':
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
                cur.execute("SELECT page_id FROM channel_facebook_pages WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = f"Page ID: {row.get('page_id')}"
                    details['status'] = "connected"

            elif c_type == 'Channel::Instagram':
                cur.execute("SELECT instagram_id FROM channel_instagram WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = f"IG ID: {row.get('instagram_id')}"
                    details['status'] = "connected"

            elif c_type == 'Channel::Email':
                cur.execute("SELECT email, imap_enabled, smtp_enabled FROM channel_email WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('email')
                    details['status'] = "connected"

            elif c_type in ('Channel::Sms', 'Channel::TwilioSms'):
                cur.execute("SELECT phone_number FROM channel_twilio_sms WHERE id = %s", (c_id,))
                row = cur.fetchone()
                if row:
                    details['identifier'] = row.get('phone_number')
                    details['status'] = "connected"

            channels_list.append(details)

        conn.close()

        # Check Evolution API status for WhatsApp QR
        evolution_status = get_evolution_instance_status('whatsapp_main')

        return {
            "ok": True,
            "channels": channels_list,
            "evolution": evolution_status
        }
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error listing channels: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "channels": []}


def toggle_channel_ai(inbox_id, enable=True, assistant_id=1):
    """
    Toggle Captain AI auto-reply on a specific inbox.
    """
    try:
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor()

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


def delete_channel_inbox(inbox_id, account_id=2):
    """
    Delete an inbox from Chatwoot.
    """
    import urllib.request
    try:
        # Try via Chatwoot API first
        url = f"{CHATWOOT_INTERNAL_API}/inboxes/{inbox_id}"
        req = urllib.request.Request(
            url,
            headers={
                "api_access_token": CHATWOOT_API_TOKEN,
                "X-Forwarded-Proto": "https"
            },
            method="DELETE"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 204):
                    return True, "تم حذف القناة بنجاح"
        except Exception:
            pass

        # Fallback to direct DB cascade deletion
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor()
        cur.execute("DELETE FROM captain_inboxes WHERE inbox_id = %s", (inbox_id,))
        cur.execute("DELETE FROM inboxes WHERE id = %s AND account_id = %s", (inbox_id, account_id))
        conn.commit()
        conn.close()
        return True, "تم حذف القناة بنجاح"
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error deleting inbox {inbox_id}: {e}", exc_info=True)
        return False, f"فشل حذف القناة: {str(e)}"


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


def get_evolution_whatsapp_qr(instance_name='whatsapp_main'):
    """
    Fetch a real-time live WhatsApp QR code from Evolution API.
    """
    import urllib.request
    try:
        # Check if instance exists or create it
        status_info = get_evolution_instance_status(instance_name)
        if status_info.get('connection_status') == 'unknown':
            # Try to create instance
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
                "qrcode": qrcode_data,
                "code": code,
                "pairing_code": pairing_code,
                "connection_status": data.get('status') or data.get('instance', {}).get('status', 'connecting')
            }
    except Exception as e:
        logger.error(f"[EvolutionAPI] Error fetching QR code: {e}", exc_info=True)
        return {"ok": False, "error": f"فشل جلب كود QR من Evolution API: {str(e)}"}


def create_channel_inbox(data, account_id=2, assistant_id=1):
    """
    Create a new inbox across any supported channel:
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
    channel_type = data.get('channel_type')
    enable_ai = data.get('enable_ai', True)

    try:
        inbox_id = None

        if channel_type == 'whatsapp_cloud':
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
                    "widget_color": data.get('widget_color', '#1f93ff'),
                    "welcome_title": data.get('welcome_title', 'مرحباً بك!'),
                    "welcome_tagline": data.get('welcome_tagline', 'كيف يمكننا مساعدتك اليوم؟')
                }
            }
            res = _post_chatwoot_inbox(payload, account_id)
            if not res.get('id'):
                return False, res.get('message') or "فشل إنشاء ودجت الموقع"
            inbox_id = res['id']

        elif channel_type == 'facebook':
            # Create Facebook Page Channel directly
            page_id = data.get('page_id')
            page_token = data.get('page_access_token')
            user_token = data.get('user_access_token') or page_token
            name = data.get('name') or f"Facebook ({page_id})"

            conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO channel_facebook_pages (page_id, user_access_token, page_access_token, account_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (page_id, account_id) DO UPDATE SET page_access_token = EXCLUDED.page_access_token
                RETURNING id
            """, (page_id, user_token, page_token, account_id))
            channel_id = cur.fetchone()[0]

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

            conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO channel_instagram (instagram_id, access_token, expires_at, account_id, created_at, updated_at)
                VALUES (%s, %s, NOW() + INTERVAL '60 days', %s, NOW(), NOW())
                ON CONFLICT (instagram_id) DO UPDATE SET access_token = EXCLUDED.access_token
                RETURNING id
            """, (instagram_id, access_token, account_id))
            channel_id = cur.fetchone()[0]

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

        # If enable_ai is checked, auto-link to Captain AI
        if inbox_id and enable_ai:
            toggle_channel_ai(inbox_id, enable=True, assistant_id=assistant_id)

        return True, "تم ربط القناة وتفعيلها بنجاح!"
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error creating channel: {e}", exc_info=True)
        return False, f"حدث خطأ أثناء ربط القناة: {str(e)}"


def _post_chatwoot_inbox(payload, account_id=2):
    import urllib.request
    url = f"{CHATWOOT_INTERNAL_API}/inboxes"
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

