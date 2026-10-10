"""
Service for Crafting and Dispatching WhatsApp Campaign Messages.
Integrates Gemini (gemini-2.5-flash) for personalized message generation,
Evolution API for sending, and CRM memory synchronization.
"""
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from django.conf import settings
from crm.models import OutboundCampaign, CampaignContact, OmnichannelMessage, CustomerMemory
from crm.services.evolution_client import send_whatsapp_message, get_connection_status
from agents.models import SystemSetting
from crm.inngest_jobs import broadcast_campaign_update

logger = logging.getLogger(__name__)

WHATSAPP_CAMPAIGN_SYSTEM_PROMPT = """أنت مسؤول تسويق وخدمة عملاء ذكي ومحترف عبر الواتساب لمنشأة أعمال مرموقة.
مهمتك صياغة رسالة واتساب شخصية، احترافية، ودودة، وموجهة للعميل المستهدف مباشرةً بناءً على سيناريو الحملة ومعلومات العميل.

تعليمات الصياغة:
1. خاطب العميل باسمه الكريم إن توفر ({customer_name}).
2. اجعل الرسالة موجزة وواضحة بدون حشو غير ضروري، وتناسب بيئة الواتساب التفاعلية.
3. التزم تماماً بهدف وسيناريو الحملة ومعلومات العرض أو المتابعة.
4. إذا تضمنت التعليمات أي تفاصيل أو روابط أو أرقام، اذكرها بدقة.
5. لا تضع أي شروحات، ولا مقدمات مثل "إليك الرسالة:"، بل أعد نص الرسالة النهائي الجاهز للإرسال فقط.
"""


def generate_personalized_whatsapp_message(campaign: OutboundCampaign, contact: CampaignContact) -> str:
    """
    Formulates a personalized WhatsApp message for a campaign contact using Gemini,
    with template variable fallback and context awareness.
    """
    raw_prompt = (campaign.whatsapp_prompt or campaign.call_prompt or "").strip()
    c_name = contact.customer_name or "عزيزي العميل"

    # 1. Fast template variable substitution if user used {name}, {customer_name}, etc.
    replacements = {
        "{name}": c_name,
        "{customer_name}": c_name,
        "{phone}": contact.phone_number,
        "{phone_number}": contact.phone_number,
    }
    if contact.attributes and isinstance(contact.attributes, dict):
        for k, v in contact.attributes.items():
            replacements[f"{{{k}}}"] = str(v)

    substituted_prompt = raw_prompt
    for placeholder, val in replacements.items():
        substituted_prompt = substituted_prompt.replace(placeholder, val)

    # 2. Try Gemini 2.5 Flash for smart formulation
    api_key = SystemSetting.get_gemini_api_key()
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            # Determine call state context
            call_context = ""
            if contact.call_status in ['no_answer', 'busy', 'failed']:
                call_context = "ملاحظة سياقية: لقد حاولنا الاتصال بالعميل هاتفياً سابقاً ولم يتم الرد، لذلك نرسل له عبر الواتساب لمتابعته بلطف واعتذار لطيف."
            elif contact.call_status == 'answered':
                call_context = f"ملاحظة سياقية: تم التواصل مع العميل هاتفياً بنجاح مسبقاً. ملخص المكالمة: {contact.call_summary or 'تمت المكالمة بنجاح'}. نرسل له الآن متابعة وتفاصيل تلخيصية."
            elif campaign.channel == 'whatsapp':
                call_context = "ملاحظة سياقية: هذه رسالة تسويقية/تواصل أولية عبر الواتساب."

            attrs_str = ""
            if contact.attributes and isinstance(contact.attributes, dict):
                attrs_str = "\nبيانات إضافية عن العميل: " + json.dumps(contact.attributes, ensure_ascii=False)

            user_content = (
                f"اسم العميل: {c_name}\n"
                f"رقم الهاتف: {contact.phone_number}"
                f"{attrs_str}\n"
                f"اسم الحملة: {campaign.name}\n"
                f"توجيهات ورسالة الحملة المحددة: {substituted_prompt or 'رسالة ترحيبية وتعريفية بالخدمة'}\n"
                f"{call_context}\n\n"
                f"المطلوب: قم بصياغة نص رسالة الواتساب النهائية الموجهة للعميل الآن."
            )

            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_content,
                config={
                    'system_instruction': WHATSAPP_CAMPAIGN_SYSTEM_PROMPT,
                    'temperature': 0.7,
                }
            )
            ai_text = resp.text.strip()
            if ai_text:
                return ai_text
        except Exception as e:
            logger.warning(f"Failed to generate WhatsApp message with Gemini: {e}")

    # 3. Robust Fallback if Gemini is not available or fails
    if substituted_prompt:
        return substituted_prompt

    if contact.call_status in ['no_answer', 'busy', 'failed']:
        return f"مرحباً {c_name}، حاولنا التواصل معكم هاتفياً بخصوص {campaign.name} وتعذر الوصول إليكم. يسعدنا تواصلكم معنا عبر الواتساب لأي استفسار أو مساعدة."

    return f"مرحباً {c_name}، يسعدنا تواصلنا معكم بخصوص {campaign.name}. كيف يمكننا مساعدتك اليوم؟"


