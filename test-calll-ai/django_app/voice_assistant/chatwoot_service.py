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


def generate_chatwoot_sso_url(user=None, account_id=2, locale=None):
    """
    Generate a direct SSO login link for Chatwoot that logs the user in
    silently without asking for credentials, using Chatwoot's Redis Alfred SSO token.
    Supports setting the user's and account's active locale ('ar' or 'en').
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

        if not chatwoot_user:
            conn.close()
            logger.warning("[ChatwootSSO] No Chatwoot user found in database.")
            return f"{CHATWOOT_BASE_URL}/app/accounts/{account_id}"

        user_id, email = chatwoot_user[0], chatwoot_user[1]

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
        if norm_locale:
            redirect_target += f"?locale={norm_locale}"

        sso_url = f"{CHATWOOT_BASE_URL}/app/login?email={encoded_email}&sso_auth_token={token}&redirect_url={urllib.parse.quote(redirect_target)}"
        logger.info(f"[ChatwootSSO] Generated silent SSO link for user {email} (ID {user_id}) [locale: {norm_locale}]")
        return sso_url
    except Exception as e:
        logger.error(f"[ChatwootSSO] Error generating SSO URL: {e}", exc_info=True)
        return f"{CHATWOOT_BASE_URL}/app/accounts/{account_id}"


def set_chatwoot_user_locale(user=None, account_id=2, locale='ar'):
    """
    Update Chatwoot user's ui_settings.locale and account.locale,
    and generate a fresh SSO URL matching the language.
    """
    norm_locale = 'en' if str(locale).lower().startswith('en') else 'ar'
    sso_url = generate_chatwoot_sso_url(user=user, account_id=account_id, locale=norm_locale)
    return {
        "status": "success",
        "locale": norm_locale,
        "sso_url": sso_url
    }


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
    grouped by platform, and whether Captain AI auto-reply is active.
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
            details = {
                "id": ibx['id'],
                "name": ibx['name'],
                "channel_type": c_type,
                "platform": "api",
                "is_captain_enabled": ibx['is_captain_enabled'],
                "created_at": ibx['created_at'].strftime("%Y-%m-%d %H:%M") if ibx.get('created_at') else "",
                "status": "connected",
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
            "api": []
        }

        for ch in channels_list:
            plt = ch.get('platform', 'api')
            if plt in grouped:
                grouped[plt].append(ch)
            else:
                grouped['api'].append(ch)

        # Primary Evolution status for fallback
        evolution_status = get_evolution_instance_status('whatsapp_main')

        return {
            "ok": True,
            "channels": channels_list,
            "grouped": grouped,
            "evolution": evolution_status,
            "evolution_instances": list(evolution_instances_map.values())
        }
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error listing channels: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "channels": [], "grouped": {}}


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


def update_channel_inbox(inbox_id, data, account_id=2, assistant_id=1):
    """
    Update channel inbox details (name, AI toggle, etc.).
    """
    try:
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor()

        new_name = data.get('name')
        if new_name:
            cur.execute("""
                UPDATE inboxes
                SET name = %s, updated_at = NOW()
                WHERE id = %s AND account_id = %s
            """, (new_name.strip(), inbox_id, account_id))

        if 'enable_ai' in data:
            enable = bool(data.get('enable_ai'))
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
        return True, "تم تحديث بيانات القناة بنجاح"
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error updating inbox {inbox_id}: {e}", exc_info=True)
        return False, f"فشل تحديث القناة: {str(e)}"


def delete_channel_inbox(inbox_id, account_id=2):
    """
    Delete an inbox from Chatwoot and its underlying Evolution instance if applicable.
    """
    import urllib.request
    try:
        # Check if this inbox has an Evolution WhatsApp instance
        instance_to_delete = None
        conn = psycopg2.connect(**CHATWOOT_DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT channel_id, channel_type FROM inboxes WHERE id = %s AND account_id = %s", (inbox_id, account_id))
        ibx = cur.fetchone()
        if ibx and ibx['channel_type'] == 'Channel::Api':
            cur.execute("SELECT webhook_url FROM channel_api WHERE id = %s", (ibx['channel_id'],))
            ch_api = cur.fetchone()
            if ch_api and ch_api.get('webhook_url') and '/chatwoot/webhook/' in ch_api['webhook_url']:
                instance_to_delete = ch_api['webhook_url'].split('/chatwoot/webhook/')[-1].strip('/')

        # Clean up captain_inboxes
        cur.execute("DELETE FROM captain_inboxes WHERE inbox_id = %s", (inbox_id,))
        cur.execute("DELETE FROM inboxes WHERE id = %s AND account_id = %s", (inbox_id, account_id))
        conn.commit()
        conn.close()

        # Delete Evolution API instance if applicable
        if instance_to_delete:
            try:
                del_url = f"{EVOLUTION_API_URL}/instance/delete/{instance_to_delete}"
                req = urllib.request.Request(del_url, headers={"apikey": EVOLUTION_API_KEY}, method="DELETE")
                urllib.request.urlopen(req, timeout=5)
                logger.info(f"[EvolutionAPI] Deleted instance {instance_to_delete}")
            except Exception as ev_err:
                logger.warning(f"[EvolutionAPI] Warning deleting instance {instance_to_delete}: {ev_err}")

        # Also try via Chatwoot API for complete internal cache cleanup
        try:
            url = f"{CHATWOOT_INTERNAL_API}/inboxes/{inbox_id}"
            req = urllib.request.Request(
                url,
                headers={
                    "api_access_token": CHATWOOT_API_TOKEN,
                    "X-Forwarded-Proto": "https"
                },
                method="DELETE"
            )
            urllib.request.urlopen(req, timeout=4)
        except Exception:
            pass

        return True, "تم حذف القناة نهائياً بنجاح"
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

            # Generate sanitized unique instance name for Evolution
            clean_token = secrets.token_hex(4)
            safe_slug = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())[:15].strip('_') or "wa"
            instance_name = f"{safe_slug}_{clean_token}"

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

        msg = "تم ربط القناة بنجاح!"
        if channel_type == 'whatsapp_qr':
            msg = f"تم إنشاء حساب واتساب جديد ({instance_name}) وجاري تجهيز كود QR للمسح!"

        return True, msg, {"inbox_id": inbox_id, "instance_name": instance_name}
    except Exception as e:
        logger.error(f"[ChatwootChannels] Error creating channel: {e}", exc_info=True)
        return False, f"حدث خطأ أثناء ربط القناة: {str(e)}", {}


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





