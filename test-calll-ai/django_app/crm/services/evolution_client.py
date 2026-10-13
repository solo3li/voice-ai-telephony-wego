import logging
import os
import requests
from typing import Dict, Any, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://evolution_api:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "evolution_secret_key_123")
DEFAULT_INSTANCE_NAME = os.getenv("EVOLUTION_DEFAULT_INSTANCE", "default_workspace")


def get_headers() -> Dict[str, str]:
    return {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }


def create_or_get_instance(instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Ensure the Evolution API instance exists for the tenant."""
    url = f"{EVOLUTION_API_URL}/instance/create"
    payload = {
        "instanceName": instance_name,
        "token": f"token_{instance_name}",
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS"
    }
    try:
        resp = requests.post(url, json=payload, headers=get_headers(), timeout=10.0)
        data = resp.json() if resp.status_code in (200, 201) else {}
        return {"ok": True, "data": data}
    except Exception as e:
        logger.warning(f"Evolution API create_instance notice: {e}")
        return {"ok": False, "error": str(e)}


def get_connection_status(instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Check connection state (open, connecting, close)."""
    url = f"{EVOLUTION_API_URL}/instance/connectionState/{instance_name}"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=6.0)
        if resp.status_code == 200:
            data = resp.json()
            state = data.get("instance", {}).get("state", "close")
            connected = (state == "open")
            return {"status": "success", "ok": True, "state": state, "connected": connected, "data": data}
        elif resp.status_code == 404:
            create_or_get_instance(instance_name)
            return {"status": "success", "ok": True, "state": "close", "connected": False, "data": {}}
        return {"status": "error", "ok": False, "state": "close", "connected": False, "error": resp.text}
    except Exception as e:
        logger.error(f"Error fetching connection state for {instance_name}: {e}")
        return {"status": "error", "ok": False, "state": "close", "connected": False, "error": str(e)}


def delete_instance(instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Delete an instance from Evolution API to clear dead/stale sessions."""
    url = f"{EVOLUTION_API_URL}/instance/delete/{instance_name}"
    try:
        resp = requests.delete(url, headers=get_headers(), timeout=10.0)
        return {"ok": resp.status_code == 200}
    except Exception as e:
        logger.warning(f"Error deleting instance {instance_name}: {e}")
        return {"ok": False, "error": str(e)}


def get_qr_code(instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Fetch base64 QR code to pair WhatsApp."""
    url = f"{EVOLUTION_API_URL}/instance/connect/{instance_name}"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10.0)
        if resp.status_code in (200, 201):
            data = resp.json()
            base64_qr = data.get("base64") or data.get("qrcode", {}).get("base64") or ""
            pairing_code = data.get("pairingCode") or ""
            count = data.get("count", 0)
            if base64_qr or pairing_code:
                return {"status": "success", "ok": True, "base64": base64_qr, "pairing_code": pairing_code, "count": count}

        # If instance not found or stale session without QR, recreate instance cleanly
        delete_instance(instance_name)
        create_or_get_instance(instance_name)
        r2 = requests.get(url, headers=get_headers(), timeout=10.0)
        if r2.status_code in (200, 201):
            d2 = r2.json()
            return {
                "status": "success",
                "ok": True,
                "base64": d2.get("base64") or d2.get("qrcode", {}).get("base64") or "",
                "pairing_code": d2.get("pairingCode", ""),
                "count": d2.get("count", 0)
            }
        return {"status": "error", "ok": False, "error": r2.text}
    except Exception as e:
        logger.error(f"Error fetching QR code: {e}")
        return {"status": "error", "ok": False, "error": str(e)}


def format_whatsapp_number(raw_phone: str) -> str:
    """Format and normalize phone number for WhatsApp / Evolution API with country code."""
    phone = str(raw_phone or "").strip()
    if not phone:
        return ""
    if "@" in phone:
        return phone.replace("+", "")

    import re
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return ""

    # Strip leading 00
    if digits.startswith("00"):
        digits = digits[2:]

    # Egyptian local mobile numbers: 010, 011, 012, 015 (11 digits)
    if digits.startswith("01") and len(digits) == 11:
        digits = "20" + digits[1:]
    # Egyptian numbers typed as 2001... (13 digits with extra 0)
    elif digits.startswith("2001") and len(digits) == 13:
        digits = "20" + digits[3:]
    # Saudi local mobile numbers: 05... (10 digits)
    elif digits.startswith("05") and len(digits) == 10:
        digits = "966" + digits[1:]
    # Saudi numbers typed as 96605... (13 digits with extra 0)
    elif digits.startswith("96605") and len(digits) == 13:
        digits = "966" + digits[4:]

    return digits


