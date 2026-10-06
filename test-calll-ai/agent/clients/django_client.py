import time
import json
from typing import Optional, Dict, Any, List
import requests
from config import DJANGO_API_URL, INTERNAL_API_KEY, logger
from .http_pool import get_http_session

# ==================== Bootstrap & Profile Parsers ====================

def parse_mcp_servers_from_bootstrap(bootstrap: dict) -> list:
    """Extract and format active MCP servers from bootstrap dictionary."""
    servers = bootstrap.get("mcp_servers", []) if bootstrap else []
    clean_servers = []
    for s in servers:
        if not s or not s.get("is_active", True):
            continue
        tools = s.get("cached_tools", [])
        if isinstance(tools, str):
            try:
                tools = json.loads(tools)
            except Exception:
                tools = []
        clean_servers.append({
            "server_url": s.get("server_url", ""),
            "auth_token": s.get("auth_token", ""),
            "tools": tools or [],
            "name": s.get("name", "خادم MCP")
        })
    return clean_servers

def parse_customer_memory_from_bootstrap(bootstrap: dict, caller_phone: str = "web_dashboard") -> dict:
    """Extract and format customer memory from bootstrap dictionary."""
    if not bootstrap:
        return {"phone_number": caller_phone, "permanent_profile": {}, "last_interaction_summary": "", "card_text": "", "total_calls_count": 0}

    mem = bootstrap.get("customer_memory", {})
    prof = mem.get("permanent_profile") or {}
    if isinstance(prof, str):
        try:
            prof = json.loads(prof)
        except Exception:
            prof = {}
    summary = mem.get("last_interaction_summary", "")

    parts = []
    if prof:
        items = []
        if prof.get("customer_name"):
            items.append(f"اسم العميل المفضل: {prof['customer_name']}")
        phone_val = caller_phone if caller_phone != 'web_dashboard' else prof.get("phone")
        if phone_val:
            items.append(f"الهاتف: {phone_val}")
        if prof.get("city") or prof.get("address"):
            items.append(f"العنوان/المدينة: {prof.get('city') or prof.get('address')}")
        if prof.get("preferences"):
            prefs = prof['preferences']
            if isinstance(prefs, list):
                prefs = "، ".join(str(p) for p in prefs)
            items.append(f"تفضيلات واهتمامات العميل: {prefs}")
        if prof.get("notes"):
            items.append(f"ملاحظات هامة: {prof['notes']}")
        if items:
            parts.append("البيانات الدائمة للعميل:\n- " + "\n- ".join(items))

    if summary:
        parts.append(f"الذاكرة اللحظية من آخر تواصل:\n{summary}")

    card_text = ""
    if parts:
        phone_label = f" ({caller_phone})" if caller_phone and caller_phone != 'web_dashboard' else ""
        card_text = f"ذاكرة وسياق العميل{phone_label} من المكالمات السابقة (استخدمها بذكاء وعفوية للتذكر والترحيب بالمتابعة):\n" + "\n\n".join(parts)

    return {
        "phone_number": caller_phone,
        "permanent_profile": prof,
        "last_interaction_summary": summary,
        "card_text": card_text,
        "total_calls_count": mem.get("total_calls_count", 0)
    }

