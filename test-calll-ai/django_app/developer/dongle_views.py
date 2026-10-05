"""Dongle Gateway API views for AI Voice Agent platform.

Allows local GSM USB Dongle gateways (desktop/mobile Flet app) to:
1. Authenticate the business owner using ONLY username and password (NO email!).
2. Initiate incoming cellular calls into LiveKit WebRTC rooms.
3. Hang up and record call sessions.
4. Check gateway status.
"""
import os
import json
import time
import secrets
import logging
import jwt
import redis
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from livekit import api

from agents.models import AgentProfile
from agents.live_context_service import get_user_live_context_cached
from voice_assistant.models import CallSession

logger = logging.getLogger(__name__)

JWT_SECRET = getattr(settings, 'SECRET_KEY', 'default_secret_key')
JWT_ALGORITHM = 'HS256'
JWT_EXP_DAYS = 90  # 90-day remember-me session


def generate_owner_dongle_jwt(user: User) -> str:
    """Generate long-lived JWT token for owner's local dongle gateway."""
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": "owner",
        "created_at": int(time.time()),
        "exp": int(time.time()) + (JWT_EXP_DAYS * 24 * 3600),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_owner_from_dongle_token(request) -> User | None:
    """Extract and validate owner user from Authorization Bearer header, X-Dongle-Token, or X-API-Key."""
    # 1. Check Bearer or X-Dongle-Token
    auth_header = request.headers.get("Authorization", "")
    token_str = ""
    if auth_header.startswith("Bearer "):
        token_str = auth_header.split("Bearer ", 1)[1].strip()
    elif request.headers.get("X-Dongle-Token"):
        token_str = request.headers.get("X-Dongle-Token").strip()
    elif request.GET.get("token"):
        token_str = request.GET.get("token").strip()

    if token_str:
        try:
            payload = jwt.decode(token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")
            if user_id:
                user = User.objects.filter(id=user_id, is_active=True).first()
                if user:
                    return user
        except jwt.PyJWTError as e:
            logger.warning(f"Invalid Dongle JWT: {e}")

    # 2. Fallback to X-API-Key if available
    api_key = request.headers.get("X-API-Key")
    if api_key:
        from developer.models import UserApiKey
        key_obj = UserApiKey.objects.filter(key=api_key, is_active=True).select_related('user').first()
        if key_obj:
            return key_obj.user

    return None


@csrf_exempt
def api_dongle_auth_login(request):
    """Authenticate business owner using strictly username and password (NO email).

    Returns JWT token, user details, and active agent profile info.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({"status": "error", "message": "صيغة البيانات غير صحيحة (JSON مطلوب)"}, status=400)

    username = str(data.get('username') or '').strip()
    password = str(data.get('password') or '').strip()

    if not username or not password:
        return JsonResponse({
            "status": "error",
            "message": "اسم المستخدم وكلمة المرور مطلوبان"
        }, status=400)

    # Strictly authenticate by username only! No email allowed
    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({
            "status": "error",
            "message": "اسم المستخدم أو كلمة المرور غير صحيحة"
        }, status=401)

    if not user.is_active:
        return JsonResponse({
            "status": "error",
            "message": "هذا الحساب معطل حالياً، يرجى مراجعة إدارة المنصة"
        }, status=403)

    # Generate persistent token for Auto-login
    token = generate_owner_dongle_jwt(user)

    # Fetch active agent profile and live context
    active_profile = AgentProfile.objects.filter(user=user, is_active=True).first()
    live_ctx = get_user_live_context_cached(user.id)

    livekit_url = getattr(settings, 'LIVEKIT_URL', 'wss://livekit.169.58.32.179.nip.io')

    return JsonResponse({
        "status": "success",
        "message": f"مرحباً بك، {user.get_full_name() or user.username}",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.get_full_name() or user.username,
            "is_staff": user.is_staff,
        },
        "active_profile": {
            "id": active_profile.id if active_profile else None,
            "name": active_profile.name if active_profile else "المساعد الافتراضي",
            "dialect": active_profile.dialect if active_profile else "egyptian",
            "persona_role": active_profile.persona_role if active_profile else "customer_support",
        } if active_profile else None,
        "has_live_context": bool(live_ctx),
        "livekit_url": livekit_url,
    })


@csrf_exempt
def api_dongle_call_init(request):
    """Initiate an incoming cellular call from the local USB Dongle into a LiveKit WebRTC room.

    Creates room, generates audio WebRTC token, and queues voice_agent with owner's live context.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    user = get_owner_from_dongle_token(request)
    if not user:
        return JsonResponse({"status": "error", "message": "غير مصرح - يرجى تسجيل الدخول أولاً"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

    caller_phone = str(data.get('caller_phone') or 'unknown_caller').strip()
    dongle_id = str(data.get('dongle_id') or 'dongle_main').strip()

    ts = int(time.time())
    rand_suffix = secrets.token_hex(3)
    room_name = f"dongle_{user.id}_{ts}_{rand_suffix}"
    participant_identity = f"dongle_{user.id}_{caller_phone}_{secrets.token_hex(2)}"

    # Generate LiveKit WebRTC AccessToken with audio publish & subscribe
    lk_key = getattr(settings, 'LIVEKIT_API_KEY', 'devkey')
    lk_secret = getattr(settings, 'LIVEKIT_API_SECRET', 'secretkey1234567890abcdef')

    token = api.AccessToken(lk_key, lk_secret) \
        .with_identity(participant_identity) \
        .with_name(f"Caller {caller_phone}") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True
        )) \
        .to_jwt()

    active_profile = AgentProfile.objects.filter(user=user, is_active=True).first()

    # Create CallSession record in PostgreSQL
    session = CallSession.objects.create(
        user=user,
        room_name=room_name,
        caller_phone=caller_phone,
        direction="inbound"
    )

    # Dispatch to Redis 'agent_jobs' so voice_agent joins with owner's live context
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        job_payload = {
            "room_name": room_name,
            "user_id": user.id,
            "caller_phone": caller_phone,
            "profile": active_profile.to_dict() if active_profile else None,
            "participant_identity": participant_identity,
            "is_queue": False,
            "is_off_hours": False,
            "session_id": session.id,
            "source": "usb_dongle",
            "dongle_id": dongle_id
        }
        r.rpush("agent_jobs", json.dumps(job_payload, ensure_ascii=False))
        logger.info(f"Queued agent job for USB dongle call in room {room_name} (Caller: {caller_phone})")
    except Exception as e:
        logger.error(f"Failed to push dongle agent job to Redis: {e}")

    livekit_url = getattr(settings, 'LIVEKIT_URL', 'wss://livekit.169.58.32.179.nip.io')

    return JsonResponse({
        "status": "success",
        "room_name": room_name,
        "token": token,
        "livekit_url": livekit_url,
        "participant_identity": participant_identity,
        "session_id": session.id,
        "caller_phone": caller_phone
    })


@csrf_exempt
def api_dongle_call_hangup(request):
    """End a dongle call session and update duration/ended_at in DB."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    user = get_owner_from_dongle_token(request)
    if not user:
        return JsonResponse({"status": "error", "message": "غير مصرح"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = {}

    room_name = data.get('room_name')
    duration = int(data.get('duration_seconds') or 0)
    session_id = data.get('session_id')

    session = None
    if session_id:
        session = CallSession.objects.filter(id=session_id, user=user).first()
    elif room_name:
        session = CallSession.objects.filter(room_name=room_name, user=user).first()

    if session:
        from django.utils import timezone
        session.ended_at = timezone.now()
        session.duration_seconds = max(session.duration_seconds or 0, duration)
        session.save(update_fields=['ended_at', 'duration_seconds'])
        logger.info(f"Dongle call session {session.id} marked completed (duration: {session.duration_seconds}s)")

    return JsonResponse({
        "status": "success",
        "message": "تم إنهاء المكالمة وتسجيل البيانات بنجاح"
    })


@csrf_exempt
def api_dongle_status(request):
    """Check owner dongle connection status, active agent, and live context."""
    user = get_owner_from_dongle_token(request)
    if not user:
        return JsonResponse({"status": "error", "message": "غير مصرح"}, status=401)

    active_profile = AgentProfile.objects.filter(user=user, is_active=True).first()
    ctx = get_user_live_context_cached(user.id)

    return JsonResponse({
        "status": "success",
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.get_full_name() or user.username
        },
        "has_active_agent": bool(active_profile),
        "agent_name": active_profile.name if active_profile else None,
        "has_live_context": bool(ctx),
        "live_context_items_count": len(ctx) if ctx else 0,
        "livekit_url": getattr(settings, 'LIVEKIT_URL', 'wss://livekit.169.58.32.179.nip.io')
    })
