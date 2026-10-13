import time
import json
import hashlib
from typing import Optional, Dict, Any, List
import requests
import redis.asyncio as aioredis
from config import DJANGO_API_URL, INTERNAL_API_KEY, REDIS_URL, logger
from .http_pool import get_http_session

_redis_aioclient: Optional[aioredis.Redis] = None


async def get_async_redis_client():
    """Retrieve shared async Redis client for sub-millisecond L1 RAG caching."""
    global _redis_aioclient
    if _redis_aioclient is None:
        try:
            _redis_aioclient = aioredis.from_url(REDIS_URL, decode_responses=True)
        except Exception as e:
            logger.debug(f"Redis async client init note: {e}")
    return _redis_aioclient


def get_rag_tenant_cache_key(user_id: int, query: str) -> str:
    """Generate normalized multi-tenant cache key for RAG queries."""
    clean_q = " ".join(
        str(query or '').lower()
        .replace('؟', ' ').replace('?', ' ')
        .replace('،', ' ').replace(',', ' ')
        .replace('!', ' ').replace('.', ' ')
        .split()
    )
    q_hash = hashlib.sha256(clean_q.encode('utf-8')).hexdigest()[:16]
    return f"rag:tenant:{user_id}:cache:{q_hash}"

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
            "custom_role": prof.get("custom_role"),
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

async def fetch_agent_bootstrap_async(user_id: Optional[int] = None, caller_phone: str = "web_dashboard", room_name: str = "", caller_extension: str = "") -> dict:
    """Fetch complete agent bootstrap bundle non-blockingly via aiohttp."""
    if not user_id and not room_name and not caller_extension:
        return {}
    url = f"{DJANGO_API_URL}/api/agents/internal/bootstrap/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"user_id": user_id, "caller_phone": caller_phone, "room_name": room_name, "caller_extension": caller_extension}
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

def fetch_agent_bootstrap_sync(user_id: Optional[int] = None, caller_phone: str = "web_dashboard", room_name: str = "", caller_extension: str = "") -> dict:
    """Fetch complete agent bootstrap bundle via synchronous HTTP (backward compatibility)."""
    if not user_id and not room_name and not caller_extension:
        return {}
    try:
        url = f"{DJANGO_API_URL}/api/agents/internal/bootstrap/"
        headers = {
            "X-Internal-API-Key": INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"user_id": user_id, "caller_phone": caller_phone, "room_name": room_name, "caller_extension": caller_extension}
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
        logger.error(f"Bootstrap API error ({res.status_code}): {res.text}")
        return {}
    except Exception as e:
        logger.error(f"Failed to fetch bootstrap from Django API: {e}")
        return {}


# ==================== Knowledge RAG API ====================

def _resolve_rag_args(arg1=None, arg2=None, genai_client=None, top_k=4, **kwargs):
    """Normalize and resolve (query, user_id) or (user_id, query) robustly."""
    uid = kwargs.get("user_id")
    q = kwargs.get("query")

    if uid is None and q is None:
        if isinstance(arg1, (int, float)) or (isinstance(arg1, str) and arg1.isdigit() and not (isinstance(arg2, str) and arg2.isdigit())):
            uid, q = arg1, arg2
        elif isinstance(arg2, (int, float)) or (isinstance(arg2, str) and str(arg2).isdigit()):
            q, uid = arg1, arg2
        else:
            q, uid = arg1, arg2
    elif uid is None:
        if isinstance(arg1, (int, float)) or (isinstance(arg1, str) and arg1.isdigit()):
            uid = arg1
        elif isinstance(arg2, (int, float)) or (isinstance(arg2, str) and str(arg2).isdigit()):
            uid = arg2
    elif q is None:
        if arg1 is not None and not (isinstance(arg1, (int, float)) or (isinstance(arg1, str) and arg1.isdigit())):
            q = arg1
        elif arg2 is not None and not (isinstance(arg2, (int, float)) or (isinstance(arg2, str) and str(arg2).isdigit())):
            q = arg2

    try:
        clean_user_id = int(uid) if uid is not None else None
    except (ValueError, TypeError):
        clean_user_id = None

    clean_query = str(q or "").strip()

    if isinstance(genai_client, int) and top_k == 4:
        top_k = genai_client

    return clean_query, clean_user_id, top_k

