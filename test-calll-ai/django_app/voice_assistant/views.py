import json
import logging
import os
import time
import uuid
import jwt
import requests
import redis
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from livekit import api

from agents.models import AgentProfile
from call_center.models import CallQueue
from telephony.models import OutboundSIPTrunk
from crm.models import CallSession
from telephony.views import _async_dial_sip_participant

# Re-export views from domain apps for backward compatibility
from knowledge.views import (
    list_documents,
    upload_document,
    delete_document,
)
from agents.views import (
    list_profiles,
    create_profile,
    activate_profile,
    update_profile,
    delete_profile,
    get_mcp_server,
    save_mcp_server,
    sync_mcp_server,
    toggle_mcp_server,
    delete_mcp_server,
    test_mcp_connection_view,
    test_mcp_tool_view,
    api_user_live_context_web,
    api_user_live_context_preview_web,
)
from crm.views import (
    list_customers_memory,
    get_customer_memory,
    reset_customer_memory,
)
from telephony.views import (
    normalize_phone_number,
    get_outbound_trunk,
    save_outbound_trunk,
    delete_outbound_trunk,
    trigger_ai_outbound_call,
    list_outbound_gateways,
    list_pbx_trunks,
    save_pbx_trunk,
    delete_pbx_trunk,
)
from telephony.models import InboundPBXTrunk
from call_center.views import (
    api_employee_login,
    api_employee_me,
    api_list_employees,
    api_create_employee,
    api_delete_employee,
    api_update_employee_status,
    list_call_queues,
    create_call_queue,
    delete_call_queue,
    api_dial_call,
    api_get_call_token,
    api_hangup_call,
)

logger = logging.getLogger(__name__)

from common.centrifugo import publish_to_centrifugo

# ==================== Authentication Views ====================

def login_view(request):
    """Render and process login."""
    if request.user.is_authenticated:
        return redirect('voice_assistant:room')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            error = "يرجى إدخال اسم المستخدم وكلمة المرور."
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next') or request.POST.get('next') or '/'
                return redirect(next_url)
            else:
                error = "اسم المستخدم أو كلمة المرور غير صحيحة."

    return render(request, 'voice_assistant/login.html', {'error': error})

def register_view(request):
    """Render and process user registration."""
    if request.user.is_authenticated:
        return redirect('voice_assistant:room')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not username or not password:
            error = "اسم المستخدم وكلمة المرور مطلوبان."
        elif len(password) < 6:
            error = "يجب أن تتكون كلمة المرور من 6 أحرف على الأقل."
        elif password != password_confirm:
            error = "كلمتا المرور غير متطابقتين."
        elif User.objects.filter(username=username).exists():
            error = "اسم المستخدم هذا مسجل بالفعل، يرجى اختيار اسم آخر."
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            return redirect('voice_assistant:room')

    return render(request, 'voice_assistant/register.html', {'error': error})

def logout_view(request):
    """Log out user and redirect to login page."""
    logout(request)
    return redirect('voice_assistant:login')

# ==================== Voice Room & WebRTC ====================

@never_cache
@login_required(login_url='/login/')
def room_view(request):
    """Render the main Voice Assistant page."""
    context = {
        'centrifugo_ws_url': settings.CENTRIFUGO_WS_URL,
        'livekit_url': settings.LIVEKIT_URL,
        'username': request.user.username,
        'user_id': request.user.id,
    }
    return render(request, 'voice_assistant/room.html', context)

