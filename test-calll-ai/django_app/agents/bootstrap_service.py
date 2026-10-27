"""JIT Agent Session Bootstrap Service.

Assembles unified bootstrap bundle for AI Voice Agent session and manages
sub-millisecond Redis caching (room_bootstrap:{room_name}) with 10-minute TTL.
"""
import re
import json
import logging
from typing import Optional, Dict, Any, Tuple

from django.conf import settings
from django.contrib.auth.models import User
import redis

from agents.models import AgentProfile, UserMCPServer, SystemSetting
from agents.live_context_service import get_user_live_context_cached

logger = logging.getLogger(__name__)

BOOTSTRAP_REDIS_PREFIX = "room_bootstrap"
BOOTSTRAP_TTL_SECONDS = 600  # 10 minutes

_redis_pool: Optional[redis.ConnectionPool] = None


def get_redis_connection() -> Optional[redis.Redis]:
    """Return a pooled Redis client instance for sub-millisecond latency."""
    global _redis_pool
    try:
        if _redis_pool is None:
            _redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, max_connections=20)
        return redis.Redis(connection_pool=_redis_pool)
    except Exception as e:
        logger.warning(f"[Bootstrap] Redis connection error: {e}")
        return None


def assemble_agent_bootstrap_data(
    user_id: Optional[int] = None,
    caller_phone: Optional[str] = None,
    caller_extension: Optional[str] = None,
    room_name: Optional[str] = None,
    wazo_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assemble the complete bootstrap bundle for an AI Voice Agent session.
    Equivalent to the data returned by /api/agents/internal/bootstrap/.
    """
    is_internal_test = False
    clean_caller_ext = str(caller_extension or "").strip()
    clean_caller_phone = str(caller_phone or "").strip()
    clean_room_name = str(room_name or "").strip()

    r = get_redis_connection()
    if clean_room_name and r:
        try:
            is_internal_test = bool(r.get(f"is_internal_test:{clean_room_name}"))
            if not clean_caller_ext:
                c_ext = r.get(f"caller_ext:{clean_room_name}")
                if c_ext:
                    clean_caller_ext = c_ext.decode() if isinstance(c_ext, bytes) else str(c_ext)
        except Exception as r_err:
            logger.debug(f"[Bootstrap] Redis lookup note for room {clean_room_name}: {r_err}")

    if not clean_caller_ext and clean_room_name and "__" in clean_room_name:
        try:
            cand = clean_room_name.split("__", 1)[1].split("_")[0]
            if cand:
                clean_caller_ext = cand
        except Exception:
            pass

    if not user_id and clean_room_name and r:
        try:
            cached_meta = r.get(f"room_job_meta:{clean_room_name}")
            if cached_meta:
                meta_json = json.loads(cached_meta)
                if meta_json.get("user_id"):
                    user_id = meta_json.get("user_id")
        except Exception:
            pass

    if not user_id and clean_room_name:
        parts = clean_room_name.split("_")
        for part in parts:
            if part.isdigit() and len(part) <= 6 and part != "999":
                try:
                    user_id = int(part)
                    break
                except ValueError:
                    pass

    if not user_id:
        return {"status": "error", "message": "user_id is required"}

    user = User.objects.filter(id=user_id).first()
    if not user:
        return {"status": "error", "message": f"User #{user_id} not found"}

    # 1. Agent Profile
    profile = AgentProfile.objects.filter(user=user, is_active=True).first()
    profile_data = profile.to_dict() if profile else {
        "name": "البروفايل الافتراضي",
        "voice_name": "Aoede",
        "gender": "female",
        "dialect": "egyptian",
        "persona_role": "customer_support",
        "speaking_style": "friendly",
        "welcome_message": "",
        "is_welcome_message_enabled": True,
        "custom_instructions": "",
        "off_topic_response": "",
        "is_active": True
    }

    # 2. External FastMCP Servers
    mcp_servers = UserMCPServer.objects.filter(user=user, is_active=True)
    mcp_list = [s.to_dict() for s in mcp_servers]

    # 2.1 Inherit Partner Shared MCP Server if user is a sub-client
    partner_info = None
    try:
        from partners.models import PartnerClientRelationship
        partner_rel = PartnerClientRelationship.objects.select_related('partner').filter(
            client=user,
            partner__status='approved'
        ).first()
        if partner_rel and partner_rel.partner:
            partner = partner_rel.partner
            partner_info = {
                "partner_id": partner.id,
                "partner_code": partner.partner_code,
                "custom_rate": float(partner.custom_rate_per_minute),
                "client_id": user.id,
                "external_reference": partner_rel.external_reference,
            }
            if partner.shared_mcp_server and partner.shared_mcp_server.is_active:
                shared_dict = partner.shared_mcp_server.to_dict()
                shared_dict['is_partner_inherited'] = True
                shared_dict['client_id'] = user.id
                if not any(s['id'] == shared_dict['id'] for s in mcp_list):
                    mcp_list.append(shared_dict)
    except Exception as p_err:
        logger.debug(f"[Bootstrap] Partner inheritance note: {p_err}")

    # 3. Customer Memory
    from crm.models import CustomerMemory
    from django.db.models import Q

    target_phone = clean_caller_phone or 'web_dashboard'

    # Resolve employee phone number if calling from internal extension/SIP
    if clean_caller_ext or target_phone.startswith('emp'):
        try:
            from call_center.models import EmployeeProfile
            ext_q = clean_caller_ext or target_phone.replace('emp', '')
            emp_obj = EmployeeProfile.objects.filter(Q(extension=ext_q) | Q(sip_username__icontains=target_phone)).first()
            if emp_obj and emp_obj.phone_number:
                target_phone = emp_obj.phone_number
        except Exception:
            pass

    if target_phone == 'web_dashboard':
        target_phone = '+201000000000'

    memory = CustomerMemory.objects.filter(user=user, phone_number=target_phone).first()
    if not memory and len(target_phone) >= 7:
        clean_digits = re.sub(r'\D', '', target_phone)
        suffix = clean_digits[-8:] if len(clean_digits) >= 8 else target_phone[-8:]
        memory = CustomerMemory.objects.filter(user=user, phone_number__endswith=suffix).first()

    memory_data = memory.to_dict() if memory else {
        "phone_number": target_phone,
        "customer_name": "",
        "permanent_profile": {},
        "card_data": {},
        "last_interaction_summary": "",
        "card_text": "",
        "total_calls_count": 0
    }

    # 4. Active Call Queues for this tenant/user
    from call_center.models import CallQueue
    queues = CallQueue.objects.filter(user=user, is_active=True).order_by('code')
    queues_list = [
        {
            "id": q.id,
            "name": q.name,
            "code": q.code,
            "description": q.description or "",
            "strategy": q.strategy,
            "ring_timeout_seconds": q.ring_timeout_seconds,
            "total_timeout_seconds": q.total_timeout_seconds,
            "members_count": q.memberships.filter(is_active=True).count()
        }
        for q in queues
    ]

    # 5. Structured Live Context (Cached in Redis)
    live_ctx_data = get_user_live_context_cached(user.id)

    # 6. Knowledge Documents Manifest
    knowledge_manifest = []
    try:
        from knowledge.models import Document
        docs = Document.objects.filter(user=user, status='ready').values('id', 'title')[:15]
        knowledge_manifest = [{"id": d["id"], "title": d["title"]} for d in docs]
    except Exception as k_err:
        logger.warning(f"[Bootstrap] Error loading knowledge manifest for user {user.id}: {k_err}")

    return {
        "status": "success",
        "user_id": user.id,
        "gemini_api_key": SystemSetting.get_gemini_api_key(),
        "profile": profile_data,
        "mcp_servers": mcp_list,
        "customer_memory": memory_data,
        "partner_info": partner_info,
        "call_queues": queues_list,
        "live_context": live_ctx_data,
        "knowledge_manifest": knowledge_manifest,
        "is_internal_test": is_internal_test,
        "caller_extension": clean_caller_ext or ""
    }


def inject_room_bootstrap_to_redis(room_name: str, bundle: Dict[str, Any], ttl: int = BOOTSTRAP_TTL_SECONDS) -> bool:
    """
    Inject unified room bootstrap bundle into Redis key room_bootstrap:{room_name}
    with TTL (default 10 minutes / 600s).
    Enables sub-millisecond (<1ms) fast read by AI voice agent workers.
    """
    if not room_name or not bundle:
        return False
    try:
        r = get_redis_connection()
        if not r:
            return False
        redis_key = f"{BOOTSTRAP_REDIS_PREFIX}:{room_name}"
        r.set(redis_key, json.dumps(bundle, ensure_ascii=False), ex=ttl)
        logger.info(f"[Bootstrap Inject] Pre-cached room_bootstrap for '{room_name}' (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.warning(f"[Bootstrap Inject Error] Failed to write room_bootstrap for '{room_name}': {e}")
        return False


def get_room_bootstrap_from_redis(room_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve room bootstrap directly from Redis if available (<1ms)."""
    if not room_name:
        return None
    try:
        r = get_redis_connection()
        if not r:
            return None
        raw = r.get(f"{BOOTSTRAP_REDIS_PREFIX}:{room_name}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug(f"[Bootstrap Read Error] Failed to read room_bootstrap for '{room_name}': {e}")
    return None
