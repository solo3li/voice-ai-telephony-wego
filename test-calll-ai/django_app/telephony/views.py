import re
import json
import uuid
import logging
import asyncio
import redis
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from livekit import api

from .models import OutboundSIPTrunk, InboundPBXTrunk
from agents.models import AgentProfile
from call_center.models import CallQueue
from crm.models import CallSession
from .services import initiate_outbound_call, normalize_phone_number, _async_dial_sip_participant

logger = logging.getLogger(__name__)

def normalize_phone_number(raw_phone: str) -> str:
    """
    Normalize phone numbers into standard E.164 format.
    - Egyptian mobile (01xxxxxxxxx, 11 digits) -> +201xxxxxxxxx
    - Egyptian mobile with 20 prefix (201xxxxxxxxx) -> +201xxxxxxxxx
    - International with 00 prefix (00...) -> +...
    - International standard (+...) -> preserved
    - Clean digits starting with non-zero country code -> +...
    """
    cleaned = re.sub(r'[\s\-\(\)\.]', '', str(raw_phone or '').strip())
    if not cleaned:
        return ""
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]
    elif cleaned.startswith('01') and len(cleaned) == 11 and cleaned.isdigit():
        cleaned = '+20' + cleaned[1:]
    elif cleaned.startswith('201') and len(cleaned) == 12 and cleaned.isdigit():
        cleaned = '+' + cleaned
    elif not cleaned.startswith('+') and re.match(r'^[1-9]\d{6,14}$', cleaned):
        cleaned = '+' + cleaned
    return cleaned


async def _async_create_or_update_outbound_trunk(name, address, port, transport_str, auth_username, auth_password, caller_id, existing_trunk_id=None):
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        trans_map = {
            'UDP': api.SIPTransport.SIP_TRANSPORT_UDP,
            'TCP': api.SIPTransport.SIP_TRANSPORT_TCP,
            'TLS': api.SIPTransport.SIP_TRANSPORT_TLS,
        }
        trans_enum = trans_map.get(str(transport_str).upper(), api.SIPTransport.SIP_TRANSPORT_UDP)

        full_address = address.strip()
        if ":" not in full_address and port:
            full_address = f"{full_address}:{port}"

        numbers = [caller_id.strip()] if caller_id and caller_id.strip() else ['*']

        if existing_trunk_id:
            try:
                await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=existing_trunk_id))
            except Exception as e:
                logger.warning(f"Failed to delete prior outbound trunk {existing_trunk_id}: {e}")

        trunk_info = api.SIPOutboundTrunkInfo(
            name=name,
            address=full_address,
            transport=trans_enum,
            numbers=numbers,
            auth_username=auth_username.strip() if auth_username else "",
            auth_password=auth_password.strip() if auth_password else "",
        )
        req = api.CreateSIPOutboundTrunkRequest(trunk=trunk_info)
        created = await lk.sip.create_sip_outbound_trunk(req)
        return created.sip_trunk_id
    finally:
        await lk.aclose()


async def _async_delete_outbound_trunk(trunk_id):
    if not trunk_id:
        return
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=trunk_id))
    except Exception as e:
        logger.warning(f"Error deleting LiveKit outbound trunk {trunk_id}: {e}")
    finally:
        await lk.aclose()


async def _async_dial_sip_participant(trunk_id, destination_phone, room_name, caller_id=None):
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        req = api.CreateSIPParticipantRequest(
            sip_trunk_id=trunk_id,
            sip_call_to=destination_phone,
            room_name=room_name,
            sip_number=caller_id or "",
            participant_identity=f"customer_{destination_phone}",
            participant_name=f"عميل ({destination_phone})",
            play_dialtone=True,
        )
        return await lk.sip.create_sip_participant(req)
    finally:
        await lk.aclose()