@login_required(login_url='/login/')
def get_tokens(request):
    """
    Generate authentication tokens for LiveKit and Centrifugo for the authenticated user.
    """
    # Pre-call Wallet Balance Verification (OpenRouter prepaid model)
    try:
        from billing.models import BillingConfig, UserWallet
        billing_cfg = BillingConfig.get_config()
        wallet, _ = UserWallet.objects.get_or_create(
            user=request.user,
            defaults={
                'balance': billing_cfg.initial_welcome_credit,
                'currency': billing_cfg.currency,
                'total_deposited': billing_cfg.initial_welcome_credit,
            }
        )
        if wallet.balance < billing_cfg.cost_per_minute:
            sym = billing_cfg.get_currency_symbol()
            return JsonResponse({
                "status": "error",
                "code": "insufficient_balance",
                "message": f"رصيدك الحالي ({wallet.balance:.2f} {sym}) غير كافٍ لبدء مكالمة جديدة. الحد الأدنى المطلوب هو تكلفة دقيقة واحدة ({billing_cfg.cost_per_minute:.2f} {sym}). يرجى شحن الرصيد للمتابعة.",
                "balance": float(wallet.balance),
                "cost_per_minute": float(billing_cfg.cost_per_minute),
                "currency": wallet.currency,
                "currency_symbol": sym,
            }, status=402)
    except Exception as b_chk_err:
        logger.warning(f"Failed to check wallet balance before call: {b_chk_err}")

    room_name = request.GET.get('room') or f"room_user_{request.user.id}_{uuid.uuid4().hex[:6]}"
    user_identity = f"user_{request.user.id}_{request.user.username}"
    channel_name = f"rooms:{room_name}"

    active_profile = AgentProfile.objects.filter(user=request.user, is_active=True).first()
    if not active_profile:
        active_profile = AgentProfile.objects.create(
            user=request.user,
            name="نورهان - خدمة عملاء مصرية",
            voice_name="Aoede",
            gender="female",
            dialect="egyptian",
            persona_role="customer_support",
            speaking_style="friendly",
            is_active=True
        )

    custom_phone = str(request.GET.get('caller_phone') or request.GET.get('phone') or request.GET.get('customer_phone') or '').strip()
    meta_dict = {
        "user_id": request.user.id,
        "username": request.user.username,
        "profile": active_profile.to_dict()
    }
    if custom_phone:
        meta_dict["caller_phone"] = custom_phone
    metadata = json.dumps(meta_dict)

    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
        .with_identity(user_identity) \
        .with_name(request.user.username) \
        .with_metadata(metadata) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    livekit_jwt = token.to_jwt()

    centrifugo_payload = {
        "sub": user_identity,
        "exp": int(time.time()) + (24 * 3600),
        "subs": {
            channel_name: {}
        }
    }
    centrifugo_jwt = jwt.encode(
        centrifugo_payload,
        settings.CENTRIFUGO_SECRET,
        algorithm="HS256"
    )

    return JsonResponse({
        "status": "success",
        "room_name": room_name,
        "channel": channel_name,
        "user_identity": user_identity,
        "livekit_url": settings.LIVEKIT_URL,
        "livekit_token": livekit_jwt,
        "centrifugo_ws_url": settings.CENTRIFUGO_WS_URL,
        "centrifugo_token": centrifugo_jwt,
        "active_profile": active_profile.to_dict(),
    })

