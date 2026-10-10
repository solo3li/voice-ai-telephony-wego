import os
import json
import logging
import datetime
import psycopg2
from django.db import transaction
from django.contrib.auth.models import User
from crm.models import OmnichannelMessage, CustomerMemory

logger = logging.getLogger(__name__)


def extract_message_text(msg_obj, msg_type: str) -> str:
    """Extract clean readable text or media label from WhatsApp message JSON."""
    if not isinstance(msg_obj, dict):
        return ""

    text = (
        msg_obj.get("conversation")
        or msg_obj.get("extendedTextMessage", {}).get("text")
        or msg_obj.get("imageMessage", {}).get("caption")
        or msg_obj.get("videoMessage", {}).get("caption")
        or msg_obj.get("documentMessage", {}).get("caption")
        or msg_obj.get("documentWithCaptionMessage", {}).get("message", {}).get("documentMessage", {}).get("caption")
    )
    if text:
        return text.strip()

    # Fallback to descriptive media labels
    if msg_type == "imageMessage":
        return "📷 صورة"
    elif msg_type in ("audioMessage", "voiceMessage"):
        return "🎤 رسالة صوتية"
    elif msg_type == "videoMessage":
        return "🎥 فيديو"
    elif msg_type == "stickerMessage":
        return "💟 ملصق (Sticker)"
    elif msg_type == "documentMessage":
        return "📄 مستند"
    elif msg_type == "contactMessage":
        return "👤 جهة اتصال"
    elif msg_type == "locationMessage":
        return "📍 موقع جغرافي"
    elif msg_type == "reactionMessage":
        reaction = msg_obj.get("reactionMessage", {}).get("text", "")
        return f"تفاعل: {reaction}" if reaction else "تفاعل"
    elif msg_type == "pollCreationMessage":
        return "📊 تصويت (استطلاع رأي)"
    
    return f"[{msg_type}]" if msg_type else ""


def normalize_jid_to_identifier(remote_jid: str) -> str:
    """
    Normalize WhatsApp JID to clean phone number or retain @lid / @g.us suffix.
    - 201108124794@s.whatsapp.net -> 201108124794
    - 143830351401098@lid -> 143830351401098@lid
    - 120363414016924957@g.us -> 120363414016924957@g.us
    """
    if not remote_jid:
        return ""
    remote_jid = remote_jid.strip()
    if remote_jid.endswith("@s.whatsapp.net"):
        return remote_jid.split("@")[0].replace("+", "")
    return remote_jid


def format_phone_display(phone_str: str, raw_jid: str = "") -> str:
    """Format phone number nicely (e.g. +20 101 943 1866)."""
    clean = "".join(ch for ch in (phone_str or "") if ch.isdigit())
    if clean.startswith("01") and len(clean) == 11:
        clean = "2" + clean  # Convert local 01X to international 201X
    if clean.startswith("20") and len(clean) >= 12:
        country = clean[:2]
        op = clean[2:5]
        p1 = clean[5:8]
        p2 = clean[8:]
        return f"+{country} {op} {p1} {p2}"
    elif len(clean) >= 10:
        return f"+{clean[:3]} {clean[3:6]} {clean[6:]}"
    elif clean:
        return f"+{clean}"
    
    if raw_jid and "@g.us" in raw_jid:
        return "👥 مجموعة واتساب"
    elif raw_jid and "@lid" in raw_jid:
        return "📱 حساب واتساب مباشر"
    return "📱 حساب واتساب"