def parse_active_profile_from_bootstrap(bootstrap: dict) -> dict:
    """Extract active profile from bootstrap dictionary with fallbacks."""
    default_profile = {
        "name": "نورهان - خدمة عملاء مصرية",
        "voice_name": "Aoede",
        "gender": "female",
        "language": "arabic",
        "dialect": "egyptian",
        "persona_role": "customer_support",
        "speaking_style": "friendly",
        "verbosity": "balanced",
        "welcome_message": "",
        "is_welcome_message_enabled": True,
        "custom_instructions": "",
        "off_topic_response": ""
    }
    if not bootstrap:
        return default_profile
    prof = bootstrap.get("profile")
    if prof and isinstance(prof, dict):
        return {
            "voice_name": prof.get("voice_name") or "Aoede",
            "gender": prof.get("gender") or "female",
            "language": prof.get("language") or "arabic",
            "dialect": prof.get("dialect") or "egyptian",
            "persona_role": prof.get("persona_role") or "customer_support",
            "speaking_style": prof.get("speaking_style") or "friendly",
            "verbosity": prof.get("verbosity") or "balanced",
            "welcome_message": prof.get("welcome_message") or "",
            "is_welcome_message_enabled": prof.get("is_welcome_message_enabled", True) if prof.get("is_welcome_message_enabled") is not None else True,
            "custom_instructions": prof.get("custom_instructions") or "",
            "off_topic_response": prof.get("off_topic_response") or "",
            "name": prof.get("name") or "المساعد"
        }
    return default_profile


# ==================== Bootstrap API ====================

async def fetch_agent_bootstrap_async(user_id: int, caller_phone: str = "web_dashboard") -> dict:
    """Fetch complete agent bootstrap bundle non-blockingly via aiohttp."""
    if not user_id:
        return {}
    url = f"{DJANGO_API_URL}/api/agents/internal/bootstrap/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"user_id": user_id, "caller_phone": caller_phone}
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=5.0) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            logger.error(f"Bootstrap API error ({resp.status}): {text}")
            return {}
    except Exception as e:
        logger.error(f"Failed to fetch bootstrap asynchronously from Django API: {e}")
        return {}

def fetch_agent_bootstrap_sync(user_id: int, caller_phone: str = "web_dashboard") -> dict:
    """Fetch complete agent bootstrap bundle via synchronous HTTP (backward compatibility)."""
    if not user_id:
        return {}
    try:
        url = f"{DJANGO_API_URL}/api/agents/internal/bootstrap/"
        headers = {
            "X-Internal-API-Key": INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        res = requests.post(url, json={"user_id": user_id, "caller_phone": caller_phone}, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
        logger.error(f"Bootstrap API error ({res.status_code}): {res.text}")
        return {}
    except Exception as e:
        logger.error(f"Failed to fetch bootstrap from Django API: {e}")
        return {}


# ==================== Knowledge RAG API ====================

async def query_knowledge_base_async(query: str, user_id: int, genai_client=None, top_k: int = 4) -> str:
    """Query user's documents semantically via Django Knowledge RAG API non-blockingly."""
    if isinstance(genai_client, int) and top_k == 4:
        top_k = genai_client
    if not user_id:
        return "لا توجد مستندات مرفوعة لهذا المستخدم."
    url = f"{DJANGO_API_URL}/api/knowledge/internal/rag/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "user_id": user_id,
        "query": query,
        "top_k": top_k
    }
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=6.0) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("text", "لم يتم العثور على أي معلومات متعلقة بهذا السؤال في المستندات المرفوعة.")
            text = await resp.text()
            logger.error(f"Knowledge RAG API error ({resp.status}): {text}")
            return "حدث خطأ أثناء البحث في المستندات عبر الواجهة البرمجية."
    except Exception as e:
        logger.error(f"Failed to query knowledge API asynchronously: {e}")
        return f"حدث خطأ أثناء البحث في المستندات: {e}"

