import logging
import os
import requests
from typing import Dict, Any, Optional

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
            return {"status": "success", "ok": True, "base64": base64_qr, "pairing_code": pairing_code, "count": count}
        elif resp.status_code == 404:
            create_or_get_instance(instance_name)
            # Retry once
            r2 = requests.get(url, headers=get_headers(), timeout=10.0)
            if r2.status_code in (200, 201):
                d2 = r2.json()
                return {"status": "success", "ok": True, "base64": d2.get("base64", ""), "pairing_code": d2.get("pairingCode", "")}
        return {"status": "error", "ok": False, "error": resp.text}
    except Exception as e:
        logger.error(f"Error fetching QR code: {e}")
        return {"status": "error", "ok": False, "error": str(e)}


def send_whatsapp_message(phone_number: str, text: str, instance_name: str = DEFAULT_INSTANCE_NAME) -> Dict[str, Any]:
    """Send text message to WhatsApp recipient."""
    clean_phone = "".join(ch for ch in phone_number if ch.isdigit())
    if not clean_phone:
        return {"status": "error", "ok": False, "error": "Invalid phone number"}

    # Check connection state first
    stat = get_connection_status(instance_name)
    if not stat.get("connected") and stat.get("state") != "open":
        logger.info(f"Skipping Evolution send to {clean_phone}: instance '{instance_name}' is not connected (state: {stat.get('state')}).")
        return {"status": "not_connected", "ok": False, "error": f"WhatsApp instance '{instance_name}' is not paired. Please scan QR code in dashboard."}

    url = f"{EVOLUTION_API_URL}/message/sendText/{instance_name}"
    payload = {
        "number": clean_phone,
        "text": text,
        "delay": 1200,
        "linkPreview": True
    }
    try:
        resp = requests.post(url, json=payload, headers=get_headers(), timeout=6.0)
        if resp.status_code in (200, 201):
            return {"status": "success", "ok": True, "data": resp.json()}
        logger.error(f"Failed to send WhatsApp message to {clean_phone}: ({resp.status_code}) {resp.text}")
        return {"status": "error", "ok": False, "error": resp.text, "status_code": resp.status_code}
    except Exception as e:
        logger.error(f"Exception sending WhatsApp message: {e}")
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