@csrf_exempt
def livekit_webhook(request):
    """
    Handle LiveKit Webhooks.
    When a human participant enters the room, trigger Voice Agent via Redis queue.
    """
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    auth_header = request.headers.get('Authorization')
    if not auth_header:
        logger.warning("LiveKit webhook missing Authorization header")
        return HttpResponse("Missing authorization header", status=401)

    try:
        token_verifier = api.TokenVerifier(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        receiver = api.WebhookReceiver(token_verifier)
        event = receiver.receive(request.body.decode('utf-8'), auth_header)
    except Exception as e:
        logger.error(f"Invalid webhook signature: {e}")
        return HttpResponse("Invalid signature", status=401)

    event_type = event.event
    room_name = event.room.name if event.room else "unknown"
    channel = f"rooms:{room_name}"

    logger.info(f"Received LiveKit Webhook: {event_type} in room {room_name}")

    if event_type == "participant_joined":
        participant_identity = event.participant.identity
        if participant_identity in ("ai-agent", "pipecat-agent"):
            logger.info(f"AI agent ({participant_identity}) joined room {room_name}.")
            publish_to_centrifugo(channel, {
                "event": "agent_connected",
                "message": "المساعد الصوتي متصل وجاهز للاستماع الآن",
                "timestamp": time.time(),
            })
            return HttpResponse("ok")

        # Skip internal helper bots (transfer hold bot, queue bots, egress recorder, etc.)
        if (
            str(participant_identity).startswith("transfer-")
            or str(participant_identity).startswith("queue-")
            or str(participant_identity).startswith("bot_")
            or str(participant_identity).startswith("EG_")
            or str(participant_identity).startswith("egress")
            or participant_identity == "transfer-bot"
        ):
            logger.info(f"Internal helper/egress participant '{participant_identity}' joined room {room_name}. Skipping agent dispatch.")
            return HttpResponse("ok")

        # Automatically start room composite recording via LiveKit Egress & MinIO
        try:
            from .egress_service import start_room_recording
            start_room_recording(room_name)
        except Exception as eg_err:
            logger.warning(f"Could not trigger egress recording for room {room_name}: {eg_err}")

        # Skip direct human-to-human calls (employee to employee or employee to external PSTN)
        if room_name.startswith("call_ext_") or room_name.startswith("call_tr_") or room_name.startswith("call_rst_") or room_name.startswith("pstn_out_") or str(participant_identity).startswith("employee_"):
            logger.info(f"Direct human-to-human call room '{room_name}' (participant: {participant_identity}). Skipping AI agent dispatch.")
            return HttpResponse("ok")

        else:
            user_id = None
            profile = None
            meta_caller_phone = None
            if event.participant.metadata:
                try:
                    meta = json.loads(event.participant.metadata)
                    user_id = meta.get("user_id")
                    profile = meta.get("profile")
                    meta_caller_phone = meta.get("caller_phone")
                except Exception:
                    pass

            if not user_id and participant_identity.startswith("user_"):
                parts = participant_identity.split("_")
                if len(parts) >= 2 and parts[1].isdigit():
                    user_id = int(parts[1])

            if not user_id and room_name.startswith("room_user_"):
                parts = room_name.split("_")
                if len(parts) >= 3 and parts[2].isdigit():
                    user_id = int(parts[2])

            is_queue = False
            queue_code = None
            queue_data = None
            parts = room_name.split("_")
            if len(parts) >= 5 and parts[3] == "queue":
                is_queue = True
                queue_code = parts[4]
            elif room_name.startswith("queue_") and len(parts) >= 2:
                is_queue = True
                queue_code = parts[1]

            if is_queue and queue_code:
                try:
                    q_filter = {"code": queue_code, "is_active": True}
                    if user_id:
                        q_filter["user_id"] = user_id
                    q_obj = CallQueue.objects.filter(**q_filter).first()
                    if q_obj:
                        queue_data = q_obj.to_dict()
                        if not user_id:
                            user_id = q_obj.user_id
                except Exception as e:
                    logger.error(f"Error loading queue {queue_code}: {e}")

            if not user_id:
                try:
                    from telephony.models import resolve_tenant_from_did, resolve_tenant_from_context_and_ext
                    call_to = ""
                    wazo_ctx = ""
                    caller_ext = ""
                    part_attrs = getattr(event.participant, "attributes", {}) or {}
                    if isinstance(part_attrs, dict):
                        l_attrs = {str(k).lower(): str(v) for k, v in part_attrs.items()}
                        call_to = (
                            part_attrs.get("sip.callTo")
                            or part_attrs.get("sip.phoneNumber")
                            or l_attrs.get("sip.callto")
                            or l_attrs.get("sip.phonenumber")
                            or ""
                        )
                        wazo_ctx = (
                            part_attrs.get("sip.h.X-Wazo-Tenant-Context")
                            or part_attrs.get("X-Wazo-Tenant-Context")
                            or l_attrs.get("sip.h.x-wazo-tenant-context")
                            or l_attrs.get("x-wazo-tenant-context")
                            or ""
                        )
                        caller_ext = (
                            part_attrs.get("sip.h.X-Wazo-Caller-Ext")
                            or part_attrs.get("X-Wazo-Caller-Ext")
                            or l_attrs.get("sip.h.x-wazo-caller-ext")
                            or l_attrs.get("x-wazo-caller-ext")
                            or part_attrs.get("sip.callerId")
                            or l_attrs.get("sip.callerid")
                            or ""
                        )

                    # Fallback: extract caller_ext from room_name (e.g. sip_999__110_xyz) or participant_identity (sip_110)
                    if not caller_ext:
                        if "__" in room_name:
                            try:
                                candidate = room_name.split("__", 1)[1].split("_")[0]
                                if candidate.isdigit() and len(candidate) <= 6:
                                    caller_ext = candidate
                            except Exception:
                                pass
                        if not caller_ext and str(participant_identity).startswith("sip_"):
                            cand = str(participant_identity).replace("sip_sip_", "").replace("sip_", "").split("@")[0]
                            if cand.isdigit() and len(cand) <= 6:
                                caller_ext = cand

                    # 1. Check if this is an internal employee call (e.g. dialed 999 or has Wazo Context)
                    if call_to in ("999", "sip:999") or "999" in room_name or wazo_ctx or (caller_ext and len(caller_ext) <= 4):
                        tenant_u, emp_prof, ext_prof = resolve_tenant_from_context_and_ext(wazo_ctx, caller_ext)
                        if tenant_u:
                            user_id = tenant_u.id
                            if ext_prof and not profile:
                                profile = ext_prof.to_dict()
                            try:
                                r = redis.Redis.from_url(settings.REDIS_URL)
                                r.set(f"is_internal_test:{room_name}", "1", ex=7200)
                                if caller_ext:
                                    r.set(f"caller_ext:{room_name}", caller_ext, ex=7200)
                            except Exception:
                                pass

                    # 2. Check external DID resolution
                    if not user_id:
                        if not call_to:
                            for p_token in parts:
                                if p_token.startswith("+") or (p_token.isdigit() and len(p_token) >= 7):
                                    call_to = p_token
                                    break
                        if call_to:
                            tenant_u, did_prof = resolve_tenant_from_did(call_to)
                            if tenant_u:
                                user_id = tenant_u.id
                                if did_prof and not profile:
                                    profile = did_prof.to_dict()

                    if not user_id and participant_identity.startswith("sip_"):
                        raw_sip_id = participant_identity.replace("sip_sip_", "").replace("sip_", "").split("@")[0]
                        tenant_u, did_prof = resolve_tenant_from_did(raw_sip_id)
                        if tenant_u:
                            user_id = tenant_u.id
                            if did_prof and not profile:
                                profile = did_prof.to_dict()
                except Exception as did_err:
                    logger.warning(f"Error resolving tenant in livekit_webhook: {did_err}")

            if user_id and not profile:
                if "_pbx_" in room_name:
                    try:
                        p_idx = parts.index("pbx")
                        if len(parts) > p_idx + 1 and parts[p_idx + 1].isdigit():
                            pbx_t = InboundPBXTrunk.objects.filter(id=int(parts[p_idx + 1])).select_related('target_profile').first()
                            if pbx_t and pbx_t.target_profile:
                                profile = pbx_t.target_profile.to_dict()
                    except Exception:
                        pass
                if not profile:
                    active_prof = AgentProfile.objects.filter(user_id=user_id, is_active=True).first()
                    if active_prof:
                        profile = active_prof.to_dict()

            # Pre-call Wallet Balance Guard
            if user_id:
                try:
                    from decimal import Decimal
                    from billing.models import BillingConfig, UserWallet
                    from partners.models import PartnerClientRelationship
                    b_cfg = BillingConfig.get_config()
                    min_bal = b_cfg.min_balance_to_call

                    partner_rel = PartnerClientRelationship.objects.select_related('partner__user').filter(
                        client_id=user_id, partner__status='approved'
                    ).first()
                    check_user_id = partner_rel.partner.user_id if partner_rel and partner_rel.partner else user_id
                    u_wallet = UserWallet.objects.filter(user_id=check_user_id).first()
                    curr_bal = u_wallet.balance if u_wallet else Decimal('0.0000')

                    if curr_bal < min_bal:
                        logger.warning(f"[PRE-CALL GUARD] Suppressing AI in room '{room_name}': insufficient balance ({curr_bal} < {min_bal}) for user #{check_user_id}")
                        publish_to_centrifugo(channel, {
                            "event": "agent_error",
                            "message": "عفواً، رصيد المحفظة غير كافٍ لإجراء أو استقبال المكالمات الصوتية بالذكاء الاصطناعي.",
                            "timestamp": time.time(),
                        })
                        return HttpResponse("insufficient_balance", status=200)
                except Exception as w_err:
                    logger.warning(f"Error checking pre-call wallet balance for user #{user_id}: {w_err}")

            pending_dest = None
            if participant_identity.startswith("sip_"):
                clean = participant_identity.replace("sip_sip_", "sip_")
                try:
                    r = redis.Redis.from_url(settings.REDIS_URL)
                    p_val = r.get(f"pending_outbound_dial:{clean}") or r.get(f"pending_outbound_dial:{participant_identity}")
                    if p_val:
                        pending_dest = p_val.decode() if isinstance(p_val, bytes) else str(p_val)
                        r.delete(f"pending_outbound_dial:{clean}")
                        r.delete(f"pending_outbound_dial:{participant_identity}")
                except Exception as ex:
                    logger.warning(f"Error checking pending outbound dial in Redis: {ex}")

            if pending_dest and user_id:
                trunk = OutboundSIPTrunk.objects.filter(user_id=user_id, is_active=True, is_default=True).first()
                if not trunk:
                    trunk = OutboundSIPTrunk.objects.filter(user_id=user_id, is_active=True).first()

                if trunk and trunk.livekit_outbound_trunk_id:
                    CallSession.objects.create(
                        user_id=user_id,
                        room_name=room_name,
                        direction='outbound_agent',
                        destination_phone=pending_dest,
                        call_goal=f"مكالمة موظف مباشرة عبر MicroSIP للرقم {pending_dest}"
                    )
                    import asyncio
                    try:
                        asyncio.run(_async_dial_sip_participant(
                            trunk_id=trunk.livekit_outbound_trunk_id,
                            destination_phone=pending_dest,
                            room_name=room_name,
                            caller_id=trunk.caller_id
                        ))
                        logger.info(f"Direct MicroSIP outbound call bridged to {pending_dest} in room {room_name}")
                    except Exception as de:
                        logger.error(f"Failed to bridge outbound participant: {de}")

                try:
                    r = redis.Redis.from_url(settings.REDIS_URL)
                    clean = participant_identity.replace("sip_sip_", "sip_")
                    r.set(f"agent_room:{participant_identity}", room_name, ex=7200)
                    r.set(f"agent_room:{clean}", room_name, ex=7200)
                except Exception:
                    pass
                return HttpResponse("ok")

            if "_ai_out_" in room_name or "_agent_out_" in room_name:
                logger.info(f"Participant joined outbound room {room_name}. Already dispatched.")
                return HttpResponse("ok")

            caller_phone = meta_caller_phone or 'web_dashboard'
            if participant_identity.startswith("sip_"):
                raw_sip = participant_identity.replace("sip_sip_", "").replace("sip_", "")
                raw_sip = raw_sip.split("@")[0].replace("sip:", "")
                if raw_sip:
                    caller_phone = raw_sip
            elif participant_identity.startswith("customer_"):
                caller_phone = participant_identity.replace("customer_", "")

            # Check Business Hours Schedule
            is_off_hours = False
            off_hours_data = None
            if user_id:
                try:
                    from telephony.models import BusinessHoursSchedule
                    b_sched = BusinessHoursSchedule.objects.filter(user_id=user_id).first()
                    if b_sched and b_sched.is_enabled and not b_sched.is_within_business_hours():
                        is_off_hours = True
                        off_hours_data = {
                            "action_type": b_sched.action_type,
                            "ai_message": b_sched.ai_message,
                            "audio_file_url": b_sched.get_audio_url(request),
                            "voice_name": (profile.get("voice_name") if profile else "Aoede") or "Aoede"
                        }
                        logger.info(f"Incoming call in room '{room_name}' is OUTSIDE business hours for user #{user_id}. Action: {b_sched.action_type}")
                except Exception as b_err:
                    logger.warning(f"Error checking business hours for user #{user_id}: {b_err}")

            logger.info(f"Human participant '{participant_identity}' (user_id={user_id}, caller_phone={caller_phone}, is_queue={is_queue}, is_off_hours={is_off_hours}) joined room {room_name}. Queuing Voice Agent...")
            if is_off_hours:
                publish_to_centrifugo(channel, {
                    "event": "off_hours_call",
                    "message": "المكالمة واردة خارج أوقات العمل الرسمية. جاري الرد بالخطة المحددة...",
                    "timestamp": time.time(),
                })
            else:
                publish_to_centrifugo(channel, {
                    "event": "agent_queued",
                    "message": f"تم رصد انضمام متصل لطابور الانتظار (كود: {queue_code})..." if is_queue else "تم رصد انضمام المستخدم. جاري استدعاء المساعد الصوتي وتجهيز قاعدة المستندات...",
                    "timestamp": time.time(),
                })

            try:
                r = redis.Redis.from_url(settings.REDIS_URL)
                job_payload = json.dumps({
                    "room_name": room_name,
                    "user_id": user_id,
                    "caller_phone": caller_phone,
                    "profile": profile,
                    "is_queue": is_queue,
                    "queue_code": queue_code,
                    "queue_data": queue_data,
                    "participant_identity": participant_identity,
                    "is_off_hours": is_off_hours,
                    "off_hours_data": off_hours_data
                })
                r.rpush("agent_jobs", job_payload)
                if participant_identity.startswith("sip_"):
                    clean = participant_identity.replace("sip_sip_", "sip_")
                    r.set(f"agent_room:{participant_identity}", room_name, ex=7200)
                    r.set(f"agent_room:{clean}", room_name, ex=7200)
                logger.info(f"Dispatched job {job_payload} to Redis 'agent_jobs' queue.")
            except Exception as ex:
                logger.error(f"Failed to dispatch room '{room_name}' to Redis: {ex}")

    elif event_type == "participant_left":
        participant_identity = event.participant.identity
        if participant_identity not in ("ai-agent", "pipecat-agent"):
            publish_to_centrifugo(channel, {
                "event": "user_left",
                "message": "المستخدم غادر الغرفة",
                "timestamp": time.time(),
            })
            if participant_identity.startswith("sip_"):
                try:
                    clean = participant_identity.replace("sip_sip_", "sip_")
                    r = redis.Redis.from_url(settings.REDIS_URL)
                    r.set(f"agent_state:{participant_identity}", "AVAILABLE")
                    r.set(f"agent_state:{clean}", "AVAILABLE")
                    r.delete(f"agent_room:{participant_identity}")
                    r.delete(f"agent_room:{clean}")
                    publish_to_centrifugo("presence_updates", {
                        "event": "agent_presence",
                        "sip_username": participant_identity,
                        "state": "AVAILABLE"
                    })
                except Exception:
                    pass

    elif event_type == "room_finished":
        logger.info(f"Room {room_name} finished.")
        try:
            from crm.models import CallSession, CampaignContact
            from crm.inngest_jobs import schedule_contact_retry
            import datetime

            session = CallSession.objects.filter(room_name=room_name, ended_at__isnull=True).first()
            if session:
                logger.info(f"[WEBHOOK] Finalizing unclosed CallSession #{session.id} for finished room '{room_name}'")
                session.ended_at = datetime.datetime.now(datetime.timezone.utc)
                session.duration_seconds = 0
                session.summary = session.summary or "انتهت المكالمة دون رد من الطرف الآخر."
                session.save(update_fields=['ended_at', 'duration_seconds', 'summary'])

                contact = CampaignContact.objects.filter(call_session=session).first()
                if not contact and session.destination_phone and session.user:
                    contact = CampaignContact.objects.filter(
                        campaign__user=session.user,
                        phone_number=session.destination_phone
                    ).exclude(call_status='answered').first()

                if contact and contact.call_status != 'answered':
                    contact.call_status = 'no_answer'
                    contact.interest_level = 'unreached'
                    contact.call_summary = "لم يرد العميل على الاتصال."
                    contact.call_session = session
                    contact.save(update_fields=['call_status', 'interest_level', 'call_summary', 'call_session', 'updated_at'])
                    contact.campaign.update_metrics()
                    schedule_contact_retry(contact.id)
        except Exception as rf_err:
            logger.warning(f"Error handling room_finished cleanup for room '{room_name}': {rf_err}")

    elif event_type == "egress_ended":
        egress_info = getattr(event, 'egress_info', None)
        if egress_info:
            r_name = getattr(egress_info, 'room_name', '')
            egress_id = getattr(egress_info, 'egress_id', '')
            status = str(getattr(egress_info, 'status', ''))
            logger.info(f"LiveKit Egress Ended: id={egress_id}, room={r_name}, status={status}")

            file_results = getattr(egress_info, 'file_results', [])
            rec_url = ""
            duration_sec = 0
            file_size = 0

            if file_results:
                f0 = file_results[0]
                fname = getattr(f0, 'filename', '')
                loc = getattr(f0, 'location', '')
                file_size = getattr(f0, 'size', 0)
                dur_ns = getattr(f0, 'duration', 0)
                if dur_ns:
                    duration_sec = int(dur_ns / 1_000_000_000)

                # Store internal proxy URL for seamless cross-network streaming
                if fname:
                    clean_f = fname.lstrip('/')
                    rec_url = f"/api/calls/recordings/{clean_f}"
                elif loc:
                    rec_url = loc

            if r_name and rec_url:
                try:
                    from crm.models import CallSession
                    updated = CallSession.objects.filter(room_name=r_name).update(
                        recording_url=rec_url
                    )
                    logger.info(f"Updated CallSession recording_url for room '{r_name}' ({updated} records updated): {rec_url}")
                except Exception as db_err:
                    logger.error(f"Error updating CallSession for room '{r_name}': {db_err}")

                try:
                    from call_center.models import EmployeeCallLog
                    emp_updated = EmployeeCallLog.objects.filter(room_name=r_name).update(
                        recording_url=rec_url
                    )
                    logger.info(f"Updated EmployeeCallLog recording_url for room '{r_name}' ({emp_updated} records updated): {rec_url}")
                except Exception as emp_db_err:
                    logger.error(f"Error updating EmployeeCallLog for room '{r_name}': {emp_db_err}")

                try:
                    r = redis.Redis.from_url(settings.REDIS_URL)
                    r.set(f"recording_url:{r_name}", rec_url, ex=86400)
                except Exception as red_err:
                    logger.warning(f"Error caching recording_url in Redis: {red_err}")

                publish_to_centrifugo(f"rooms:{r_name}", {
                    "event": "recording_ready",
                    "recording_url": rec_url,
                    "duration_seconds": duration_sec,
                    "file_size": file_size,
                    "timestamp": time.time()
                })

    return HttpResponse("ok")


@csrf_exempt
def stream_call_recording(request, filename):
    """
    Stream call recording from internal MinIO storage to browser/client.
    Supports range headers for smooth scrubbing in audio players.
    """
    import requests
    from django.http import StreamingHttpResponse, Http404

    minio_endpoint = getattr(settings, 'MINIO_ENDPOINT', 'http://minio:9000')
    bucket = getattr(settings, 'MINIO_BUCKET_NAME', 'call-recordings')
    clean_filename = filename.lstrip('/')
    minio_url = f"{minio_endpoint}/{bucket}/{clean_filename}"

    try:
        headers = {}
        if 'HTTP_RANGE' in request.META:
            headers['Range'] = request.META['HTTP_RANGE']

        upstream_resp = requests.get(minio_url, headers=headers, stream=True, timeout=10)
        if upstream_resp.status_code in [200, 206]:
            response = StreamingHttpResponse(
                upstream_resp.iter_content(chunk_size=8192),
                status=upstream_resp.status_code,
                content_type=upstream_resp.headers.get('Content-Type', 'audio/mpeg')
            )
            for h in ['Content-Length', 'Content-Range', 'Accept-Ranges', 'ETag', 'Last-Modified']:
                if h in upstream_resp.headers:
                    response[h] = upstream_resp.headers[h]
            return response
        elif upstream_resp.status_code == 404:
            return HttpResponse("Recording not found", status=404)
        else:
            return HttpResponse("Error fetching recording", status=upstream_resp.status_code)
    except Exception as e:
        logger.error(f"Error streaming recording {filename}: {e}")
        return HttpResponse(f"Error streaming recording: {e}", status=500)


@login_required
def calls_page_view(request):
    """Render dedicated Call Detail Records & Recordings page."""
    context = {
        'page_title': 'سجل المكالمات (CDR) والتسجيلات',
        'page_icon': '📋',
        'active_nav': 'calls',
    }
    return render(request, 'voice_assistant/pages/calls.html', context)


@login_required
def billing_page_view(request):
    """Render dedicated Usage & Billing page."""
    context = {
        'page_title': 'الرصيد والفواتير',
        'page_icon': '💳',
        'active_nav': 'billing',
    }
    return render(request, 'voice_assistant/pages/billing.html', context)


@login_required
def crm_page_view(request):
    """Render dedicated CRM & Customer Memory page."""
    context = {
        'page_title': 'ذاكرة وسجل العملاء',
        'page_icon': '🧠',
        'active_nav': 'crm',
    }
    return render(request, 'voice_assistant/pages/crm.html', context)


@login_required
def rag_page_view(request):
    """Render dedicated Knowledge Base RAG page."""
    context = {
        'page_title': 'قاعدة المعرفة RAG',
        'page_icon': '📚',
        'active_nav': 'rag',
    }
    return render(request, 'voice_assistant/pages/rag.html', context)


@login_required
def personas_page_view(request):
    """Render dedicated AI Personas & Voice Studio page."""
    context = {
        'page_title': 'الشخصيات واللهجات',
        'page_icon': '🎭',
        'active_nav': 'personas',
    }
    return render(request, 'voice_assistant/pages/personas.html', context)


@login_required
def campaigns_page_view(request):
    """Render dedicated Outbound Campaigns & Leads CRM page."""
    context = {
        'page_title': 'حملات الاتصال والعملاء',
        'page_icon': '🚀',
        'active_nav': 'campaigns',
    }
    return render(request, 'voice_assistant/pages/campaigns.html', context)


@login_required
def store_page_view(request):
    """Render dedicated Tools & MCP Store page."""
    context = {
        'page_title': 'متجر وأدوات MCP',
        'page_icon': '🛍️',
        'active_nav': 'store',
    }
    return render(request, 'voice_assistant/pages/store.html', context)


@login_required
def developer_page_view(request):
    """Render dedicated Developer API Portal page."""
    context = {
        'page_title': 'واجهات المطورين (API)',
        'page_icon': '⚡',
        'active_nav': 'developer',
    }
    return render(request, 'voice_assistant/pages/developer.html', context)


@login_required
def callcenter_page_view(request):
    """Render dedicated Call Center & Queues page."""
    context = {
        'page_title': 'المركز الهاتفي وطوابير الانتظار',
        'page_icon': '🎧',
        'active_nav': 'callcenter',
    }
    return render(request, 'voice_assistant/pages/callcenter.html', context)


@login_required
def telephony_page_view(request):
    """Render dedicated Telephony & PBX Trunks page."""
    context = {
        'page_title': 'الاتصالات وسنترالات PBX',
        'page_icon': '📞',
        'active_nav': 'telephony',
    }
    return render(request, 'voice_assistant/pages/telephony.html', context)


@login_required
def partner_page_view(request):
    """Render dedicated Partner & SaaS Portal page."""
    context = {
        'page_title': 'بوابة الشركاء وحلول الـ SaaS',
        'page_icon': '💼',
        'active_nav': 'partner',
    }
    return render(request, 'voice_assistant/pages/partner.html', context)


@login_required
def business_hours_page_view(request):
    """Render dedicated Business Hours & Off-Hours Schedule page."""
    context = {
        'page_title': 'مواعيد العمل والخطة البديلة',
        'page_icon': '⏰',
        'active_nav': 'business_hours',
    }
    return render(request, 'voice_assistant/pages/business_hours.html', context)


@login_required
def coworker_page_view(request):
    """Render dedicated Autonomous Digital Coworker management page."""
    from agents.models import DigitalCoworkerConfig
    cfg = DigitalCoworkerConfig.get_or_create_config(request.user)
    context = {
        'page_title': 'الموظف الرقمي الذكي المستقل',
        'page_icon': '🤖',
        'active_nav': 'coworker',
        'coworker_config': cfg.to_dict(),
    }
    return render(request, 'voice_assistant/pages/coworker.html', context)



@login_required
def get_business_hours(request):
    """GET /api/business-hours/ - Retrieve user business hours configuration."""
    from telephony.models import BusinessHoursSchedule
    sched, _ = BusinessHoursSchedule.objects.get_or_create(user=request.user)
    return JsonResponse({
        "status": "success",
        "schedule": sched.to_dict(request)
    })


@login_required
def save_business_hours(request):
    """POST /api/business-hours/save/ - Save business hours configuration with optional audio upload."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    from telephony.models import BusinessHoursSchedule
    sched, _ = BusinessHoursSchedule.objects.get_or_create(user=request.user)

    is_json = request.content_type == 'application/json'
    if is_json:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)
    else:
        data = request.POST

    if 'is_enabled' in data:
        val = data['is_enabled']
        sched.is_enabled = val in (True, 'true', 'True', '1', 1)

    if 'timezone' in data and str(data['timezone']).strip():
        sched.timezone = str(data['timezone']).strip()

    if 'days_config' in data:
        cfg = data['days_config']
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:
                cfg = None
        if isinstance(cfg, dict):
            sched.days_config = cfg

    if 'action_type' in data and data['action_type'] in ('ai_message', 'audio_file'):
        sched.action_type = data['action_type']

    if 'ai_message' in data:
        sched.ai_message = str(data['ai_message']).strip()

    if 'audio_file_url' in data:
        sched.audio_file_url = str(data['audio_file_url']).strip()

    # Handle audio file upload (Dashboard only)
    if 'audio_file' in request.FILES:
        uploaded_file = request.FILES['audio_file']
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in ('.mp3', '.wav', '.ogg', '.m4a'):
            return JsonResponse({"status": "error", "message": "يجب رفع ملف صوتي بصيغة MP3 أو WAV أو OGG أو M4A"}, status=400)
        sched.audio_file = uploaded_file

    sched.save()

    return JsonResponse({
        "status": "success",
        "message": "تم حفظ جدول مواعيد العمل بنجاح",
        "schedule": sched.to_dict(request)
    })