def sync_whatsapp_data(user: User, clean_old: bool = True, max_messages_per_chat: int = 40) -> dict:
    """
    Sync all genuine WhatsApp chats and recent messages from evolution_db into Django CRM.
    
    Args:
        user: The Django User instance (tenant).
        clean_old: If True, purges previous mock/test messages for this user.
        max_messages_per_chat: Max number of recent messages to import per chat (default: 40).
        
    Returns:
        dict: Sync summary report with chat count and message count.
    """
    instance_name = f"user_{user.id}"
    logger.info(f"Starting real WhatsApp sync for user {user.username} (instance: {instance_name})...")

    db_host = os.getenv("POSTGRES_HOST", "voice_postgres")
    db_port = int(os.getenv("POSTGRES_PORT", "5432"))
    db_user = os.getenv("POSTGRES_USER", "voice_user")
    db_pass = os.getenv("POSTGRES_PASSWORD", "voice_password_123")
    db_name = os.getenv("EVOLUTION_DB_NAME", "evolution_db")

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
            connect_timeout=6
        )
    except Exception as e:
        logger.error(f"Failed to connect to evolution_db: {e}")
        return {
            "status": "error",
            "message": f"تعذر الاتصال بقاعدة بيانات الواتساب (evolution_db): {str(e)}"
        }

    try:
        cur = conn.cursor()

        # 1. Resolve instanceId
        cur.execute('SELECT id FROM "Instance" WHERE name = %s LIMIT 1;', (instance_name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {
                "status": "error",
                "message": f"لم يتم العثور على ربط واتساب برقم هاتفك للمستخدم {user.username} ({instance_name}). يرجى مسح رمز QR أولاً."
            }
        instance_id = row[0]

        # 2. Fetch Contact Names & Profiles
        cur.execute('''
            SELECT 
                c."remoteJid",
                COALESCE(NULLIF(c."pushName", ''), NULLIF(ch.name, ''), '') as contact_name,
                c."profilePicUrl"
            FROM "Contact" c
            FULL OUTER JOIN "Chat" ch ON ch."remoteJid" = c."remoteJid" AND ch."instanceId" = c."instanceId"
            WHERE COALESCE(c."instanceId", ch."instanceId") = %s;
        ''', (instance_id,))
        contact_map = {}
        for r_jid, c_name, pic_url in cur.fetchall():
            if r_jid:
                contact_map[r_jid] = {
                    "name": c_name or "",
                    "pic_url": pic_url or ""
                }

        # 2.5 Build reverse phone lookup from @s.whatsapp.net contacts
        cur.execute('''
            SELECT "remoteJid", "pushName"
            FROM "Contact"
            WHERE "instanceId" = %s
              AND "remoteJid" LIKE '%%@s.whatsapp.net'
              AND "pushName" IS NOT NULL AND "pushName" != '';
        ''', (instance_id,))
        phone_by_name = {}
        for r_jid, p_name in cur.fetchall():
            p_clean = r_jid.split('@')[0]
            nm = p_name.strip()
            phone_by_name[nm.lower()] = p_clean
            phone_by_name[nm] = p_clean

        known_aliases = {
            "201108124794": {"name": "أنا (ملاحظات شخصية)", "phone": "201108124794"},
            "172108650950843@lid": {"name": "أنا (جهاز مرتبط)", "phone": "201091121410"},
            "82120160620664@lid": {"name": "دعم CommPeak (VoIP)", "phone": ""},
            "81007378182162@lid": {"name": "عميل استفسار النماذج والتكلفة", "phone": ""},
            "85512832475186@lid": {"name": "عميل استفسار Gemini Pro", "phone": ""},
            "30460696637668@lid": {"name": "عميل استفسار Business SIP", "phone": ""},
            "120363419022376600@g.us": {"name": "Real estate استفسار", "phone": ""},
            "120363414016924957@g.us": {"name": "Student Housing – El Shorouk☀", "phone": ""},
            "0": {"name": "واتساب الرسمي", "phone": "0"},
        }

        # 3. Fetch latest messages per chat using SQL Window Function (last N messages)
        cur.execute('''
            WITH ranked_messages AS (
                SELECT 
                    m.id,
                    m.key->>'remoteJid' as remote_jid,
                    (m.key->>'fromMe')::boolean as from_me,
                    m.message,
                    m."pushName",
                    m."messageType",
                    m."messageTimestamp",
                    ROW_NUMBER() OVER (
                        PARTITION BY m.key->>'remoteJid' 
                        ORDER BY m."messageTimestamp" DESC
                    ) as rn
                FROM "Message" m
                WHERE m."instanceId" = %s
                  AND m.key->>'remoteJid' IS NOT NULL
                  AND m.key->>'remoteJid' != 'status@broadcast'
            )
            SELECT 
                id,
                remote_jid,
                from_me,
                message,
                "pushName",
                "messageType",
                "messageTimestamp"
            FROM ranked_messages
            WHERE rn <= %s
            ORDER BY remote_jid, "messageTimestamp" ASC;
        ''', (instance_id, max_messages_per_chat))

        raw_messages = cur.fetchall()
        conn.close()

        if not raw_messages:
            return {
                "status": "warning",
                "chats_count": 0,
                "messages_count": 0,
                "message": "تم فحص حساب الواتساب ولكن لا توجد رسائل مسجلة بعد في قاعدة بيانات واتساب."
            }

        # 3.5 Pre-load existing CustomerMemory names for this user as smart fallback
        existing_memories = {
            m.phone_number: m.customer_name 
            for m in CustomerMemory.objects.filter(user=user) 
            if m.customer_name
        }

        # 4. Process and Group Messages by Chat
        chats_data = {}  # identifier -> list of message dicts
        for m_id, r_jid, from_me, msg_content, push_name, msg_type, msg_ts in raw_messages:
            if not r_jid:
                continue

            identifier = normalize_jid_to_identifier(r_jid)
            if not identifier:
                continue

            # Determine best contact name and real phone
            alias = known_aliases.get(identifier) or known_aliases.get(r_jid)
            if alias:
                name = alias["name"]
                real_phone = alias.get("phone", "")
            else:
                info = contact_map.get(r_jid, {})
                name = info.get("name") or (push_name if not from_me else "") or ""
                if not name:
                    clean_digits = "".join(ch for ch in identifier if ch.isdigit())
                    name = (
                        existing_memories.get(identifier) 
                        or existing_memories.get(clean_digits) 
                        or existing_memories.get(f"+{clean_digits}")
                        or ""
                    )
                if not name:
                    if r_jid.endswith("@g.us"):
                        name = "مجموعة واتساب"
                    else:
                        name = "عميل واتساب جديد"

                real_phone = phone_by_name.get(name.lower().strip()) or phone_by_name.get(name.strip()) or ""
                if not real_phone and "@" not in identifier and identifier.isdigit():
                    real_phone = identifier

            text = extract_message_text(msg_content, msg_type)
            if not text:
                continue

            direction = "outbound_human" if from_me else "inbound"
            dt = datetime.datetime.fromtimestamp(msg_ts, tz=datetime.timezone.utc)

            if identifier not in chats_data:
                chats_data[identifier] = {
                    "raw_jid": r_jid,
                    "customer_name": name,
                    "real_phone": real_phone,
                    "messages": []
                }
            else:
                if name and chats_data[identifier]["customer_name"] in ("", "عميل واتساب جديد"):
                    chats_data[identifier]["customer_name"] = name
                if real_phone and not chats_data[identifier].get("real_phone"):
                    chats_data[identifier]["real_phone"] = real_phone

            chats_data[identifier]["messages"].append({
                "direction": direction,
                "text": text,
                "created_at": dt,
                "push_name": push_name or name or identifier
            })

        # 5. Save to Django Database within transaction
        with transaction.atomic():
            if clean_old:
                deleted_count, _ = OmnichannelMessage.objects.filter(user=user).delete()
                logger.info(f"Purged {deleted_count} previous mock messages for user {user.username}.")

            messages_to_create = []
            for identifier, c_info in chats_data.items():
                c_name = c_info["customer_name"]
                c_real_phone = c_info.get("real_phone", "")
                for msg in c_info["messages"]:
                    om_msg = OmnichannelMessage(
                        user=user,
                        phone_number=identifier,
                        customer_name=c_name,
                        channel="whatsapp",
                        direction=msg["direction"],
                        message_text=msg["text"],
                        is_followup=False,
                        followup_reason="whatsapp_sync",
                        metadata={"raw_jid": c_info["raw_jid"]}
                    )
                    om_msg.created_at = msg["created_at"]
                    messages_to_create.append(om_msg)

                # Initialize CustomerMemory with AI Autopilot enabled
                mem, _ = CustomerMemory.objects.get_or_create(
                    user=user,
                    phone_number=identifier,
                    defaults={"customer_name": c_name}
                )
                mem.customer_name = c_name
                prof = mem.permanent_profile or {}
                if c_real_phone:
                    prof["real_phone"] = c_real_phone
                prof["display_phone"] = format_phone_display(c_real_phone, identifier)
                mem.permanent_profile = prof

                wm = mem.whatsapp_memory or {}
                wm["ai_auto_reply_enabled"] = True  # AI active by default for all chats!
                
                # Update last interaction and last messages
                if c_info["messages"]:
                    last_msg = c_info["messages"][-1]
                    wm["last_interaction_at"] = last_msg["created_at"].isoformat()
                    # Last inbound text if available
                    inbound_msgs = [m["text"] for m in c_info["messages"] if m["direction"] == "inbound"]
                    if inbound_msgs:
                        wm["last_received_message"] = inbound_msgs[-1]
                    
                    # Store last 10 messages for prompt context
                    last_10 = []
                    for m in c_info["messages"][-10:]:
                        sender_role = "customer" if m["direction"] == "inbound" else "assistant"
                        last_10.append({
                            "sender": sender_role,
                            "text": m["text"],
                            "time": m["created_at"].strftime("%Y-%m-%d %H:%M")
                        })
                    wm["last_messages"] = last_10

                mem.whatsapp_memory = wm
                mem.save()

            # Bulk create messages
            OmnichannelMessage.objects.bulk_create(messages_to_create, batch_size=200)

        total_imported_msgs = len(messages_to_create)
        total_chats = len(chats_data)
        logger.info(f"Successfully synced {total_chats} chats with {total_imported_msgs} messages for {user.username}!")

        return {
            "status": "success",
            "chats_count": total_chats,
            "messages_count": total_imported_msgs,
            "message": f"تمت مزامنة {total_chats} محادثة حقيقية بالكامل و{total_imported_msgs} رسالة مباشرة من هاتفك بنجاح!"
        }

    except Exception as e:
        logger.error(f"Error during WhatsApp sync execution: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"حدث خطأ أثناء مزامنة محادثات الواتساب: {str(e)}"
        }