@login_required(login_url='/login/')
def get_outbound_trunk(request):
    """Retrieve default/active Outbound SIP Trunk for current user."""
    trunk = OutboundSIPTrunk.objects.filter(user=request.user, is_default=True).first()
    if not trunk:
        trunk = OutboundSIPTrunk.objects.filter(user=request.user).first()

    return JsonResponse({
        "status": "success",
        "has_trunk": trunk is not None,
        "trunk": trunk.to_dict() if trunk else None,
        "providers_guide": [
            {
                "name": "Telnyx",
                "host": "sip.telnyx.com",
                "port": 5060,
                "transport": "UDP",
                "docs": "أنشئ Outbound SIP Connection وضع بيانات الـ SIP Credentials هنا ورقم هاتفك في Caller ID."
            },
            {
                "name": "Twilio Elastic SIP Trunking",
                "host": "{your-trunk}.pstn.twilio.com",
                "port": 5060,
                "transport": "UDP",
                "docs": "أنشئ Elastic SIP Trunk وضع Termination SIP URI وبيانات المصادقة ورقم هاتفك المشترى."
            },
            {
                "name": "Generic / Any SIP Provider",
                "host": "sip.provider.com",
                "port": 5060,
                "transport": "UDP",
                "docs": "يدعم النظام أي خادم SIP خارجي متوافق مع معايير RFC 3261."
            }
        ]
    })


@login_required(login_url='/login/')
def save_outbound_trunk(request):
    """Save or update Outbound SIP Trunk and provision in LiveKit."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        name = (data.get('name') or 'حساب المزود الخارجي (Generic SIP Trunk)').strip()
        sip_host = (data.get('sip_host') or '').strip()
        sip_port = int(data.get('sip_port') or 5060)
        transport = (data.get('transport') or 'UDP').strip().upper()
        auth_username = (data.get('auth_username') or '').strip()
        auth_password = (data.get('auth_password') or '').strip()
        caller_id_raw = (data.get('caller_id') or '').strip()

        if not sip_host:
            return JsonResponse({"status": "error", "message": "عنوان الخادم (SIP Host) مطلوب"}, status=400)

        caller_id = normalize_phone_number(caller_id_raw) if caller_id_raw else ""

        # Find existing default trunk or create new
        existing_trunk = OutboundSIPTrunk.objects.filter(user=request.user).first()
        # If user didn't enter password on update, keep existing password
        plain_password_for_lk = auth_password
        if not auth_password and existing_trunk:
            plain_password_for_lk = existing_trunk.get_auth_password()

        lk_trunk_id = asyncio.run(_async_create_or_update_outbound_trunk(
            name=name,
            address=sip_host,
            port=sip_port,
            transport_str=transport,
            auth_username=auth_username,
            auth_password=plain_password_for_lk,
            caller_id=caller_id,
            existing_trunk_id=existing_trunk_id
        ))

        if existing_trunk:
            existing_trunk.name = name
            existing_trunk.sip_host = sip_host
            existing_trunk.sip_port = sip_port
            existing_trunk.transport = transport
            existing_trunk.auth_username = auth_username
            if auth_password:
                existing_trunk.set_auth_password(auth_password)
            existing_trunk.caller_id = caller_id
            existing_trunk.livekit_outbound_trunk_id = lk_trunk_id
            existing_trunk.is_active = True
            existing_trunk.is_default = True
            existing_trunk.save()
            trunk_obj = existing_trunk
        else:
            trunk_obj = OutboundSIPTrunk(
                user=request.user,
                name=name,
                sip_host=sip_host,
                sip_port=sip_port,
                transport=transport,
                auth_username=auth_username,
                caller_id=caller_id,
                livekit_outbound_trunk_id=lk_trunk_id,
                is_active=True,
                is_default=True
            )
            trunk_obj.set_auth_password(auth_password)
            trunk_obj.save()

        # Cache default outbound trunk in Redis for fast access by sip_proxy and workers
        try:
            r = redis.Redis.from_url(settings.REDIS_URL)
            r.set(f"user_outbound_trunk:{request.user.id}", json.dumps({
                "trunk_id": lk_trunk_id,
                "caller_id": caller_id,
                "sip_host": sip_host
            }))
        except Exception:
            pass

        return JsonResponse({
            "status": "success",
            "message": f"تم تسجيل الجذع الخارجي '{name}' بنجاح وربطه بخادم LiveKit (معرف الجذع: {lk_trunk_id})",
            "trunk": trunk_obj.to_dict()
        })

    except Exception as e:
        logger.error(f"Error saving outbound trunk: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": f"فشل تسجيل الجذع الخارجي: {str(e)}"}, status=500)


@login_required(login_url='/login/')
def delete_outbound_trunk(request, trunk_id):
    """Delete an Outbound SIP Trunk."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    trunk = get_object_or_404(OutboundSIPTrunk, id=trunk_id, user=request.user)
    try:
        asyncio.run(_async_delete_outbound_trunk(trunk.livekit_outbound_trunk_id))
    except Exception as e:
        logger.warning(f"Error deleting trunk {trunk.livekit_outbound_trunk_id}: {e}")

    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.delete(f"user_outbound_trunk:{request.user.id}")
    except Exception:
        pass

    name = trunk.name
    trunk.delete()
    return JsonResponse({
        "status": "success",
        "message": f"تم حذف الجذع الخارجي '{name}' بنجاح."
    })