def query_knowledge_base_sync(query: str, user_id: int, genai_client=None, top_k: int = 4) -> str:
    """Query user's documents semantically via Django Knowledge RAG API synchronously."""
    if not user_id:
        return "لا توجد مستندات مرفوعة لهذا المستخدم."
    try:
        url = f"{DJANGO_API_URL}/api/knowledge/internal/rag/"
        headers = {
            "X-Internal-API-Key": INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "user_id": user_id,
            "query": query,
            "top_k": top_k
        }
        res = requests.post(url, json=payload, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            return data.get("text", "لم يتم العثور على أي معلومات متعلقة بهذا السؤال في المستندات المرفوعة.")
        logger.error(f"Knowledge RAG API error ({res.status_code}): {res.text}")
        return "حدث خطأ أثناء البحث في المستندات عبر الواجهة البرمجية."
    except Exception as e:
        logger.error(f"Failed to query knowledge API: {e}", exc_info=True)
        return f"حدث خطأ أثناء البحث في المستندات: {e}"


# ==================== AI Transfer API ====================

async def trigger_ai_transfer_async(room_name: str, user_id: int, queue_code: str, caller_phone: str = "web", caller_name: str = "العميل", reason: str = "") -> dict:
    """Notify Django backend to dispatch Inngest transfer non-blockingly."""
    url = f"{DJANGO_API_URL}/api/call-center/internal/ai-transfer/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "room_name": room_name,
        "user_id": user_id,
        "queue_code": queue_code,
        "caller_phone": caller_phone,
        "caller_name": caller_name,
        "reason": reason
    }
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=5.0) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            logger.error(f"AI transfer API error ({resp.status}): {text}")
            return {"status": "error", "message": text}
    except Exception as e:
        logger.error(f"Failed to trigger AI transfer asynchronously: {e}")
        return {"status": "error", "message": str(e)}