def send_whatsapp_message(phone_number: str, text: str, instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Send text message to WhatsApp recipient (supports both standard numbers and @lid/@g.us JIDs)."""
    target_number = format_whatsapp_number(phone_number)
    if not target_number:
        return {"status": "error", "ok": False, "error": "Invalid phone number"}

    # Check connection state first
    stat = get_connection_status(instance_name)
    if not stat.get("connected") and stat.get("state") != "open":
        logger.info(f"Skipping Evolution send to {target_number}: instance '{instance_name}' is not connected (state: {stat.get('state')}).")
        return {"status": "not_connected", "ok": False, "error": f"WhatsApp instance '{instance_name}' is not paired. Please scan QR code in dashboard."}

    url = f"{EVOLUTION_API_URL}/message/sendText/{instance_name}"
    payload = {
        "number": target_number,
        "text": text,
        "delay": 1200,
        "linkPreview": True
    }
    try:
        resp = requests.post(url, json=payload, headers=get_headers(), timeout=6.0)
        if resp.status_code in (200, 201):
            return {"status": "success", "ok": True, "data": resp.json()}
        logger.error(f"Failed to send WhatsApp message to {target_number}: ({resp.status_code}) {resp.text}")
        return {"status": "error", "ok": False, "error": resp.text, "status_code": resp.status_code}
    except Exception as e:
        logger.error(f"Exception sending WhatsApp message: {e}")
        return {"status": "error", "ok": False, "error": str(e)}


def send_whatsapp_presence(phone_number: str, presence: str = "composing", delay_ms: int = 1200, instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """
    Send chat presence status (e.g. 'composing' for typing indicator) to Evolution API.
    """
    target_number = format_whatsapp_number(phone_number)
    if not target_number:
        return {"status": "error", "ok": False, "error": "Invalid phone number"}

    url = f"{EVOLUTION_API_URL}/chat/sendPresence/{instance_name}"
    payload = {
        "number": target_number,
        "presence": presence,
        "delay": delay_ms
    }
    try:
        resp = requests.post(url, json=payload, headers=get_headers(), timeout=3.0)
        if resp.status_code in (200, 201):
            return {"status": "success", "ok": True, "data": resp.json() if resp.text else {}}
        return {"status": "error", "ok": False, "error": resp.text, "status_code": resp.status_code}
    except Exception as e:
        logger.debug(f"Exception sending WhatsApp presence: {e}")
        return {"status": "error", "ok": False, "error": str(e)}


def logout_instance(instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Disconnect and log out the WhatsApp session."""
    url = f"{EVOLUTION_API_URL}/instance/logout/{instance_name}"
    try:
        resp = requests.delete(url, headers=get_headers(), timeout=10.0)
        return {"status": "success", "ok": True, "data": resp.text}
    except Exception as e:
        logger.error(f"Error logging out instance: {e}")
        return {"ok": False, "error": str(e)}


def configure_instance_webhook(webhook_url: str, instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Configure Evolution API to forward inbound messages to Django webhook."""
    url = f"{EVOLUTION_API_URL}/webhook/set/{instance_name}"
    payload = {
        "webhook": {
            "enabled": True,
            "url": webhook_url,
            "byEvents": False,
            "base64": False,
            "events": [
                "MESSAGES_UPSERT",
                "CONNECTION_UPDATE"
            ]
        }
    }
    try:
        resp = requests.post(url, json=payload, headers=get_headers(), timeout=8.0)
        return {"ok": resp.status_code in (200, 201), "data": resp.text}
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return {"ok": False, "error": str(e)}


def check_group_can_send(group_jid: str, instance_name: str = DEFAULT_INSTANCE_NAME) -> tuple:
    """
    Check if this WhatsApp instance has permission to send messages into a group.
    Returns (can_send: bool, reason: str).
    """
    if not group_jid or not group_jid.endswith('@g.us'):
        return True, ""

    from django.core.cache import cache
    cache_key = f"wa_group_can_send_{instance_name}_{group_jid}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        # 1. Fetch instance owner JID
        inst_url = f"{EVOLUTION_API_URL}/instance/fetchInstances?instanceName={instance_name}"
        inst_resp = requests.get(inst_url, headers=get_headers(), timeout=4.0)
        owner_jid = ""
        if inst_resp.status_code == 200:
            data = inst_resp.json()
            if data and isinstance(data, list):
                owner_jid = data[0].get("ownerJid", "")

        # 2. Fetch group metadata
        grp_url = f"{EVOLUTION_API_URL}/group/findGroupInfos/{instance_name}?groupJid={group_jid}"
        grp_resp = requests.get(grp_url, headers=get_headers(), timeout=4.0)
        if grp_resp.status_code != 200:
            res = (False, "تعذر التحقق من إعدادات المجموعة أو تم الخروج منها")
            cache.set(cache_key, res, timeout=300)
            return res

        gd = grp_resp.json()
        is_announce = gd.get("announce", False)
        if not is_announce:
            res = (True, "")
            cache.set(cache_key, res, timeout=300)
            return res

        # Announcement group: Only admins can send
        participants = gd.get("participants", [])
        owner_clean = owner_jid.split("@")[0] if owner_jid else ""
        is_admin = False
        if owner_clean:
            for p in participants:
                pid = p.get("id", "")
                if owner_clean and owner_clean in pid:
                    if p.get("admin") in ("admin", "superadmin"):
                        is_admin = True
                        break

        if is_admin:
            res = (True, "")
        else:
            res = (False, "المشرفون فقط هم من يستطيعون إرسال الرسائل في هذه المجموعة")

        cache.set(cache_key, res, timeout=300)
        return res
    except Exception as e:
        logger.warning(f"Error checking group send status for {group_jid}: {e}")
        return True, ""


def fetch_profile_picture_url(number: str, instance_name: str = DEFAULT_INSTANCE_NAME) -> Optional[str]:
    """Fetch live profile picture URL from WhatsApp for a contact or group."""
    if not number:
        return None
    cache_key = f"wa_profile_pic_{instance_name}_{number}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    url = f"{EVOLUTION_API_URL}/chat/fetchProfilePictureUrl/{instance_name}"
    payload = {"number": number}
    try:
        resp = requests.post(url, json=payload, headers=get_headers(), timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            pic_url = data.get("profilePictureUrl") or ""
            cache.set(cache_key, pic_url, timeout=3600)
            return pic_url or None
    except Exception as e:
        logger.warning(f"Error fetching profile picture for {number}: {e}")
    cache.set(cache_key, "", timeout=300)
    return None