@csrf_exempt
@login_required(login_url='/login/')
def trigger_ai_outbound_call(request):
    """Initiate an autonomous outbound AI call to a destination phone number or internal extension."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        raw_phone = (data.get('phone_number') or '').strip()
        call_goal = (data.get('call_goal') or '').strip()
        profile_id = data.get('profile_id')
        gateway_type = (data.get('gateway_type') or 'auto').strip()
        gateway_id = data.get('gateway_id')

        res = initiate_outbound_call(
            user=request.user,
            phone_number=raw_phone,
            call_goal=call_goal,
            profile_id=profile_id,
            gateway_type=gateway_type,
            gateway_id=gateway_id,
        )
        http_status = res.pop('http_status', 200)
        return JsonResponse(res, status=http_status)

    except Exception as e:
        logger.error(f"Error triggering AI outbound call: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": f"فشل بدء المكالمة الصادرة: {str(e)}"}, status=500)


@login_required(login_url='/login/')
def list_outbound_gateways(request):
    """List all available outbound dialing routes (Cloud Generic Trunk + PBX Trunks with outbound enabled)."""
    gateways = []

    # 1. Cloud Provider (Telnyx / Twilio)
    cloud_trunk = OutboundSIPTrunk.objects.filter(user=request.user, is_active=True).first()
    if cloud_trunk and cloud_trunk.livekit_outbound_trunk_id:
        gateways.append({
            "type": "cloud",
            "id": cloud_trunk.id,
            "name": f"🌐 {cloud_trunk.name} (مزود سحابي مباشر)",
            "caller_id": cloud_trunk.caller_id or "",
            "is_default": cloud_trunk.is_default
        })

    # 2. PBX Trunks with outbound enabled
    pbx_trunks = InboundPBXTrunk.objects.filter(user=request.user, is_active=True, enable_outbound=True)
    for pt in pbx_trunks:
        if pt.livekit_outbound_trunk_id:
            first_num = pt.inbound_numbers.split(',')[0].strip() if pt.inbound_numbers else ""
            gateways.append({
                "type": "pbx",
                "id": pt.id,
                "name": f"🏢 سنترال {pt.name} (خطوط محلية / PRI / GSM)",
                "caller_id": first_num,
                "is_default": pt.is_default_outbound
            })

    default_gw = next((g for g in gateways if g.get('is_default')), gateways[0] if gateways else None)

    return JsonResponse({
        "status": "success",
        "gateways": gateways,
        "default_gateway": default_gw
    })


# ==================== Bidirectional PBX (Issabel / Asterisk) Integration ====================

async def _async_create_pbx_inbound_trunk_and_rule(
    name, auth_mode, pbx_ip, auth_username, auth_password, inbound_numbers_str,
    destination_type, target_queue_code, user_id, trunk_db_id,
    existing_trunk_id=None, existing_rule_id=None,
    enable_outbound=True, outbound_port=5060, outbound_transport='UDP',
    existing_outbound_trunk_id=None
):
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    trunk_id = ""
    rule_id = ""
    outbound_trunk_id = ""
    try:
        if existing_rule_id:
            try:
                await lk.sip.delete_sip_dispatch_rule(api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=existing_rule_id))
            except Exception as ex:
                logger.warning(f"Error cleaning prior dispatch rule {existing_rule_id}: {ex}")
        if existing_trunk_id:
            try:
                await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=existing_trunk_id))
            except Exception as ex:
                logger.warning(f"Error cleaning prior inbound trunk {existing_trunk_id}: {ex}")
        if existing_outbound_trunk_id:
            try:
                await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=existing_outbound_trunk_id))
            except Exception as ex:
                logger.warning(f"Error cleaning prior outbound trunk {existing_outbound_trunk_id}: {ex}")

        numbers = [n.strip() for n in inbound_numbers_str.split(",") if n.strip()] if inbound_numbers_str else []
        allowed_addresses = [pbx_ip.strip()] if auth_mode == 'ip' and pbx_ip and pbx_ip.strip() else []
        u_name = auth_username.strip() if auth_mode == 'credentials' and auth_username else ""
        u_pass = auth_password.strip() if auth_mode == 'credentials' and auth_password else ""

        # 1. Inbound Trunk
        trunk_info = api.SIPInboundTrunkInfo(
            name=f"PBX Inbound {trunk_db_id} - {name} (User {user_id})",
            numbers=numbers,
            allowed_addresses=allowed_addresses,
            auth_username=u_name,
            auth_password=u_pass,
        )
        created_trunk = await lk.sip.create_sip_inbound_trunk(api.CreateSIPInboundTrunkRequest(trunk=trunk_info))
        trunk_id = created_trunk.sip_trunk_id

        # 2. Dispatch Rule
        if destination_type in ('call_queue', 'queue') and target_queue_code:
            room_prefix = f"room_user_{user_id}_queue_{target_queue_code}_pbx_{trunk_db_id}_"
        else:
            room_prefix = f"room_user_{user_id}_pbx_{trunk_db_id}_"

        rule_req = api.CreateSIPDispatchRuleRequest(
            name=f"Rule for PBX {trunk_db_id} - {name}",
            trunk_ids=[trunk_id],
            rule=api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix=room_prefix
                )
            )
        )
        created_rule = await lk.sip.create_sip_dispatch_rule(rule_req)
        rule_id = created_rule.sip_dispatch_rule_id

        # 3. Outbound Trunk (if enabled and pbx_ip is set)
        if enable_outbound and pbx_ip and pbx_ip.strip():
            trans_map = {
                'UDP': api.SIPTransport.SIP_TRANSPORT_UDP,
                'TCP': api.SIPTransport.SIP_TRANSPORT_TCP,
                'TLS': api.SIPTransport.SIP_TRANSPORT_TLS,
            }
            trans_enum = trans_map.get(str(outbound_transport).upper(), api.SIPTransport.SIP_TRANSPORT_UDP)
            full_addr = pbx_ip.strip()
            if ":" not in full_addr and outbound_port:
                full_addr = f"{full_addr}:{outbound_port}"

            outbound_nums = list(numbers)
            if '*' not in outbound_nums:
                outbound_nums.append('*')

            out_trunk_info = api.SIPOutboundTrunkInfo(
                name=f"PBX Outbound {trunk_db_id} - {name} (User {user_id})",
                address=full_addr,
                transport=trans_enum,
                numbers=outbound_nums,
                auth_username=u_name,
                auth_password=u_pass,
            )
            created_out = await lk.sip.create_sip_outbound_trunk(api.CreateSIPOutboundTrunkRequest(trunk=out_trunk_info))
            outbound_trunk_id = created_out.sip_trunk_id

        return trunk_id, rule_id, outbound_trunk_id
    except Exception:
        if rule_id:
            try:
                await lk.sip.delete_sip_dispatch_rule(api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=rule_id))
            except Exception:
                pass
        if trunk_id:
            try:
                await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=trunk_id))
            except Exception:
                pass
        if outbound_trunk_id:
            try:
                await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=outbound_trunk_id))
            except Exception:
                pass
        raise
    finally:
        await lk.aclose()


async def _async_delete_pbx_trunk_and_rule(trunk_id, rule_id, outbound_trunk_id=None):
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        if rule_id:
            try:
                await lk.sip.delete_sip_dispatch_rule(api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=rule_id))
            except Exception as ex:
                logger.warning(f"Error deleting dispatch rule {rule_id}: {ex}")
        if trunk_id:
            try:
                await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=trunk_id))
            except Exception as ex:
                logger.warning(f"Error deleting inbound trunk {trunk_id}: {ex}")
        if outbound_trunk_id:
            try:
                await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=outbound_trunk_id))
            except Exception as ex:
                logger.warning(f"Error deleting outbound trunk {outbound_trunk_id}: {ex}")
    finally:
        await lk.aclose()


@login_required(login_url='/login/')
def list_pbx_trunks(request):
    """List all Inbound PBX Trunks for the authenticated user with generated Issabel config."""
    trunks = InboundPBXTrunk.objects.filter(user=request.user).select_related('target_queue', 'target_profile')
    host_domain = getattr(settings, 'SIP_PUBLIC_DOMAIN', request.get_host().split(':')[0])
    return JsonResponse({
        "status": "success",
        "trunks": [t.to_dict(host_domain=host_domain) for t in trunks],
        "host_domain": host_domain,
        "sip_port": 5060,
    })


@login_required(login_url='/login/')
def save_pbx_trunk(request):
    """Create or update a Bidirectional PBX Trunk (Issabel / Asterisk) and sync with LiveKit SIP."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        trunk_id = data.get('id')
        name = str(data.get('name') or 'سنترال الشركة (Issabel PBX)').strip()
        auth_mode = data.get('auth_mode', 'ip')
        pbx_ip = str(data.get('pbx_ip') or '').strip()
        auth_username = str(data.get('auth_username') or '').strip()
        auth_password = str(data.get('auth_password') or '').strip()
        inbound_numbers = str(data.get('inbound_numbers') or '').strip()
        destination_type = data.get('destination_type', 'ai_assistant')
        if destination_type in ('ai', 'ai_assistant'):
            destination_type = 'ai_assistant'
        elif destination_type in ('queue', 'call_queue'):
            destination_type = 'call_queue'
        target_queue_id = data.get('target_queue_id')
        target_profile_id = data.get('target_profile_id')
        enable_outbound = bool(data.get('enable_outbound', True))
        outbound_port = int(data.get('outbound_port') or 5060)
        outbound_transport = str(data.get('outbound_transport') or 'UDP').strip().upper()
        is_default_outbound = bool(data.get('is_default_outbound', False))
        is_active = bool(data.get('is_active', True))

        if auth_mode not in ['ip', 'credentials']:
            return JsonResponse({"status": "error", "message": "نوع المصادقة غير صالح (اختر IP أو اسم مستخدم وكلمة مرور)"}, status=400)

        if auth_mode == 'ip' and not pbx_ip:
            return JsonResponse({"status": "error", "message": "يرجى إدخال عنوان IP لسنترال Issabel"}, status=400)

        if auth_mode == 'credentials' and not auth_username:
            return JsonResponse({"status": "error", "message": "يرجى إدخال اسم المستخدم للربط"}, status=400)

        target_queue = None
        if destination_type == 'call_queue':
            if not target_queue_id:
                return JsonResponse({"status": "error", "message": "يرجى اختيار طابور الانتظار المستهدف للمكالمات"}, status=400)
            target_queue = CallQueue.objects.filter(id=target_queue_id, user=request.user).first()
            if not target_queue:
                return JsonResponse({"status": "error", "message": "طابور الانتظار المحدد غير موجود"}, status=404)

        target_profile = None
        if target_profile_id:
            target_profile = AgentProfile.objects.filter(id=target_profile_id, user=request.user).first()

        if is_default_outbound:
            InboundPBXTrunk.objects.filter(user=request.user).update(is_default_outbound=False)

        trunk = None
        if trunk_id:
            trunk = get_object_or_404(InboundPBXTrunk, id=trunk_id, user=request.user)
            trunk.name = name
            trunk.auth_mode = auth_mode
            trunk.pbx_ip = pbx_ip
            trunk.auth_username = auth_username
            if auth_password:
                trunk.set_auth_password(auth_password)
            trunk.inbound_numbers = inbound_numbers
            trunk.destination_type = destination_type
            trunk.target_queue = target_queue
            trunk.target_profile = target_profile
            trunk.enable_outbound = enable_outbound
            trunk.outbound_port = outbound_port
            trunk.outbound_transport = outbound_transport
            trunk.is_default_outbound = is_default_outbound
            trunk.is_active = is_active
            trunk.save()
        else:
            if auth_mode == 'credentials' and not auth_password:
                auth_password = uuid.uuid4().hex[:12]

            trunk = InboundPBXTrunk(
                user=request.user,
                name=name,
                auth_mode=auth_mode,
                pbx_ip=pbx_ip,
                auth_username=auth_username,
                inbound_numbers=inbound_numbers,
                destination_type=destination_type,
                target_queue=target_queue,
                target_profile=target_profile,
                enable_outbound=enable_outbound,
                outbound_port=outbound_port,
                outbound_transport=outbound_transport,
                is_default_outbound=is_default_outbound,
                is_active=is_active
            )
            trunk.set_auth_password(auth_password)
            trunk.save()

        target_queue_code = target_queue.code if target_queue else None
        livekit_trunk_id, livekit_rule_id, livekit_outbound_trunk_id = asyncio.run(_async_create_pbx_inbound_trunk_and_rule(
            name=trunk.name,
            auth_mode=trunk.auth_mode,
            pbx_ip=trunk.pbx_ip,
            auth_username=trunk.auth_username,
            auth_password=trunk.auth_password,
            inbound_numbers_str=trunk.inbound_numbers,
            destination_type=trunk.destination_type,
            target_queue_code=target_queue_code,
            user_id=request.user.id,
            trunk_db_id=trunk.id,
            existing_trunk_id=trunk.livekit_trunk_id or None,
            existing_rule_id=trunk.livekit_rule_id or None,
            enable_outbound=trunk.enable_outbound,
            outbound_port=trunk.outbound_port,
            outbound_transport=trunk.outbound_transport,
            existing_outbound_trunk_id=trunk.livekit_outbound_trunk_id or None
        ))

        trunk.livekit_trunk_id = livekit_trunk_id
        trunk.livekit_rule_id = livekit_rule_id
        trunk.livekit_outbound_trunk_id = livekit_outbound_trunk_id
        trunk.save(update_fields=['livekit_trunk_id', 'livekit_rule_id', 'livekit_outbound_trunk_id'])

        host_domain = getattr(settings, 'SIP_PUBLIC_DOMAIN', request.get_host().split(':')[0])
        return JsonResponse({
            "status": "success",
            "message": "تم حفظ وإعداد ربط سنترال Issabel ثنائي الاتجاه في LiveKit بنجاح",
            "trunk": trunk.to_dict(host_domain=host_domain)
        })

    except Exception as e:
        logger.error(f"Error saving PBX Trunk: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": f"فشل حفظ سنترال Issabel: {str(e)}"}, status=500)


@login_required(login_url='/login/')
def delete_pbx_trunk(request, trunk_id):
    """Delete a PBX Trunk and remove all its LiveKit inbound/outbound resources."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        trunk = get_object_or_404(InboundPBXTrunk, id=trunk_id, user=request.user)
        asyncio.run(_async_delete_pbx_trunk_and_rule(
            trunk.livekit_trunk_id,
            trunk.livekit_rule_id,
            trunk.livekit_outbound_trunk_id
        ))
        trunk.delete()
        return JsonResponse({"status": "success", "message": "تم حذف السنترال وإلغاء الربط بنجاح"})
    except Exception as e:
        logger.error(f"Error deleting PBX Trunk {trunk_id}: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": f"فشل حذف السنترال: {str(e)}"}, status=500)
