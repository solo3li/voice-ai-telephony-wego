import json
import logging
import datetime
import re
import os
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Q

from .models import CustomerMemory, CallSession
from common.auth import verify_internal_api_key

logger = logging.getLogger(__name__)


@login_required(login_url='/login/')
def list_customers_memory(request):
    """List all customers (by phone number) for the authenticated user with search."""
    query = request.GET.get('q', '').strip()
    memories = CustomerMemory.objects.filter(user=request.user)
    if query:
        from django.db.models import Q
        memories = memories.filter(
            Q(phone_number__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(last_interaction_summary__icontains=query)
        )
    
    results = [m.to_dict() for m in memories]
    return JsonResponse({
        "status": "success",
        "customers": results,
        "count": len(results)
    })


@login_required(login_url='/login/')
def get_customer_memory(request):
    """Retrieve the customer memory card and recent call history for a specific phone number."""
    phone = request.GET.get('phone', '').strip()
    if not phone:
        # Default to web_dashboard or the most recently updated customer
        latest = CustomerMemory.objects.filter(user=request.user).first()
        phone = latest.phone_number if latest else 'web_dashboard'

    memory, _ = CustomerMemory.objects.get_or_create(user=request.user, phone_number=phone)
    recent_calls = CallSession.objects.filter(user=request.user)
    if phone != 'web_dashboard':
        from django.db.models import Q
        recent_calls = recent_calls.filter(Q(caller_phone=phone) | Q(destination_phone=phone))
    recent_calls = recent_calls[:5]

    return JsonResponse({
        "status": "success",
        "phone_number": phone,
        "memory": memory.to_dict(),
        "recent_calls": [c.to_dict() for c in recent_calls]
    })


@login_required(login_url='/login/')
def reset_customer_memory(request):
    """Reset customer memory for a specific phone number."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    data = json.loads(request.body.decode('utf-8')) if request.body else {}
    phone = (data.get('phone') or request.POST.get('phone') or '').strip()
    if not phone:
        phone = 'web_dashboard'

    memory = CustomerMemory.objects.filter(user=request.user, phone_number=phone).first()
    if memory:
        memory.permanent_profile = {}
        memory.customer_name = ""
        memory.last_interaction_summary = ""
        memory.last_interaction_at = None
        memory.save()
        res_dict = memory.to_dict()
    else:
        res_dict = {}

    return JsonResponse({
        "status": "success",
        "message": f"تمت إعادة تعيين ذاكرة العميل ({phone}) بنجاح.",
        "memory": res_dict
    })


# ==================== Internal Agent Call Completion & Memory API ====================

@csrf_exempt
def api_internal_get_customer_memory(request):
    """Internal API to get or search customer memory by user_id, caller_phone, or query identifier."""
    if request.method not in ['GET', 'POST']:
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not verify_internal_api_key(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        user_id = None
        caller_phone = 'web_dashboard'
        query = ''
        if request.method == 'POST':
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
            user_id = data.get('user_id') or request.POST.get('user_id')
            raw_phone = str(data.get('caller_phone') or request.POST.get('caller_phone') or 'web_dashboard')
            query = str(data.get('query') or data.get('identifier') or request.POST.get('query') or '').strip()
        else:
            user_id = request.GET.get('user_id')
            raw_phone = str(request.GET.get('caller_phone') or 'web_dashboard')
            query = str(request.GET.get('query') or request.GET.get('identifier') or '').strip()

        caller_phone = raw_phone.strip()
        if raw_phone.startswith(' ') and not caller_phone.startswith('+'):
            caller_phone = '+' + caller_phone

        # Defensive handling of user_id / query inverted
        try:
            user_id = int(user_id) if user_id is not None else None
        except (ValueError, TypeError):
            if isinstance(user_id, str) and not user_id.isdigit() and str(query).strip().isdigit():
                user_id, query = int(query), user_id
            else:
                user_id = None

        if not user_id:
            return JsonResponse({"status": "error", "message": "Valid numeric user_id is required"}, status=400)

        memory = None
        # 1. Search by query/identifier if provided
        if query:
            # A. Exact phone match
            memory = CustomerMemory.objects.filter(user_id=user_id, phone_number=query).first()
            # B. Suffix phone match (last 8 digits)
            if not memory:
                clean_digits = re.sub(r'\D', '', query)
                if len(clean_digits) >= 7:
                    memory = CustomerMemory.objects.filter(user_id=user_id, phone_number__endswith=clean_digits[-8:]).first()
            # C. Name match
            if not memory:
                memory = CustomerMemory.objects.filter(user_id=user_id, customer_name__icontains=query).first()
            # D. Profile text match
            if not memory:
                memory = CustomerMemory.objects.filter(user_id=user_id, permanent_profile__icontains=query).first()

        # 2. Fallback to caller_phone lookup only if query was not provided
        if not memory and not query and caller_phone:
            memory = CustomerMemory.objects.filter(user_id=user_id, phone_number=caller_phone).first()
            if not memory and caller_phone != 'web_dashboard' and len(caller_phone) >= 7:
                clean_digits = re.sub(r'\D', '', caller_phone)
                suffix = clean_digits[-8:] if len(clean_digits) >= 8 else caller_phone[-8:]
                memory = CustomerMemory.objects.filter(user_id=user_id, phone_number__endswith=suffix).first()

        found = bool(memory)
        card_text = memory.format_for_system_instruction() if memory else ""
        mem_dict = memory.to_dict() if memory else {
            "phone_number": caller_phone,
            "customer_name": "",
            "permanent_profile": {},
            "last_interaction_summary": "",
            "total_calls_count": 0
        }

        return JsonResponse({
            "status": "success",
            "found": found,
            "phone_number": memory.phone_number if memory else caller_phone,
            "card_text": card_text,
            "memory": mem_dict
        })
    except Exception as e:
        logger.error(f"Error in api_internal_get_customer_memory: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_internal_save_call_session_and_memory(request):
    """
    Internal API called by Voice Agent upon call completion to persist
    the CallSession details and update CustomerMemory for (user, caller_phone).
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not verify_internal_api_key(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        from crm.services.session_persistence import persist_call_session_and_memory
        res = persist_call_session_and_memory(data)
        http_status = 200 if res.get("status") == "success" else (404 if "not found" in res.get("message", "") else 400)
        return JsonResponse(res, status=http_status)
    except Exception as e:
        logger.error(f"Error saving CallSession and memory: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ==================== Call Detail Records (CDR) API ====================

@login_required(login_url='/login/')
def list_all_calls(request):
    """
    List and filter all Call Detail Records (CDR) for the authenticated user
    with advanced filters (search, direction, date presets, duration ranges).
    """
    try:
        from django.db.models import Q, Sum, Count
        from django.utils import timezone

        calls = CallSession.objects.filter(user=request.user)

        # 1. Search filter
        search = request.GET.get('search', '').strip()
        if search:
            calls = calls.filter(
                Q(caller_phone__icontains=search) |
                Q(destination_phone__icontains=search) |
                Q(room_name__icontains=search) |
                Q(call_goal__icontains=search) |
                Q(summary__icontains=search)
            )

        # 2. Direction filter
        direction = request.GET.get('direction', '').strip()
        if direction and direction != 'all':
            if direction == 'ai':
                calls = calls.filter(direction__in=['inbound', 'outbound_ai'])
            elif direction in ['internal', 'internal_employee']:
                calls = calls.filter(direction__in=['internal_employee', 'internal_test'])
            else:
                calls = calls.filter(direction=direction)

        # 3. Date presets / range
        date_preset = request.GET.get('date_preset', '').strip()
        now = timezone.now()

        if date_preset == 'today':
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            calls = calls.filter(started_at__gte=start_of_day)
        elif date_preset == 'last_7_days':
            start_7 = now - datetime.timedelta(days=7)
            calls = calls.filter(started_at__gte=start_7)
        elif date_preset == 'this_month':
            start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            calls = calls.filter(started_at__gte=start_month)
        else:
            from_date = request.GET.get('from_date', '').strip()
            to_date = request.GET.get('to_date', '').strip()
            if from_date:
                try:
                    f_dt = datetime.datetime.strptime(from_date, '%Y-%m-%d')
                    calls = calls.filter(started_at__date__gte=f_dt.date())
                except ValueError:
                    pass
            if to_date:
                try:
                    t_dt = datetime.datetime.strptime(to_date, '%Y-%m-%d')
                    calls = calls.filter(started_at__date__lte=t_dt.date())
                except ValueError:
                    pass

        # 4. Duration filter
        duration_filter = request.GET.get('duration', '').strip()
        if duration_filter == 'under_1m':
            calls = calls.filter(duration_seconds__lt=60)
        elif duration_filter == '1m_to_5m':
            calls = calls.filter(duration_seconds__gte=60, duration_seconds__lte=300)
        elif duration_filter == 'over_5m':
            calls = calls.filter(duration_seconds__gt=300)

        # Compute aggregate metrics on filtered set (strip ordering during aggregation)
        stats = calls.order_by().aggregate(
            total_calls=Count('id'),
            total_duration=Sum('duration_seconds'),
            total_minutes=Sum('billed_minutes'),
            total_cost=Sum('cost')
        )

        limit = int(request.GET.get('limit', 100))
        results = [c.to_dict(request) for c in calls[:limit]]

        return JsonResponse({
            "status": "success",
            "calls": results,
            "count": len(results),
            "stats": {
                "total_calls": stats.get('total_calls') or 0,
                "total_duration_seconds": stats.get('total_duration') or 0,
                "total_billed_minutes": stats.get('total_minutes') or 0,
                "total_cost": float(stats.get('total_cost') or 0.0),
            }
        })
    except Exception as e:
        logger.error(f"Error in list_all_calls: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ==================== Evolution API WhatsApp Omnichannel ====================

@login_required(login_url='/login/')
def api_whatsapp_status(request):
    """Get Evolution API WhatsApp connection status."""
    from .services.evolution_client import get_connection_status
    instance_name = f"user_{request.user.id}"
    res = get_connection_status(instance_name)
    return JsonResponse(res)


@login_required(login_url='/login/')
def api_whatsapp_connect(request):
    """Fetch QR code for pairing WhatsApp."""
    from .services.evolution_client import get_qr_code, configure_instance_webhook
    instance_name = f"user_{request.user.id}"
    res = get_qr_code(instance_name)

    # Configure webhook back to Django
    try:
        webhook_url = f"http://django:8000/api/crm/whatsapp/webhook/?tenant_id={request.user.id}"
        configure_instance_webhook(webhook_url, instance_name)
    except Exception as wh_err:
        logger.warning(f"Could not configure webhook: {wh_err}")

    return JsonResponse(res)


@login_required(login_url='/login/')
def api_whatsapp_disconnect(request):
    """Disconnect WhatsApp session."""
    from .services.evolution_client import logout_instance
    instance_name = f"user_{request.user.id}"
    res = logout_instance(instance_name)
    return JsonResponse(res)


@login_required(login_url='/login/')
def api_whatsapp_messages(request):
    """List recent Omnichannel messages for this user."""
    from .models import OmnichannelMessage
    limit = int(request.GET.get('limit', 50))
    msgs = OmnichannelMessage.objects.filter(user=request.user).order_by('-created_at')[:limit]
    return JsonResponse({
        "status": "success",
        "messages": [m.to_dict() for m in msgs]
    })


def _resolve_contact_display(phone_number: str, mem=None, last_msg=None, user=None) -> tuple:
    """Helper to return (customer_name, display_phone, real_phone, profile_pic_url)"""
    from .services.whatsapp_sync import format_phone_display
    prof = (mem.permanent_profile or {}) if mem else {}
    c_name = (mem.customer_name if mem else '') or prof.get('customer_name') or (last_msg.customer_name if last_msg else '')
    clean_p = phone_number.strip()
    
    # If no friendly name, fallback to friendly labels
    if not c_name or c_name == clean_p:
        if clean_p.endswith('@g.us'):
            c_name = "مجموعة واتساب"
        elif clean_p == '0':
            c_name = "واتساب الرسمي"
        elif clean_p == '201108124794':
            c_name = "أنا (ملاحظات شخصية)"
        else:
            c_name = "عميل واتساب جديد"

    real_phone = prof.get('real_phone') or (clean_p if ('@' not in clean_p and clean_p.isdigit()) else '')
    display_phone = prof.get('display_phone') or format_phone_display(real_phone, clean_p)
    profile_pic_url = prof.get('profile_pic_url') or ''
    if not profile_pic_url and user:
        try:
            from crm.services.evolution_client import fetch_profile_picture_url
            instance_name = f"user_{user.id}"
            profile_pic_url = fetch_profile_picture_url(real_phone or clean_p, instance_name) or ''
            if profile_pic_url and mem:
                prof['profile_pic_url'] = profile_pic_url
                mem.permanent_profile = prof
                mem.save(update_fields=['permanent_profile'])
        except Exception:
            pass
    return c_name, display_phone, real_phone, profile_pic_url


@login_required(login_url='/login/')
def api_whatsapp_conversations(request):
    """List all WhatsApp conversations grouped by customer/phone (WhatsApp Web Inbox format)."""
    from .models import OmnichannelMessage, CustomerMemory
    from django.db.models import Max, Count

    threads = (
        OmnichannelMessage.objects.filter(user=request.user)
        .values('phone_number')
        .annotate(
            last_message_at=Max('created_at'),
            messages_count=Count('id')
        )
        .order_by('-last_message_at')
    )

    phones = [t['phone_number'] for t in threads]
    memories = {m.phone_number: m for m in CustomerMemory.objects.filter(user=request.user, phone_number__in=phones)}

    results = []
    for t in threads:
        p = t['phone_number']
        last_msg = OmnichannelMessage.objects.filter(user=request.user, phone_number=p).order_by('-created_at').first()
        mem = memories.get(p)
        c_name, display_phone, real_phone, profile_pic_url = _resolve_contact_display(p, mem, last_msg, user=request.user)
        wm = mem.whatsapp_memory or {} if mem else {}
        ai_active = wm.get("ai_auto_reply_enabled", True)

        results.append({
            "phone_number": p,
            "customer_name": c_name,
            "display_phone": display_phone,
            "real_phone": real_phone,
            "profile_pic_url": profile_pic_url,
            "last_message": {
                "text": last_msg.message_text if last_msg else "",
                "direction": last_msg.direction if last_msg else "inbound",
                "is_outbound": last_msg.direction in ('outbound_ai', 'outbound_human', 'outbound') if last_msg else False,
                "is_ai": last_msg.direction == 'outbound_ai' if last_msg else False,
                "is_human": last_msg.direction == 'outbound_human' if last_msg else False,
                "created_at": last_msg.created_at.strftime("%Y-%m-%d %H:%M") if last_msg else "",
                "created_at_time": last_msg.created_at.strftime("%I:%M %p") if last_msg else "",
                "created_at_iso": last_msg.created_at.isoformat() if last_msg else "",
            },
            "messages_count": t['messages_count'],
            "ai_active": ai_active,
            "needs_human_attention": wm.get("needs_human_attention", False),
            "conversation_state": wm.get("conversation_state", "AI_ACTIVE" if ai_active else "PENDING_AGENT_REPLY"),
            "assigned_agent_id": wm.get("assigned_agent_id"),
            "sla_seconds": wm.get("sla_seconds", 300),
            "escalation_reason": wm.get("escalation_reason", ""),
            "escalation_urgency": wm.get("escalation_urgency", ""),
            "escalation_summary": wm.get("escalation_summary", ""),
            "escalated_at": wm.get("escalated_at", ""),
            "has_call_history": bool(mem and mem.total_calls_count > 0)
        })

    return JsonResponse({"status": "success", "conversations": results})


@login_required(login_url='/login/')
def api_whatsapp_conversation_messages(request, phone_number):
    """Get full message thread for a specific customer phone number or WhatsApp JID."""
    from .models import OmnichannelMessage, CustomerMemory
    clean_phone = phone_number.strip()

    msgs_qs = OmnichannelMessage.objects.filter(
        user=request.user,
        phone_number=clean_phone
    ).order_by('created_at')

    msgs = list(msgs_qs[:150])
    mem = CustomerMemory.objects.filter(user=request.user, phone_number=clean_phone).first()
    last_msg = msgs[-1] if msgs else None
    c_name, display_phone, real_phone, profile_pic_url = _resolve_contact_display(clean_phone, mem, last_msg, user=request.user)
    wm = mem.whatsapp_memory or {} if mem else {}
    cm = mem.call_memory or {} if mem else {}

    return JsonResponse({
        "status": "success",
        "phone_number": clean_phone,
        "customer_name": c_name,
        "display_phone": display_phone,
        "real_phone": real_phone,
        "profile_pic_url": profile_pic_url,
        "ai_active": wm.get("ai_auto_reply_enabled", True),
        "needs_human_attention": wm.get("needs_human_attention", False),
        "conversation_state": wm.get("conversation_state", "AI_ACTIVE" if wm.get("ai_auto_reply_enabled", True) else "PENDING_AGENT_REPLY"),
        "assigned_agent_id": wm.get("assigned_agent_id"),
        "sla_seconds": wm.get("sla_seconds", 300),
        "escalation_reason": wm.get("escalation_reason", ""),
        "escalation_urgency": wm.get("escalation_urgency", ""),
        "escalation_summary": wm.get("escalation_summary", ""),
        "escalated_at": wm.get("escalated_at", ""),
        "call_summary": cm.get("last_call_summary") or (mem.last_interaction_summary if mem else ""),
        "total_calls_count": mem.total_calls_count if mem else 0,
        "messages": [m.to_dict() for m in msgs]
    })


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_conversation_update_contact(request, phone_number):
    """Update contact name and phone number directly from the UI."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    try:
        from .models import OmnichannelMessage, CustomerMemory
        from .services.whatsapp_sync import format_phone_display
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        new_name = str(data.get("name") or data.get("customer_name") or "").strip()
        new_phone = str(data.get("phone") or data.get("real_phone") or "").strip()

        clean_phone = phone_number.strip()
        mem, _ = CustomerMemory.objects.get_or_create(
            user=request.user,
            phone_number=clean_phone
        )
        if new_name:
            mem.customer_name = new_name
            OmnichannelMessage.objects.filter(user=request.user, phone_number=clean_phone).update(customer_name=new_name)

        prof = mem.permanent_profile or {}
        if new_name:
            prof["customer_name"] = new_name
        if new_phone:
            prof["real_phone"] = new_phone
            prof["display_phone"] = format_phone_display(new_phone, clean_phone)

        mem.permanent_profile = prof
        mem.save()

        disp_phone = prof.get("display_phone") or format_phone_display(prof.get("real_phone", ""), clean_phone)

        return JsonResponse({
            "status": "success",
            "customer_name": mem.customer_name,
            "display_phone": disp_phone,
            "real_phone": prof.get("real_phone", "")
        })
    except Exception as e:
        logger.error(f"Error updating contact: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_conversation_reply(request, phone_number):
    """Manual human agent reply sent directly from the chat interface to WhatsApp."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        text = str(data.get("message", "")).strip()
        if not text:
            return JsonResponse({"status": "error", "message": "نص الرسالة مطلوب"}, status=400)

        clean_phone = phone_number.strip()
        instance_name = f"user_{request.user.id}"
        from .services.evolution_client import send_whatsapp_message
        from .models import OmnichannelMessage, CustomerMemory

        send_res = send_whatsapp_message(clean_phone, text, instance_name)

        mem = CustomerMemory.objects.filter(user=request.user, phone_number=clean_phone).first()
        c_name = mem.customer_name if mem else ""

        msg = OmnichannelMessage.objects.create(
            user=request.user,
            phone_number=clean_phone,
            customer_name=c_name,
            channel="whatsapp",
            direction="outbound_human",
            message_text=text,
            metadata={"send_result": send_res, "manual_reply": True}
        )

        if mem:
            wm = mem.whatsapp_memory or {}
            wm["last_interaction_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            wm["last_sent_message"] = text
            msgs_list = wm.get("last_messages", [])
            msgs_list.append({
                "sender": "human_agent",
                "text": text,
                "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
            })
            wm["last_messages"] = msgs_list[-15:]
            mem.whatsapp_memory = wm
            mem.save()

        return JsonResponse({
            "status": "success",
            "message": msg.to_dict(),
            "send_result": send_res
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_conversation_toggle_ai(request, phone_number):
    """Toggle AI auto-reply on/off for this specific customer conversation (Human takeover)."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        clean_phone = phone_number.strip()
        from .models import CustomerMemory
        mem, _ = CustomerMemory.objects.get_or_create(user=request.user, phone_number=clean_phone)
        wm = mem.whatsapp_memory or {}

        if "ai_active" in data:
            new_state = bool(data["ai_active"])
        else:
            current = wm.get("ai_auto_reply_enabled", True)
            new_state = not current

        wm["ai_auto_reply_enabled"] = new_state
        if new_state:
            wm["needs_human_attention"] = False
        mem.whatsapp_memory = wm
        mem.save()

        return JsonResponse({
            "status": "success",
            "phone_number": clean_phone,
            "ai_active": new_state,
            "message": "تم تفعيل الرد الآلي للذكاء الاصطناعي لهذا العميل" if new_state else "تم إيقاف الرد الآلي وتحويل المحادثة للموظف البشري"
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_sync(request):
    """Sync all genuine WhatsApp chats and messages directly from Evolution API / evolution_db."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    try:
        from .services.whatsapp_sync import sync_whatsapp_data
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        clean_old = bool(data.get("clean_old", True))
        max_messages = int(data.get("max_messages", 40))

        res = sync_whatsapp_data(request.user, clean_old=clean_old, max_messages_per_chat=max_messages)
        return JsonResponse(res)
    except Exception as e:
        logger.error(f"Error in api_whatsapp_sync: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_send_test(request):
    """Send a direct WhatsApp test message."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        phone = data.get("phone", "").strip()
        text = data.get("message", "").strip()
        trigger = data.get("trigger", "manual_test")

        if not phone:
            return JsonResponse({"status": "error", "message": "رقم الهاتف مطلوب"}, status=400)

        instance_name = f"user_{request.user.id}"
        from .services.evolution_client import send_whatsapp_message
        from .models import OmnichannelMessage

        if not text:
            text = "مرحباً بك! هذه رسالة تجريبية من الموظف الذكي عبر Evolution API و LangGraph 🚀"

        res = send_whatsapp_message(phone, text, instance_name)
        if res.get("status") == "success":
            OmnichannelMessage.objects.create(
                user=request.user,
                phone_number=phone,
                channel="whatsapp",
                direction="outbound",
                message_text=text,
                status="sent",
                metadata={"test": True, "trigger": trigger}
            )
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_trigger_followup(request):
    """Trigger LangGraph autonomous follow-up on demand for a customer number."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        phone = data.get("phone", "").strip()
        if not phone:
            return JsonResponse({"status": "error", "message": "رقم الهاتف مطلوب"}, status=400)

        from crm.inngest_jobs import dispatch_whatsapp_followup_job
        dispatch_whatsapp_followup_job(
            user_id=request.user.id,
            phone_number=phone,
            trigger_type="scheduled_followup",
            customer_name=data.get("customer_name", ""),
        )
        return JsonResponse({"status": "success", "message": "تم إرسال مهمة المتابعة الذكية إلى Inngest بنجاح!"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_whatsapp_webhook(request):
    """
    Handle inbound Evolution API webhooks.
    Triggers LangGraph autonomous response for inbound customer messages via durable Inngest jobs.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        tenant_id = request.GET.get('tenant_id')
        user = User.objects.filter(id=int(tenant_id)).first() if tenant_id and tenant_id.isdigit() else None
        if not user:
            user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        body = json.loads(request.body.decode('utf-8')) if request.body else {}
        event = body.get("event")

        if event == "messages.upsert":
            data = body.get("data", {})
            key = data.get("key", {})
            from_me = key.get("fromMe", False)
            if from_me:
                return JsonResponse({"status": "ignored", "reason": "outbound_message"})

            remote_jid = key.get("remoteJid", "")
            from .services.whatsapp_sync import normalize_jid_to_identifier
            clean_phone = normalize_jid_to_identifier(remote_jid)
            push_name = data.get("pushName") or ""

            message_content = data.get("message", {})
            msg_text = (
                message_content.get("conversation")
                or message_content.get("extendedTextMessage", {}).get("text")
                or ""
            ).strip()

            from .services.whatsapp_media import (
                extract_media_info_from_message,
                get_or_download_whatsapp_media,
                analyze_media_with_gemini
            )

            media_info = extract_media_info_from_message(message_content, data.get("messageType", ""))
            has_media = media_info.get("has_media", False)

            if not msg_text and not has_media:
                return JsonResponse({"status": "ignored", "reason": "empty_content_and_no_media"})

            if not clean_phone:
                return JsonResponse({"status": "ignored", "reason": "empty_phone"})

            msg_meta = {
                "raw_data": data,
                "raw_key": key,
                "raw_msg": message_content,
                "whatsapp_msg_id": key.get("id", ""),
            }
            if has_media:
                msg_meta.update(media_info)

            display_initial_text = msg_text
            if not display_initial_text and has_media:
                m_type = media_info.get("media_type")
                if m_type == "audio":
                    display_initial_text = "🎤 رسالة صوتية"
                elif m_type == "image":
                    display_initial_text = "📷 صورة"
                elif m_type == "video":
                    display_initial_text = "🎥 فيديو"
                else:
                    display_initial_text = f"[{m_type}]"

            # 1. Log inbound message
            from .models import OmnichannelMessage, CustomerMemory
            msg_obj = OmnichannelMessage.objects.create(
                user=user,
                phone_number=clean_phone,
                customer_name=push_name,
                channel="whatsapp",
                direction="inbound",
                message_text=display_initial_text,
                metadata=msg_meta
            )

            # If message contains media, decrypt and run Gemini Multimodal analysis
            if has_media:
                try:
                    media_path, mimetype = get_or_download_whatsapp_media(msg_obj, instance_name=f"user_{user.id}")
                    if media_path and os.path.exists(media_path):
                        with open(media_path, "rb") as mf:
                            media_bytes = mf.read()
                        analysis = analyze_media_with_gemini(
                            media_bytes=media_bytes,
                            mimetype=mimetype,
                            media_type=media_info.get("media_type", ""),
                            caption=media_info.get("caption", "")
                        )
                        if media_info.get("media_type") == "audio":
                            transcription = analysis.get("transcription", "")
                            msg_meta["transcription"] = transcription
                            msg_meta["audio_summary"] = analysis.get("summary", "")
                            msg_meta["audio_intent"] = analysis.get("intent", "")
                            if transcription:
                                msg_text = f"🎤 [رسالة صوتية مسجلة]: {transcription}"
                                msg_obj.message_text = msg_text
                        elif media_info.get("media_type") in ("image", "video"):
                            vision_desc = analysis.get("description", "")
                            pmt = analysis.get("payment_details")
                            msg_meta["vision_analysis"] = analysis
                            prefix = "📷 [صورة مرفقة]" if media_info.get("media_type") == "image" else "🎥 [فيديو مرفق]"
                            if pmt:
                                details_str = f"إيصال دفع: {pmt.get('المبلغ المحول') or pmt.get('amount') or ''} - عملية: {pmt.get('رقم العملية') or pmt.get('ref') or ''}"
                                msg_text = f"{prefix}: {details_str} ({vision_desc})"
                            elif vision_desc:
                                msg_text = f"{prefix}: {vision_desc}"
                            msg_obj.message_text = msg_text

                        msg_obj.metadata = msg_meta
                        msg_obj.save(update_fields=["message_text", "metadata"])
                except Exception as media_err:
                    logger.error(f"Error analyzing incoming WhatsApp media: {media_err}", exc_info=True)

            logger.info(f"Received inbound WhatsApp message from {clean_phone} ({push_name}): {msg_obj.message_text[:60]}")

            # 2. Update CustomerMemory whatsapp_memory
            mem, _ = CustomerMemory.objects.get_or_create(
                user=user,
                phone_number=clean_phone,
                defaults={"customer_name": push_name}
            )
            wm = mem.whatsapp_memory or {}
            wm["last_received_message"] = msg_obj.message_text
            wm["last_interaction_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            msgs_list = wm.get("last_messages", [])
            msgs_list.append({"sender": "customer", "text": msg_obj.message_text, "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")})
            wm["last_messages"] = msgs_list[-6:]
            mem.whatsapp_memory = wm
            if push_name and not mem.customer_name:
                mem.customer_name = push_name
            mem.save()

            # 3. Check if AI auto-reply is active for this customer (Human takeover check)
            if wm.get("ai_auto_reply_enabled", True) is False:
                logger.info(f"AI auto-reply is paused for {clean_phone} (Human takeover active). Skipping LangGraph dispatch.")
                return JsonResponse({"status": "received", "action": "ai_paused_manual_takeover"})

            # 4. Trigger LangGraph via durable Inngest background job
            from crm.inngest_jobs import dispatch_whatsapp_followup_job
            dispatch_whatsapp_followup_job(
                user_id=user.id,
                phone_number=clean_phone,
                trigger_type="inbound_whatsapp",
                inbound_message=msg_obj.message_text,
                customer_name=push_name,
            )

            return JsonResponse({"status": "success", "action": "inngest_dispatched"})

        return JsonResponse({"status": "received", "event": event})

    except Exception as e:
        logger.error(f"Error handling Evolution API webhook: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_message_media(request, message_id):
    """
    GET /api/crm/whatsapp/messages/<message_id>/media/
    Streams decrypted media (audio, image, video, document) with HTTP Range support.
    """
    from .models import OmnichannelMessage
    msg = get_object_or_404(OmnichannelMessage, id=message_id, user=request.user)
    meta = msg.metadata or {}
    if not meta.get("has_media"):
        return JsonResponse({"status": "error", "message": "Message does not contain media"}, status=400)

    from .services.whatsapp_media import get_or_download_whatsapp_media, analyze_media_with_gemini
    instance_name = f"user_{request.user.id}"
    media_path, mimetype = get_or_download_whatsapp_media(msg, instance_name=instance_name)

    if not media_path or not os.path.exists(media_path):
        return JsonResponse({"status": "error", "message": "Media could not be retrieved or decrypted"}, status=404)

    # Lazy transcription on first stream if missing
    if meta.get("media_type") == "audio" and not meta.get("transcription"):
        try:
            with open(media_path, "rb") as af:
                a_bytes = af.read()
            analysis = analyze_media_with_gemini(a_bytes, mimetype, "audio")
            if analysis.get("transcription"):
                meta["transcription"] = analysis["transcription"]
                meta["audio_summary"] = analysis.get("summary", "")
                meta["audio_intent"] = analysis.get("intent", "")
                msg.metadata = meta
                msg.save(update_fields=["metadata"])
        except Exception as e:
            logger.warning(f"Could not lazy-transcribe audio for msg {message_id}: {e}")

    elif meta.get("media_type") == "image" and not meta.get("vision_analysis"):
        try:
            with open(media_path, "rb") as imf:
                i_bytes = imf.read()
            analysis = analyze_media_with_gemini(i_bytes, mimetype, "image", caption=meta.get("caption", ""))
            if analysis:
                meta["vision_analysis"] = analysis
                msg.metadata = meta
                msg.save(update_fields=["metadata"])
        except Exception as e:
            logger.warning(f"Could not lazy-analyze image for msg {message_id}: {e}")

    response = FileResponse(open(media_path, 'rb'), content_type=mimetype or 'application/octet-stream')
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'public, max-age=86400'
    return response


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_conversation_resolve(request, phone_number):
    """
    POST /api/crm/whatsapp/conversations/<path:phone_number>/resolve/
    Resolves an active support conversation:
    - Sets conversation_state = 'RESOLVED'
    - Reactivates AI auto-reply: ai_auto_reply_enabled = True
    - Saves resolution notes and timestamp in CustomerMemory
    - Synchronizes any OPEN CRMSupportTicket for this phone to RESOLVED
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    clean_phone = str(phone_number).strip()
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        data = {}

    notes = data.get("resolution_notes", "")
    res_status = data.get("resolution_status", "RESOLVED")

    from crm.services.whatsapp_dispatcher import resolve_conversation
    res = resolve_conversation(
        user_id=request.user,
        phone_number=clean_phone,
        resolution_notes=notes,
        resolution_status=res_status
    )
    return JsonResponse(res)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_conversation_claim(request, phone_number):
    """
    POST /api/crm/whatsapp/conversations/<path:phone_number>/claim/
    Claim an escalated WhatsApp conversation from the shared ringing pool.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    clean_phone = str(phone_number).strip()
    from crm.services.whatsapp_dispatcher import claim_conversation
    res = claim_conversation(
        user_id=request.user,
        phone_number=clean_phone,
        agent_user_id=request.user.id
    )
    return JsonResponse(res)


@csrf_exempt
@login_required(login_url='/login/')
def api_whatsapp_conversation_release(request, phone_number):
    """
    POST /api/crm/whatsapp/conversations/<path:phone_number>/release/
    Release a claimed conversation back into the shared ringing pool.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    clean_phone = str(phone_number).strip()
    from crm.services.whatsapp_dispatcher import release_conversation_to_pool
    res = release_conversation_to_pool(
        user_id=request.user,
        phone_number=clean_phone,
        reason="Agent released back to queue"
    )
    return JsonResponse(res)