def send_campaign_contact_whatsapp(contact_id: int) -> dict:
    """
    Sends a personalized WhatsApp message for a campaign contact.
    Updates CampaignContact, logs OmnichannelMessage, updates CustomerMemory,
    and updates campaign metrics.
    """
    try:
        contact = CampaignContact.objects.select_related('campaign', 'campaign__user').get(id=contact_id)
        campaign = contact.campaign

        if campaign.status in ['paused', 'completed']:
            logger.info(f"Campaign #{campaign.id} is {campaign.status}. Skipping WhatsApp for contact #{contact.id}.")
            return {"status": "skipped", "reason": f"Campaign is {campaign.status}"}

        # Check if already sent successfully to prevent double-messaging
        if contact.whatsapp_status in ['sent', 'delivered', 'replied']:
            logger.info(f"Contact #{contact.id} already received WhatsApp. Skipping.")
            return {"status": "already_sent", "contact_id": contact.id}

        user = campaign.user
        instance_name = f"user_{user.id}"

        # Check Evolution API instance connection
        conn_status = get_connection_status(instance_name)
        if not conn_status.get("connected") and conn_status.get("state") != "open":
            contact.whatsapp_status = 'failed'
            contact.whatsapp_message_text = "تعذر الإرسال: حساب الواتساب غير متصل في لوحة التحكم (Evolution API)."
            contact.save(update_fields=['whatsapp_status', 'whatsapp_message_text', 'updated_at'])
            campaign.update_metrics()
            broadcast_campaign_update(campaign.id, "contact_whatsapp_failed", {
                **contact.to_dict(),
                "error": "WhatsApp instance is not connected"
            })
            return {"status": "error", "code": "whatsapp_not_connected", "message": "WhatsApp instance is not connected"}

        contact.whatsapp_status = 'in_progress'
        contact.save(update_fields=['whatsapp_status', 'updated_at'])

        # Generate message
        msg_text = generate_personalized_whatsapp_message(campaign, contact)

        # Dispatch via Evolution API
        send_res = send_whatsapp_message(contact.phone_number, msg_text, instance_name=instance_name)

        if send_res.get("ok"):
            now_dt = datetime.now(timezone.utc)
            contact.whatsapp_status = 'sent'
            contact.whatsapp_message_text = msg_text
            contact.whatsapp_sent_at = now_dt
            if contact.interest_level == 'uncontacted':
                contact.interest_level = 'warm'
            contact.save(update_fields=['whatsapp_status', 'whatsapp_message_text', 'whatsapp_sent_at', 'interest_level', 'updated_at'])

            # Log OmnichannelMessage
            OmnichannelMessage.objects.create(
                user=user,
                phone_number=contact.phone_number,
                customer_name=contact.customer_name or "",
                channel="whatsapp",
                direction="outbound_ai",
                message_text=msg_text,
                metadata={
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "contact_id": contact.id,
                    "is_campaign": True,
                    "send_result": send_res
                }
            )

            # Sync CustomerMemory
            mem, _ = CustomerMemory.objects.get_or_create(
                user=user,
                phone_number=contact.phone_number,
                defaults={"customer_name": contact.customer_name or ""}
            )
            wm = mem.whatsapp_memory or {}
            wm["last_interaction_at"] = now_dt.isoformat()
            wm["last_sent_message"] = msg_text
            msgs = wm.get("last_messages", [])
            msgs.append({
                "sender": "ai_campaign",
                "text": msg_text,
                "time": now_dt.strftime("%Y-%m-%d %H:%M")
            })
            wm["last_messages"] = msgs[-20:]
            mem.whatsapp_memory = wm
            if not mem.customer_name and contact.customer_name:
                mem.customer_name = contact.customer_name
            mem.save()

            campaign.update_metrics()
            broadcast_campaign_update(campaign.id, "contact_whatsapp_sent", contact.to_dict())
            logger.info(f"Successfully sent campaign WhatsApp message to contact #{contact.id} ({contact.phone_number}).")
            return {"status": "success", "contact_id": contact.id, "message_text": msg_text}
        else:
            contact.whatsapp_status = 'failed'
            err_msg = send_res.get("error") or "فشل تسليم الرسالة عبر مزود الواتساب"
            contact.whatsapp_message_text = f"فشل الإرسال: {err_msg}"
            contact.save(update_fields=['whatsapp_status', 'whatsapp_message_text', 'updated_at'])
            campaign.update_metrics()
            broadcast_campaign_update(campaign.id, "contact_whatsapp_failed", {
                **contact.to_dict(),
                "error": err_msg
            })
            logger.warning(f"Failed to send campaign WhatsApp message to contact #{contact.id}: {err_msg}")
            return {"status": "error", "error": err_msg}

    except Exception as e:
        logger.exception(f"Unexpected error in send_campaign_contact_whatsapp for contact #{contact_id}: {e}")
        return {"status": "error", "message": str(e)}