def trigger_ai_transfer_sync(room_name: str, user_id: int, queue_code: str, caller_phone: str = "web", caller_name: str = "العميل", reason: str = "") -> dict:
    """Notify Django backend to dispatch Inngest transfer synchronously."""
    try:
        url = f"{DJANGO_API_URL}/api/call-center/internal/ai-transfer/"
        headers = {
            "X-Internal-API-Key": INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "room_name": room_name,
            "user_id": user_id,
            "queue_code": queue_code,
            "caller_phone": caller_phone,
            "caller_name": caller_name,
            "reason": reason
        }
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
        logger.error(f"AI transfer API error ({res.status_code}): {res.text}")
        return {"status": "error", "message": res.text}
    except Exception as e:
        logger.error(f"Failed to trigger AI transfer via Django API: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ==================== Call Session & Memory Save API ====================

def _build_call_complete_payload(user_id: int, room_name: str, started_at: float, transcript_text: str, summary: str, updated_profile: dict, caller_phone: str = "web_dashboard", outbound_context: dict = None, duration_seconds: Optional[int] = None) -> dict:
    now_ts = time.time()
    if duration_seconds is not None:
        duration = max(0, int(duration_seconds))
    else:
        duration = max(0, int(now_ts - started_at))
    direction = 'inbound'
    destination_phone = ''
    call_goal = ''
    if outbound_context:
        if outbound_context.get("is_outbound_ai"):
            direction = 'outbound_ai'
        elif outbound_context.get("direction"):
            direction = outbound_context.get("direction")
        destination_phone = str(outbound_context.get("destination_phone") or "")
        call_goal = str(outbound_context.get("call_goal") or "")

    return {
        "user_id": user_id,
        "room_name": room_name,
        "caller_phone": caller_phone,
        "started_at": started_at,
        "duration_seconds": duration,
        "direction": direction,
        "destination_phone": destination_phone,
        "call_goal": call_goal,
        "transcript_text": transcript_text,
        "summary": summary,
        "permanent_profile": updated_profile
    }

async def save_call_session_and_update_memory_async(user_id: int, room_name: str, started_at: float, transcript_text: str, summary: str, updated_profile: dict, caller_phone: str = "web_dashboard", outbound_context: dict = None, duration_seconds: Optional[int] = None):
    """Persist completed CallSession and update CustomerMemory non-blockingly via aiohttp."""
    if not user_id:
        return
    payload = _build_call_complete_payload(user_id, room_name, started_at, transcript_text, summary, updated_profile, caller_phone, outbound_context, duration_seconds=duration_seconds)
    url = f"{DJANGO_API_URL}/api/crm/internal/complete-call/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=5.0) as resp:
            if resp.status == 200:
                logger.info(f"Successfully saved CallSession & CustomerMemory via Django CRM API (async) for ({user_id}, {caller_phone})")
            else:
                text = await resp.text()
                logger.error(f"Error saving CallSession via CRM API ({resp.status}): {text}")
    except Exception as e:
        logger.error(f"Failed to save call session via Django API asynchronously: {e}")

def save_call_session_and_update_memory_sync(user_id: int, room_name: str, started_at: float, transcript_text: str, summary: str, updated_profile: dict, caller_phone: str = "web_dashboard", outbound_context: dict = None, duration_seconds: Optional[int] = None):
    """Persist completed CallSession and update CustomerMemory synchronously."""
    if not user_id:
        return
    payload = _build_call_complete_payload(user_id, room_name, started_at, transcript_text, summary, updated_profile, caller_phone, outbound_context, duration_seconds=duration_seconds)
    url = f"{DJANGO_API_URL}/api/crm/internal/complete-call/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 200:
            logger.info(f"Successfully saved CallSession & CustomerMemory via Django CRM API for ({user_id}, {caller_phone})")
        else:
            logger.error(f"Error saving CallSession via CRM API ({res.status_code}): {res.text}")
    except Exception as e:
        logger.error(f"Failed to save call session via Django API: {e}", exc_info=True)


def fetch_user_active_profile_sync(user_id: int, bootstrap: dict = None) -> dict:
    """Fetch active agent profile for user via Django API."""
    if bootstrap is not None:
        return parse_active_profile_from_bootstrap(bootstrap)
    if not user_id:
        return parse_active_profile_from_bootstrap({})
    try:
        b = fetch_agent_bootstrap_sync(user_id)
        return parse_active_profile_from_bootstrap(b)
    except Exception as e:
        logger.error(f"Error fetching active profile for user {user_id}: {e}")
        return parse_active_profile_from_bootstrap({})


def fetch_customer_memory_sync(user_id: int, caller_phone: str = "web_dashboard", bootstrap: dict = None) -> dict:
    """Fetch customer memory (permanent profile + immediate summary) for a specific phone number via Django API."""
    if bootstrap is not None:
        return parse_customer_memory_from_bootstrap(bootstrap, caller_phone)
    if not user_id:
        return parse_customer_memory_from_bootstrap({}, caller_phone)
    try:
        b = fetch_agent_bootstrap_sync(user_id, caller_phone)
        return parse_customer_memory_from_bootstrap(b, caller_phone)
    except Exception as e:
        logger.error(f"Error fetching customer memory for user {user_id} ({caller_phone}): {e}")
        return {"phone_number": caller_phone, "permanent_profile": {}, "last_interaction_summary": "", "card_text": "", "total_calls_count": 0}


async def lookup_customer_memory_async(user_id: int, query: str) -> dict:
    """Lookup customer memory in Django CRM by name or phone query non-blockingly."""
    if not user_id or not query:
        return {"status": "error", "found": False, "message": "query and user_id are required"}
    url = f"{DJANGO_API_URL}/api/crm/internal/memory/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"user_id": user_id, "query": query}
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=5.0) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            logger.error(f"CRM Memory lookup error ({resp.status}): {text}")
            return {"status": "error", "found": False, "message": text}
    except Exception as e:
        logger.error(f"Failed to lookup customer memory asynchronously: {e}")
        return {"status": "error", "found": False, "message": str(e)}


def lookup_customer_memory_sync(user_id: int, query: str) -> dict:
    """Lookup customer memory in Django CRM synchronously."""
    if not user_id or not query:
        return {"status": "error", "found": False, "message": "query and user_id are required"}
    try:
        url = f"{DJANGO_API_URL}/api/crm/internal/memory/"
        headers = {
            "X-Internal-API-Key": INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        res = requests.post(url, json={"user_id": user_id, "query": query}, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
        logger.error(f"CRM Memory lookup sync error ({res.status_code}): {res.text}")
        return {"status": "error", "found": False, "message": res.text}
    except Exception as e:
        logger.error(f"Failed to lookup customer memory synchronously: {e}")
        return {"status": "error", "found": False, "message": str(e)}

