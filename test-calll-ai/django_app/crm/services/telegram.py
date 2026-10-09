"""Telegram Bot Service for Instant Approval Gates and Customer Messaging."""
import logging
import requests
from typing import Dict, Any, Optional
from django.conf import settings
from django.contrib.auth.models import User
from agents.models import DigitalCoworkerConfig

logger = logging.getLogger(__name__)


def send_telegram_approval_message(
    bot_token: str,
    chat_id: str,
    title: str,
    description: str,
    approval_id: int,
    dashboard_url: str = ""
) -> Dict[str, Any]:
    """
    Send an interactive Telegram message with inline buttons [✅ موافقة] and [❌ رفض]
    plus a deep link to the Django dashboard for full review.
    """
    if not bot_token or not chat_id:
        return {"status": "skipped", "reason": "No telegram credentials"}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    text = (
        f"🚨 *طلب موافقة جديد من الموظف الذكي*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 *العنوان:* {title}\n"
        f"📝 *التفاصيل:* {description}\n"
        f"🔢 *رقم الطلب:* `#{approval_id}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"اختر إجراءك الفوري بالضغط أدناه:"
    )

    inline_keyboard = [
        [
            {"text": "✅ موافقة (Approve)", "callback_data": f"appr:{approval_id}"},
            {"text": "❌ رفض (Reject)", "callback_data": f"rejc:{approval_id}"}
        ]
    ]

    if dashboard_url:
        inline_keyboard.append([
            {"text": "🔍 فحص التقرير الكامل في اللوحة", "url": dashboard_url}
        ])

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": inline_keyboard
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            res_data = resp.json().get("result", {})
            msg_id = str(res_data.get("message_id", ""))
            logger.info(f"[Telegram Bot] Sent approval #{approval_id} to chat {chat_id}: msg_id={msg_id}")
            return {"status": "sent", "message_id": msg_id}
        else:
            logger.warning(f"[Telegram Bot] Telegram API error {resp.status_code}: {resp.text}")
            return {"status": "failed", "error": resp.text}
    except Exception as e:
        logger.error(f"[Telegram Bot] Failed to send telegram message: {e}")
        return {"status": "failed", "error": str(e)}


def update_telegram_message_status(
    bot_token: str,
    chat_id: str,
    message_id: str,
    original_text: str,
    decision_text: str
) -> bool:
    """Update message text in Telegram to reflect final decision and disable buttons."""
    if not bot_token or not chat_id or not message_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    new_text = f"{original_text}\n\n{decision_text}"
    
    payload = {
        "chat_id": chat_id,
        "message_id": int(message_id),
        "text": new_text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": []}  # Remove buttons after decision
    }

    try:
        resp = requests.post(url, json=payload, timeout=4)
        return resp.status_code == 200
    except Exception:
        return False