async def query_knowledge_base_async(arg1=None, arg2=None, genai_client=None, top_k: int = 4, **kwargs) -> str:
    """Query user's documents semantically via Django Knowledge RAG API non-blockingly.
    Supports (query, user_id) or (user_id, query) or kwargs.
    """
    query, user_id, top_k = _resolve_rag_args(arg1, arg2, genai_client=genai_client, top_k=top_k, **kwargs)
    if not user_id:
        return "لا توجد مستندات مرفوعة لهذا المستخدم."
    if not query:
        return "يرجى تحديد سؤال للبحث في المستندات."

    # 0. Check L1 In-Memory Redis Cache directly (sub-millisecond latency)
    cache_key = get_rag_tenant_cache_key(user_id, query)
    try:
        r = await get_async_redis_client()
        if r:
            cached_val = await r.get(cache_key)
            if cached_val:
                cached_data = json.loads(cached_val)
                text_out = cached_data.get("text", "")
                if text_out:
                    logger.info(f"[L1 Redis Agent Cache Hit] Served instantly (<1ms) for tenant {user_id}")
                    return text_out
    except Exception as redis_read_err:
        logger.debug(f"Direct Redis L1 read skipped: {redis_read_err}")

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
                ret_text = data.get("text", "لم يتم العثور على أي معلومات متعلقة بهذا السؤال في المستندات المرفوعة.")
                # Save to Redis L1 cache directly for sub-millisecond future hits
                try:
                    r = await get_async_redis_client()
                    if r and data.get("matches"):
                        await r.set(
                            cache_key,
                            json.dumps({"text": ret_text, "matches": data.get("matches", [])}, ensure_ascii=False),
                            ex=86400 * 7
                        )
                except Exception as redis_write_err:
                    logger.debug(f"Direct Redis L1 write skipped: {redis_write_err}")
                return ret_text
            text = await resp.text()
            logger.error(f"Knowledge RAG API error ({resp.status}): {text}")
            return "حدث خطأ أثناء البحث في المستندات عبر الواجهة البرمجية."
    except Exception as e:
        logger.error(f"Failed to query knowledge API asynchronously: {e}")
        return f"حدث خطأ أثناء البحث في المستندات: {e}"

def query_knowledge_base_sync(arg1=None, arg2=None, genai_client=None, top_k: int = 4, **kwargs) -> str:
    """Query user's documents semantically via Django Knowledge RAG API synchronously.
    Supports (query, user_id) or (user_id, query) or kwargs.
    """
    query, user_id, top_k = _resolve_rag_args(arg1, arg2, genai_client=genai_client, top_k=top_k, **kwargs)
    if not user_id:
        return "لا توجد مستندات مرفوعة لهذا المستخدم."
    if not query:
        return "يرجى تحديد سؤال للبحث في المستندات."

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


def _resolve_memory_args(arg1=None, arg2=None, **kwargs):
    uid = kwargs.get("user_id")
    q = kwargs.get("query")
    if uid is None and q is None:
        if isinstance(arg1, (int, float)) or (isinstance(arg1, str) and arg1.isdigit()):
            uid, q = arg1, arg2
        elif isinstance(arg2, (int, float)) or (isinstance(arg2, str) and str(arg2).isdigit()):
            q, uid = arg1, arg2
        else:
            uid, q = arg1, arg2
    elif uid is None:
        if isinstance(arg1, (int, float)) or (isinstance(arg1, str) and arg1.isdigit()):
            uid = arg1
        elif isinstance(arg2, (int, float)) or (isinstance(arg2, str) and str(arg2).isdigit()):
            uid = arg2
    elif q is None:
        if arg1 is not None and not (isinstance(arg1, (int, float)) or (isinstance(arg1, str) and arg1.isdigit())):
            q = arg1
        elif arg2 is not None and not (isinstance(arg2, (int, float)) or (isinstance(arg2, str) and str(arg2).isdigit())):
            q = arg2
    try:
        clean_user_id = int(uid) if uid is not None else None
    except (ValueError, TypeError):
        clean_user_id = None
    clean_query = str(q or "").strip()
    return clean_user_id, clean_query

async def lookup_customer_memory_async(arg1=None, arg2=None, **kwargs) -> dict:
    """Lookup customer memory in Django CRM by name or phone query non-blockingly."""
    user_id, query = _resolve_memory_args(arg1, arg2, **kwargs)
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


def lookup_customer_memory_sync(arg1=None, arg2=None, **kwargs) -> dict:
    """Lookup customer memory in Django CRM synchronously."""
    user_id, query = _resolve_memory_args(arg1, arg2, **kwargs)
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


async def send_whatsapp_message_async(user_id: int, phone: str, message: str) -> dict:
    """Send WhatsApp message to caller during live AI call session non-blockingly."""
    if not user_id or not phone or not message:
        return {"status": "error", "message": "user_id, phone, and message are required"}
    url = f"{DJANGO_API_URL}/api/agents/internal/whatsapp/send/"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "user_id": user_id,
        "phone_number": phone,
        "message": message
    }
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=5.0) as resp:
            if resp.status == 200:
                return await resp.json()
            err_text = await resp.text()
            logger.error(f"WhatsApp send API error ({resp.status}): {err_text}")
            return {"status": "error", "message": f"API error {resp.status}"}
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message via Django API: {e}")
        return {"status": "error", "message": str(e)}


def send_whatsapp_message_sync(user_id: int, phone: str, message: str) -> dict:
    """Send WhatsApp message synchronously."""
    if not user_id or not phone or not message:
        return {"status": "error", "message": "user_id, phone, and message are required"}
    try:
        url = f"{DJANGO_API_URL}/api/agents/internal/whatsapp/send/"
        headers = {
            "X-Internal-API-Key": INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        res = requests.post(url, json={"user_id": user_id, "phone_number": phone, "message": message}, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
        logger.error(f"WhatsApp send sync error ({res.status_code}): {res.text}")
        return {"status": "error", "message": res.text}
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message synchronously: {e}")
        return {"status": "error", "message": str(e)}


