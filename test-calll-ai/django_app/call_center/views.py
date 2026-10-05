import re
import os
import time
import json
import uuid
import math
import logging
import datetime
import requests
import jwt
import redis
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from asgiref.sync import async_to_sync
import inngest
from livekit import api

from .models import EmployeeProfile, CallQueue, QueueMembership, EmployeeCallLog
from .inngest_jobs import inngest_client
from telephony.wazo_client import wazo_client

logger = logging.getLogger(__name__)

JWT_SECRET = getattr(settings, 'SECRET_KEY', 'default_secret_key')

from common.centrifugo import publish_to_centrifugo

def generate_employee_jwt(employee: EmployeeProfile):
    payload = {
        "user_id": employee.user_id,
        "username": employee.user.username,
        "employee_id": employee.id,
        "extension": employee.extension,
        "exp": int(time.time()) + (30 * 24 * 3600),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def get_employee_from_token(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        token_str = request.GET.get("token")
        if not token_str:
            return None
    else:
        token_str = auth_header.split("Bearer ")[1].strip()

    try:
        payload = jwt.decode(token_str, JWT_SECRET, algorithms=["HS256"])
        return EmployeeProfile.objects.select_related('user').filter(id=payload.get("employee_id"), is_active=True).first()
    except Exception as e:
        logger.warning(f"Invalid employee JWT: {e}")
        return None

def generate_centrifugo_token_for_employee(employee: EmployeeProfile):
    centrifugo_payload = {
        "sub": f"employee_{employee.id}_{employee.extension}",
        "exp": int(time.time()) + (30 * 24 * 3600),
        "info": {
            "id": employee.id,
            "name": employee.display_name,
            "extension": employee.extension,
            "department": employee.department,
        }
    }
    return jwt.encode(centrifugo_payload, settings.CENTRIFUGO_SECRET, algorithm="HS256")

# ==================== Auth & Profile APIs ====================

@csrf_exempt
def api_employee_login(request):
    """Authenticate employee by username or extension and return JWT & Centrifugo tokens."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        identifier = str(data.get('identifier') or data.get('username') or data.get('extension') or '').strip()
        password = str(data.get('password') or '').strip()

        if not identifier or not password:
            return JsonResponse({"status": "error", "message": "يرجى إدخال اسم المستخدم أو التحويلة وكلمة المرور"}, status=400)

        # 1. Try direct authentication by username first
        user = authenticate(request, username=identifier, password=password)
        if not user:
            # 2. If not matched directly by username, identifier may be an extension shared across employers
            # Find all matching active employee profiles and check password against their respective user account
            candidate_employees = list(EmployeeProfile.objects.select_related('user').filter(extension=identifier, is_active=True))
            for candidate in candidate_employees:
                matched_user = authenticate(request, username=candidate.user.username, password=password)
                if matched_user:
                    user = matched_user
                    break

        if not user:
            return JsonResponse({"status": "error", "message": "بيانات الدخول غير صحيحة (اسم المستخدم/التحويلة أو كلمة المرور خطأ)"}, status=401)

        # 3. Fetch or auto-create EmployeeProfile
        employee = EmployeeProfile.objects.filter(user=user).first()
        is_owner_user = bool(user.is_superuser or user.agent_profiles.exists() or user.managed_employees.exists())

        if not employee:
            ext = str(100 + user.id)
            display = f"{user.get_full_name() or user.username} (المالك / المشرف)" if is_owner_user else (user.get_full_name() or user.username)
            employee = EmployeeProfile.objects.create(
                user=user,
                employer=user if is_owner_user else None,
                extension=ext,
                display_name=display,
                department="الإدارة العامة" if is_owner_user else ("المبيعات" if user.id % 2 != 0 else "خدمة العملاء"),
                status="ready"
            )
        else:
            update_fields = ['status']
            employee.status = "ready"
            if is_owner_user:
                if employee.employer_id != user.id:
                    employee.employer = user
                    update_fields.append('employer')
                if "(المالك" not in employee.display_name:
                    employee.display_name = f"{user.get_full_name() or user.username} (المالك / المشرف)"
                    update_fields.append('display_name')
            employee.save(update_fields=update_fields)

        # 4. Generate Tokens
        app_token = generate_employee_jwt(employee)
        centrifugo_token = generate_centrifugo_token_for_employee(employee)

        publish_to_centrifugo("employees:presence", {
            "event": "status_change",
            "employee": employee.to_dict()
        })

        return JsonResponse({
            "status": "success",
            "token": app_token,
            "employee": employee.to_dict(),
            "centrifugo": {
                "ws_url": settings.CENTRIFUGO_WS_URL,
                "token": centrifugo_token,
                "channel": f"employee:{employee.id}"
            }
        })

    except Exception as e:
        logger.error(f"Error in api_employee_login: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
def api_employee_me(request):
    """Return profile and Centrifugo credentials for the authenticated employee."""
    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    centrifugo_token = generate_centrifugo_token_for_employee(employee)
    return JsonResponse({
        "status": "success",
        "employee": employee.to_dict(),
        "centrifugo": {
            "ws_url": settings.CENTRIFUGO_WS_URL,
            "token": centrifugo_token,
            "channel": f"employee:{employee.id}"
        }
    })

# ==================== Employee Directory APIs ====================

@csrf_exempt
def api_list_employees(request):
    """List all employees and active call queues for the internal directory."""
    employee = get_employee_from_token(request)
    if not employee and not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    if employee:
        employer = employee.employer or employee.user
        employees = EmployeeProfile.objects.filter(employer=employer, is_active=True).exclude(id=employee.id).order_by('extension')
        queues = CallQueue.objects.filter(user=employer, is_active=True).order_by('code')
        current_emp_data = employee.to_dict()
    else:
        employer = request.user
        employees = EmployeeProfile.objects.filter(employer=employer, is_active=True).order_by('extension')
        queues = CallQueue.objects.filter(user=employer, is_active=True).order_by('code')
        current_emp_data = None

    return JsonResponse({
        "status": "success",
        "current_employee": current_emp_data,
        "employees": [e.to_dict() for e in employees],
        "queues": [q.to_dict() for q in queues]
    })

@csrf_exempt
def api_create_employee(request):
    """Create a new employee profile and user account from dashboard or API."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not request.user.is_authenticated and not get_employee_from_token(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        display_name = str(data.get('display_name') or '').strip()
        username = str(data.get('username') or '').strip()
        extension = str(data.get('extension') or '').strip()
        department = str(data.get('department') or 'المبيعات').strip()
        password = str(data.get('password') or 'password123').strip()

        if not display_name or not username or not extension:
            return JsonResponse({"status": "error", "message": "الاسم واسم المستخدم ورقم التحويلة حقول مطلوبة"}, status=400)

        if EmployeeProfile.objects.filter(extension=extension).exists():
            return JsonResponse({"status": "error", "message": f"رقم التحويلة '{extension}' مسجل بالفعل لموظف آخر"}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({"status": "error", "message": f"اسم المستخدم '{username}' مسجل بالفعل"}, status=400)

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=display_name
        )

        employer = None
        if request.user.is_authenticated:
            employer = request.user
        else:
            creator_emp = get_employee_from_token(request)
            if creator_emp:
                employer = creator_emp.employer or creator_emp.user
        if not employer:
            employer = User.objects.filter(is_superuser=True).order_by('id').first()

        # Ensure tenant has a native Wazo context
        tenant_context = None
        try:
            from telephony.models import get_or_create_tenant_context
            tenant_cfg = get_or_create_tenant_context(employer)
            tenant_context = tenant_cfg.wazo_context
        except Exception as e:
            logger.warning(f"Could not resolve tenant context: {e}")

        # Headless Wazo Provisioning in Tenant Context
        wazo_info = wazo_client.provision_employee(
            display_name=display_name,
            extension=extension,
            password=password,
            context=tenant_context
        )

        employee = EmployeeProfile.objects.create(
            user=user,
            employer=employer,
            extension=extension,
            display_name=display_name,
            department=department,
            status='ready',
            avatar_url=f"https://api.dicebear.com/7.x/bottts/png?seed={extension}",
            wazo_user_uuid=wazo_info.get("wazo_user_uuid", ""),
            wazo_line_id=wazo_info.get("wazo_line_id", ""),
            sip_username=wazo_info.get("sip_username", f"emp{extension}"),
            sip_password=wazo_info.get("sip_password", password),
            sip_host=wazo_info.get("sip_host", ""),
            sip_port=wazo_info.get("sip_port", 5070)
        )

        publish_to_centrifugo("employees:presence", {
            "event": "employee_created",
            "employee": employee.to_dict()
        })

        return JsonResponse({
            "status": "success",
            "message": f"تم إنشاء حساب الموظف '{display_name}' (تحويلة {extension}) وضبط إعدادات SIP بنجاح",
            "employee": employee.to_dict()
        }, status=201)

    except Exception as e:
        logger.error(f"Error creating employee: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
def api_delete_employee(request, employee_id):
    """Delete an employee and their associated user account."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not request.user.is_authenticated and not get_employee_from_token(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        employee = EmployeeProfile.objects.filter(id=employee_id).first()
        if not employee:
            return JsonResponse({"status": "error", "message": "الموظف غير موجود"}, status=404)

        if employee.wazo_user_uuid:
            wazo_client.delete_user(employee.wazo_user_uuid)

        name = employee.display_name
        ext = employee.extension
        user = employee.user
        user.delete()

        publish_to_centrifugo("employees:presence", {
            "event": "employee_deleted",
            "employee_id": employee_id,
            "extension": ext
        })

        return JsonResponse({
            "status": "success",
            "message": f"تم حذف الموظف '{name}' (تحويلة {ext}) بنجاح"
        })

    except Exception as e:
        logger.error(f"Error deleting employee: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
def api_update_employee_status(request):
    """Update employee status (ready, break, busy, offline)."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        new_status = data.get('status', 'ready')
        if new_status in ['ready', 'break', 'busy', 'offline']:
            employee.status = new_status
            employee.save(update_fields=['status'])

            publish_to_centrifugo("employees:presence", {
                "event": "status_change",
                "employee": employee.to_dict()
            })

            return JsonResponse({"status": "success", "employee": employee.to_dict()})
        else:
            return JsonResponse({"status": "error", "message": "Invalid status value"}, status=400)

    except Exception as e:
        logger.error(f"Error in api_update_employee_status: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def send_expo_push_notification(push_token: str, title: str, body: str, data: dict = None) -> bool:
    """Send an Expo push notification to wake up the employee mobile app."""
    if not push_token or not (push_token.startswith("ExponentPushToken") or push_token.startswith("ExpoPushToken")):
        return False
    try:
        payload = {
            "to": push_token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {},
            "priority": "high",
            "channelId": "call-notifications",
            "categoryId": "INCOMING_CALL",
        }
        res = requests.post(
            "https://exp.host/--/api/v2/push/send",
            json=payload,
            headers={
                "Accept": "application/json",
                "Accept-encoding": "gzip, deflate",
                "Content-Type": "application/json",
            },
            timeout=4.0
        )
        logger.info(f"Expo push notification sent to {push_token[:15]}...: status={res.status_code}")
        return res.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to send Expo push notification: {e}")
        return False


@csrf_exempt
def api_update_push_token(request):
    """Update or register Expo Push Token for the logged-in employee."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        token = str(data.get('push_token', '')).strip()
        employee.push_token = token
        employee.save(update_fields=['push_token'])
        logger.info(f"Updated push token for employee #{employee.id} ({employee.display_name})")
        return JsonResponse({
            "status": "success",
            "message": "Push token updated successfully",
            "push_token": token
        })
    except Exception as e:
        logger.error(f"Error updating employee push token: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_get_active_incoming_call(request):
    """Query Redis for any active incoming call currently ringing for this employee."""
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        raw = r.get(f"call_center:ringing:employee:{employee.id}")
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            call_payload = json.loads(raw)
            return JsonResponse({
                "status": "ringing",
                "incoming_call": call_payload
            })
        return JsonResponse({
            "status": "idle",
            "incoming_call": None
        })
    except Exception as e:
        logger.error(f"Error checking active incoming call for employee #{employee.id}: {e}", exc_info=True)
        return JsonResponse({"status": "idle", "incoming_call": None})


@csrf_exempt
def api_employee_heartbeat(request):
    """
    Heartbeat and Keep-Alive watchdog endpoint for mobile softphone apps.
    Refreshes employee presence in Redis (TTL: 90s) and returns any pending active call.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        body = {}

    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        now_ts = timezone.now().isoformat()
        heartbeat_data = {
            "employee_id": employee.id,
            "extension": employee.extension,
            "status": employee.status,
            "last_heartbeat": now_ts,
            "device": body.get("device", {}),
        }
        r.setex(
            f"call_center:employee:{employee.id}:alive",
            90,
            json.dumps(heartbeat_data)
        )

        # Check for any active ringing call
        active_call = None
        raw_ringing = r.get(f"call_center:ringing:employee:{employee.id}")
        if raw_ringing:
            if isinstance(raw_ringing, bytes):
                raw_ringing = raw_ringing.decode('utf-8')
            try:
                active_call = json.loads(raw_ringing)
            except Exception:
                pass

        return JsonResponse({
            "status": "ok",
            "employee_id": employee.id,
            "server_time": now_ts,
            "active_call": active_call,
        })
    except Exception as e:
        logger.error(f"Error in employee heartbeat for #{employee.id}: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ==================== Call Queues Management ====================

async def _async_create_queue_trunk_and_rule(queue_name, queue_code, user_id):
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        trunk_req = api.CreateSIPInboundTrunkRequest(
            trunk=api.SIPInboundTrunkInfo(
                name=f"Queue {queue_code} - {queue_name} (User {user_id})",
                numbers=[str(queue_code)],
                allowed_numbers=[str(queue_code)],
            )
        )
        created_trunk = await lk.sip.create_sip_inbound_trunk(trunk_req)
        trunk_id = created_trunk.sip_trunk_id

        rule_req = api.CreateSIPDispatchRuleRequest(
            name=f"Rule for Queue {queue_code} - User {user_id}",
            trunk_ids=[trunk_id],
            rule=api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix=f"room_user_{user_id}_queue_{queue_code}_"
                )
            )
        )
        created_rule = await lk.sip.create_sip_dispatch_rule(rule_req)
        rule_id = created_rule.sip_dispatch_rule_id
        return trunk_id, rule_id
    finally:
        await lk.aclose()

@csrf_exempt
def list_call_queues(request):
    """List all call queues for authenticated user or employee with waiting metrics."""
    employee = get_employee_from_token(request)
    if not employee and not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    if employee:
        employer = employee.employer or employee.user
        queues = CallQueue.objects.filter(user=employer, is_active=True).prefetch_related('memberships__employee')
    else:
        queues = CallQueue.objects.filter(user=request.user, is_active=True).prefetch_related('memberships__employee')
    r = None
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
    except Exception:
        pass

    results = []
    for q in queues:
        q_dict = q.to_dict()
        waiting_count = 0
        if r:
            try:
                waiting_count = r.llen(f"queue:{q.code}:waiting")
            except Exception:
                pass
        q_dict["waiting_calls_count"] = waiting_count
        results.append(q_dict)

    return JsonResponse({
        "status": "success",
        "queues": results
    })

@login_required(login_url='/login/')
def create_call_queue(request):
    """Create a new CallQueue and assign members."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    try:
        name = request.POST.get('name', '').strip() or "طابور المبيعات"
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        strategy = request.POST.get('strategy', 'round_robin').strip()
        ring_timeout = int(request.POST.get('ring_timeout_seconds', 15))
        total_timeout = int(request.POST.get('total_timeout_seconds', 60))
        fallback_action = request.POST.get('fallback_action', 'ai_assistant')

        if not code or not code.isdigit():
            return JsonResponse({"status": "error", "message": "يجب إدخال كود رقمي صحيح للطابور (مثل 200 أو 300)"}, status=400)

        if CallQueue.objects.filter(user=request.user, code=code).exists():
            return JsonResponse({"status": "error", "message": f"كود الطابور {code} مستخدم بالفعل لهذا الحساب"}, status=400)

        hold_music_file = request.FILES.get('hold_music')

        import asyncio
        trunk_id, rule_id = asyncio.run(_async_create_queue_trunk_and_rule(
            queue_name=name,
            queue_code=code,
            user_id=request.user.id
        ))

        tenant_context = None
        try:
            from telephony.models import get_or_create_tenant_context
            tenant_cfg = get_or_create_tenant_context(request.user)
            tenant_context = tenant_cfg.wazo_context
        except Exception as e:
            logger.warning(f"Could not resolve tenant context for queue: {e}")

        # Headless Wazo Queue Provisioning in Tenant Context
        wazo_q = wazo_client.create_queue(
            name=name,
            number=code,
            strategy=strategy,
            ring_timeout=ring_timeout,
            context=tenant_context
        )
        wazo_queue_id = str(wazo_q.get("id") or "")

        queue = CallQueue.objects.create(
            user=request.user,
            name=name,
            code=code,
            description=description,
            wazo_queue_id=wazo_queue_id,
            strategy=strategy,
            ring_timeout_seconds=ring_timeout,
            total_timeout_seconds=total_timeout,
            fallback_action=fallback_action,
            hold_music=hold_music_file,
            livekit_trunk_id=trunk_id or '',
            livekit_rule_id=rule_id or '',
            is_active=True
        )

        member_ids = request.POST.getlist('member_ids')
        for order_idx, emp_id in enumerate(member_ids):
            emp = EmployeeProfile.objects.filter(id=emp_id).first()
            if emp:
                QueueMembership.objects.create(
                    queue=queue,
                    employee=emp,
                    order=order_idx,
                    is_active=True
                )
                if queue.wazo_queue_id and emp.wazo_user_uuid:
                    try:
                        wazo_client.add_queue_member(queue.wazo_queue_id, emp.wazo_user_uuid, priority=order_idx)
                    except Exception as member_err:
                        logger.warning(f"Failed to sync member {emp.extension} to Wazo queue {queue.wazo_queue_id}: {member_err}")

        return JsonResponse({
            "status": "success",
            "message": f"تم إنشاء طابور '{name}' بنجاح في السنترال وتفعيل الكود {code}.",
            "queue": queue.to_dict()
        }, status=201)

    except Exception as e:
        logger.error(f"Error creating call queue: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": f"حدث خطأ أثناء إنشاء الطابور: {str(e)}"}, status=400)

@login_required(login_url='/login/')
def update_call_queue(request, queue_id):
    """Update call queue description and configuration."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    queue = get_object_or_404(CallQueue, id=queue_id, user=request.user)
    try:
        data = request.POST
        if not data and request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = {}

        if 'description' in data:
            queue.description = str(data.get('description') or '').strip()
        if 'name' in data and data.get('name'):
            queue.name = str(data.get('name')).strip()
        if 'strategy' in data and data.get('strategy'):
            queue.strategy = str(data.get('strategy')).strip()
        if 'ring_timeout_seconds' in data:
            queue.ring_timeout_seconds = int(data.get('ring_timeout_seconds'))
        if 'total_timeout_seconds' in data:
            queue.total_timeout_seconds = int(data.get('total_timeout_seconds'))

        if 'member_ids' in data or request.POST.getlist('member_ids'):
            member_ids = request.POST.getlist('member_ids') or data.get('member_ids', [])
            if not isinstance(member_ids, list):
                member_ids = [member_ids]

            current_memberships = QueueMembership.objects.filter(queue=queue)
            for m in current_memberships:
                if queue.wazo_queue_id and m.employee.wazo_user_uuid:
                    try:
                        wazo_client.remove_queue_member(queue.wazo_queue_id, m.employee.wazo_user_uuid)
                    except Exception as err:
                        logger.warning(f"Error removing member from Wazo queue: {err}")
            current_memberships.delete()

            for order_idx, emp_id in enumerate(member_ids):
                emp = EmployeeProfile.objects.filter(id=emp_id).first()
                if emp:
                    QueueMembership.objects.create(
                        queue=queue,
                        employee=emp,
                        order=order_idx,
                        is_active=True
                    )
                    if queue.wazo_queue_id and emp.wazo_user_uuid:
                        try:
                            wazo_client.add_queue_member(queue.wazo_queue_id, emp.wazo_user_uuid, priority=order_idx)
                        except Exception as member_err:
                            logger.warning(f"Failed to sync member {emp.extension} to Wazo queue {queue.wazo_queue_id}: {member_err}")

        queue.save()
        return JsonResponse({
            "status": "success",
            "message": f"تم تحديث إعدادات طابور '{queue.name}' بنجاح.",
            "queue": queue.to_dict()
        })
    except Exception as e:
        logger.error(f"Error updating call queue {queue_id}: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": f"حدث خطأ أثناء التحديث: {str(e)}"}, status=400)

@login_required(login_url='/login/')
def delete_call_queue(request, queue_id):
    """Delete a call queue."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    queue = get_object_or_404(CallQueue, id=queue_id, user=request.user)
    if queue.wazo_queue_id:
        wazo_client.delete_queue(queue.wazo_queue_id)
    name = queue.name
    queue.delete()
    return JsonResponse({"status": "success", "message": f"تم حذف الطابور '{name}' بنجاح."})

# ==================== Call Dialing & WebRTC APIs ====================

@csrf_exempt
def api_dial_call(request):
    """Initiate an internal WebRTC call to an employee extension or a Call Queue."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    caller = get_employee_from_token(request)
    if not caller:
        if hasattr(request, 'user') and request.user.is_authenticated:
            caller = EmployeeProfile.objects.filter(user=request.user).first()
            if not caller:
                caller = EmployeeProfile.objects.create(
                    user=request.user,
                    extension=f"99{request.user.id}",
                    display_name=request.user.get_full_name() or request.user.username or "المشرف (لوحة التحكم)",
                    department="الإدارة",
                    status="ready"
                )
        else:
            return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        target = str(data.get('target', '')).strip()

        if not target:
            return JsonResponse({"status": "error", "message": "يرجى تحديد رقم التحويلة أو كود الطابور للاتصال"}, status=400)

        # 0. Check if target is AI Assistant (Linked 1:1 to Employer Voice Room)
        # Supports plain '000', 'ai', or with simulated phone e.g. '000*01108124794', '000#01108124794', '000:01108124794'
        target_clean = target.strip()
        simulated_phone = str(data.get('customer_phone') or data.get('simulate_phone') or '').strip()
        is_ai_target = False
        target_lower = target_clean.lower()

        if target_lower in ['000', 'ai', 'assistant', 'bot', 'test_ai']:
            is_ai_target = True
        else:
            for sep in ['*', '#', ':', '/']:
                if sep in target_clean:
                    prefix, _, suffix = target_clean.partition(sep)
                    if prefix.strip().lower() in ['000', 'ai', 'assistant', 'bot', 'test_ai']:
                        is_ai_target = True
                        if not simulated_phone:
                            simulated_phone = suffix.strip()
                        break

        if is_ai_target:
            if not caller.is_owner:
                return JsonResponse({
                    "status": "error",
                    "message": "الاتصال بالمساعد الذكي مخصص فقط لحساب المالك أو المشرف"
                }, status=403)

            from agents.models import AgentProfile
            from telephony.models import BusinessHoursSchedule
            from crm.models import CustomerMemory

            # 1. Resolve Employer / Owner
            owner_user = caller.employer or caller.user
            if not owner_user:
                # If employer not set, resolve to main admin/superuser who created the profiles
                owner_user = User.objects.filter(is_superuser=True).order_by('id').first() or caller.user

            # 2. Resolve Active Profile belonging to the owner
            active_profile = AgentProfile.objects.filter(user=owner_user, is_active=True).first()
            if not active_profile:
                active_profile = AgentProfile.objects.filter(user=owner_user).first()
            if not active_profile:
                # Fallback to any active profile in system
                active_profile = AgentProfile.objects.filter(is_active=True).first()
                if active_profile:
                    owner_user = active_profile.user

            profile_dict = active_profile.to_dict() if active_profile else None
            ai_name = active_profile.name if active_profile else "المساعد الصوتي الذكي"

            # 2.1 Resolve caller_phone & CustomerMemory
            caller_phone = 'web_dashboard'
            matched_memory = None
            if simulated_phone:
                matched_memory = CustomerMemory.objects.filter(user=owner_user, phone_number=simulated_phone).first()
                if not matched_memory and len(simulated_phone) >= 7:
                    matched_memory = CustomerMemory.objects.filter(user=owner_user, phone_number__endswith=simulated_phone[-8:]).first()
                if matched_memory:
                    caller_phone = matched_memory.phone_number
                else:
                    caller_phone = simulated_phone

            # 3. Check Business Hours Schedule of the employer
            is_off_hours = False
            off_hours_data = None
            if owner_user:
                try:
                    b_sched = BusinessHoursSchedule.objects.filter(user=owner_user).first()
                    if b_sched and b_sched.is_enabled and not b_sched.is_within_business_hours():
                        is_off_hours = True
                        off_hours_data = {
                            "action_type": b_sched.action_type,
                            "ai_message": b_sched.ai_message,
                            "audio_file_url": b_sched.get_audio_url(request),
                            "voice_name": (profile_dict.get("voice_name") if profile_dict else "Aoede") or "Aoede"
                        }
                        logger.info(f"AI call from employee #{caller.id} ({caller.extension}) is OUTSIDE business hours for owner #{owner_user.id}. Action: {b_sched.action_type}")
                except Exception as b_err:
                    logger.warning(f"Error checking business hours for owner #{owner_user.id}: {b_err}")

            room_name = f"ai_test_{caller.id}_{uuid.uuid4().hex[:6]}"
            channel_name = f"rooms:{room_name}"

            token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
                .with_identity(f"employee_{caller.id}_{caller.extension}") \
                .with_name(caller.display_name) \
                .with_metadata(json.dumps({
                    "role": "caller",
                    "employee_id": caller.id,
                    "owner_user_id": owner_user.id,
                    "caller_phone": caller_phone
                })) \
                .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
            caller_jwt = token.to_jwt()

            # 4. Dispatch AI agent job to Redis matching web voice assistant room 1:1
            try:
                r = redis.Redis.from_url(settings.REDIS_URL)
                job_payload = json.dumps({
                    "room_name": room_name,
                    "user_id": owner_user.id,
                    "caller_phone": caller_phone,
                    "profile": profile_dict,
                    "is_queue": False,
                    "participant_identity": f"employee_{caller.id}_{caller.extension}",
                    "is_off_hours": is_off_hours,
                    "off_hours_data": off_hours_data
                })
                r.rpush("agent_jobs", job_payload)
                logger.info(f"Dispatched AI room '{room_name}' to Redis for employee {caller.display_name} mirrored to owner {owner_user.username} [caller_phone={caller_phone}, off_hours={is_off_hours}]")
            except Exception as ex:
                logger.error(f"Failed to dispatch AI test call room '{room_name}' to Redis: {ex}")

            # Notify Centrifugo room channel
            if is_off_hours:
                publish_to_centrifugo(channel_name, {
                    "event": "off_hours_call",
                    "message": "المكالمة واردة خارج أوقات العمل الرسمية للمنشأة. جاري تطبيق خطة الرد المحددة...",
                    "timestamp": time.time(),
                })
            else:
                publish_to_centrifugo(channel_name, {
                    "event": "agent_queued",
                    "message": f"تم استدعاء المساعد الصوتي ({ai_name}) وتجهيز مستندات وقواعد معرفة المنشأة...",
                    "timestamp": time.time(),
                })

            # Log outbound call for employee
            sim_label = f" (محاكاة العميل: {caller_phone})" if caller_phone != 'web_dashboard' else ""
            EmployeeCallLog.objects.create(
                employee=caller,
                other_party=f"تجربة المساعد الذكي ({ai_name}){sim_label}",
                extension="000",
                room_name=room_name,
                call_type='outbound',
            )

            # Update caller status to busy
            if caller.status != 'busy':
                caller.status = 'busy'
                caller.save(update_fields=['status'])
                publish_to_centrifugo("employees:presence", {
                    "event": "status_change",
                    "employee": caller.to_dict()
                })

            return JsonResponse({
                "status": "success",
                "call_type": "ai_test",
                "room_name": room_name,
                "target_name": f"🤖 {ai_name}",
                "target_number": "000",
                "caller_phone": caller_phone,
                "simulated_customer": matched_memory.to_dict() if matched_memory else None,
                "livekit_url": settings.LIVEKIT_URL,
                "livekit_token": caller_jwt,
                "is_off_hours": is_off_hours
            })

        employer = caller.employer or caller.user

        # 1. Check if target is a CallQueue
        queue = CallQueue.objects.filter(user=employer, code=target, is_active=True).first()
        if not queue:
            queue = CallQueue.objects.filter(code=target, is_active=True).first()
        if queue:
            room_name = f"queue_{queue.code}_{uuid.uuid4().hex[:6]}"

            token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
                .with_identity(f"employee_{caller.id}_{caller.extension}") \
                .with_name(caller.display_name) \
                .with_metadata(json.dumps({"role": "caller", "employee_id": caller.id})) \
                .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
            caller_jwt = token.to_jwt()

            # Broadcast incoming call to queue members
            members = queue.memberships.filter(is_active=True).select_related('employee')
            notified_count = 0
            ringing_emp_ids = []
            for m in members:
                if m.employee and m.employee.id != caller.id and m.employee.status == 'ready':
                    call_payload = {
                        "event": "incoming_call",
                        "room_name": room_name,
                        "caller_name": caller.display_name,
                        "caller_extension": caller.extension,
                        "caller_department": caller.department,
                        "queue_name": queue.name,
                        "queue_code": queue.code,
                        "call_type": "queue"
                    }
                    publish_to_centrifugo(f"employee:{m.employee.id}", call_payload)
                    ringing_emp_ids.append(m.employee.id)
                    try:
                        r = redis.Redis.from_url(settings.REDIS_URL)
                        r.set(f"call_center:ringing:employee:{m.employee.id}", json.dumps(call_payload), ex=45)
                    except Exception as re:
                        logger.warning(f"Redis queue ringing set error: {re}")

                    if m.employee.push_token:
                        send_expo_push_notification(
                            m.employee.push_token,
                            f"مكالمة واردة: {queue.name}",
                            f"اتصال وارد من {caller.display_name} ({caller.extension})",
                            call_payload
                        )
                    notified_count += 1

            if ringing_emp_ids:
                try:
                    r = redis.Redis.from_url(settings.REDIS_URL)
                    r.set(f"call_center:ringing:room:{room_name}", json.dumps(ringing_emp_ids), ex=60)
                except Exception as re:
                    pass

            return JsonResponse({
                "status": "success",
                "call_type": "queue",
                "room_name": room_name,
                "target_name": queue.name,
                "target_number": queue.code,
                "livekit_url": settings.LIVEKIT_URL,
                "livekit_token": caller_jwt,
                "notified_agents": notified_count
            })

        # 2. Check if target is an Employee Extension
        callee = EmployeeProfile.objects.filter(employer=employer, extension=target, is_active=True).first()
        if not callee:
            callee = EmployeeProfile.objects.filter(extension=target, is_active=True).first()
        if callee:
            if callee.id == caller.id:
                return JsonResponse({"status": "error", "message": "لا يمكنك الاتصال بتحويلتك الشخصية"}, status=400)

            room_name = f"call_ext_{caller.extension}_{callee.extension}_{uuid.uuid4().hex[:6]}"

            token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
                .with_identity(f"employee_{caller.id}_{caller.extension}") \
                .with_name(caller.display_name) \
                .with_metadata(json.dumps({"role": "caller", "employee_id": caller.id})) \
                .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
            caller_jwt = token.to_jwt()

            callee_payload = {
                "event": "incoming_call",
                "room_name": room_name,
                "caller_name": caller.display_name,
                "caller_extension": caller.extension,
                "caller_department": caller.department,
                "call_type": "direct_internal"
            }
            publish_to_centrifugo(f"employee:{callee.id}", callee_payload)
            try:
                r = redis.Redis.from_url(settings.REDIS_URL)
                r.set(f"call_center:ringing:employee:{callee.id}", json.dumps(callee_payload), ex=45)
                r.set(f"call_center:ringing:room:{room_name}", json.dumps([callee.id]), ex=60)
            except Exception as re:
                logger.warning(f"Redis direct ringing set error: {re}")

            if callee.push_token:
                send_expo_push_notification(
                    callee.push_token,
                    "مكالمة واردة",
                    f"اتصال وارد من {caller.display_name} (#{caller.extension})",
                    callee_payload
                )

            # ── Log outbound for caller ──
            EmployeeCallLog.objects.create(
                employee=caller,
                other_party=callee.display_name,
                extension=callee.extension,
                room_name=room_name,
                call_type='outbound',
            )

            # Mark caller status as busy
            if caller.status != 'busy':
                caller.status = 'busy'
                caller.save(update_fields=['status'])
                publish_to_centrifugo("employees:presence", {
                    "event": "status_change",
                    "employee": caller.to_dict()
                })

            return JsonResponse({
                "status": "success",
                "call_type": "direct_internal",
                "room_name": room_name,
                "target_name": callee.display_name,
                "target_number": callee.extension,
                "target_status": callee.status,
                "livekit_url": settings.LIVEKIT_URL,
                "livekit_token": caller_jwt
            })

        # 3. Check if target is an External Phone Number (PSTN via telephony app)
        cleaned_phone = re.sub(r'[^\d+]', '', target)
        if len(cleaned_phone) >= 7:
            from telephony.models import OutboundSIPTrunk
            from crm.models import CallSession
            trunk = OutboundSIPTrunk.objects.filter(is_active=True).first()
            if not trunk or not trunk.livekit_outbound_trunk_id:
                return JsonResponse({
                    "status": "error",
                    "message": "لا يوجد خط SIP Trunk خارجي مفعل. يرجى إعداد بيانات المزود الخارجي أولاً."
                }, status=400)

            room_name = f"pstn_out_{caller.extension}_{uuid.uuid4().hex[:6]}"

            token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
                .with_identity(f"employee_{caller.id}_{caller.extension}") \
                .with_name(caller.display_name) \
                .with_metadata(json.dumps({"role": "caller", "employee_id": caller.id, "phone": cleaned_phone})) \
                .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
            caller_jwt = token.to_jwt()

            CallSession.objects.create(
                user=caller.user,
                room_name=room_name,
                direction='outbound_agent',
                destination_phone=cleaned_phone,
                call_goal=f"مكالمة موظف ({caller.display_name}) لرقم العميل {cleaned_phone}"
            )

            import asyncio
            async def _dial_external_customer():
                lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
                try:
                    dial_req = api.CreateSIPParticipantRequest(
                        sip_trunk_id=trunk.livekit_outbound_trunk_id,
                        sip_call_to=cleaned_phone,
                        room_name=room_name,
                        participant_identity=f"customer_{cleaned_phone}",
                        participant_name=f"Customer {cleaned_phone}",
                        play_ringtone=True,
                    )
                    await lk.sip.create_sip_participant(dial_req)
                finally:
                    await lk.aclose()

            try:
                asyncio.run(_dial_external_customer())
            except Exception as e:
                logger.error(f"Failed to dial external customer via SIP trunk: {e}")

            # Trigger Egress recording for external PSTN call
            try:
                from voice_assistant.egress_service import start_room_recording
                start_room_recording(room_name)
            except Exception as eg_err:
                logger.warning(f"Could not trigger egress recording for PSTN room {room_name}: {eg_err}")

            return JsonResponse({
                "status": "success",
                "call_type": "external_pstn",
                "room_name": room_name,
                "target_name": f"عميل خارجي ({cleaned_phone})",
                "target_number": cleaned_phone,
                "livekit_url": settings.LIVEKIT_URL,
                "livekit_token": caller_jwt
            })

        return JsonResponse({"status": "error", "message": f"التحويلة أو كود الطابور '{target}' غير موجود"}, status=404)

    except Exception as e:
        logger.error(f"Error in api_dial_call: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
def api_get_call_token(request):
    """Generate LiveKit token for callee to answer and join an active WebRTC room."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        room_name = data.get('room_name')
        if not room_name:
            return JsonResponse({"status": "error", "message": "room_name مطلوب"}, status=400)

        token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
            .with_identity(f"employee_{employee.id}_{employee.extension}") \
            .with_name(employee.display_name) \
            .with_metadata(json.dumps({"role": "callee", "employee_id": employee.id})) \
            .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
        callee_jwt = token.to_jwt()

        publish_to_centrifugo("queues:broadcast", {
            "event": "call_accepted",
            "room_name": room_name,
            "accepted_by": employee.to_dict()
        })

        # Clear ringing records from Redis for answering employee and room
        try:
            r = redis.Redis.from_url(settings.REDIS_URL)
            r.delete(f"call_center:ringing:employee:{employee.id}")
            room_ringing = r.get(f"call_center:ringing:room:{room_name}")
            if room_ringing:
                emp_ids = json.loads(room_ringing.decode('utf-8'))
                for eid in emp_ids:
                    r.delete(f"call_center:ringing:employee:{eid}")
                r.delete(f"call_center:ringing:room:{room_name}")
        except Exception as re:
            logger.warning(f"Error clearing ringing state on answer: {re}")

        # ── Determine caller info from room_name and log inbound for the answering employee ──
        caller_name = "عميل / طابور"
        caller_ext = ""
        if room_name.startswith("call_ext_"):
            parts = room_name.split("_")
            if len(parts) >= 4:
                caller_ext = parts[2]  # first extension in call_ext_{ext1}_{ext2}_{uuid}
                caller_profile = EmployeeProfile.objects.filter(extension=caller_ext, is_active=True).first()
                if caller_profile:
                    caller_name = caller_profile.display_name
        elif room_name.startswith("queue_"):
            parts = room_name.split("_")
            if len(parts) >= 2:
                caller_ext = parts[1]
                caller_name = f"طابور {caller_ext}"

        # Only create inbound log if not already logged (avoid duplicate on re-answer)
        if not EmployeeCallLog.objects.filter(employee=employee, room_name=room_name, call_type='inbound').exists():
            EmployeeCallLog.objects.create(
                employee=employee,
                other_party=caller_name,
                extension=caller_ext,
                room_name=room_name,
                call_type='inbound',
            )

        # Trigger Egress recording for this answered call
        try:
            from voice_assistant.egress_service import start_room_recording
            start_room_recording(room_name)
        except Exception as eg_err:
            logger.warning(f"Could not trigger egress recording for answered room {room_name}: {eg_err}")

        # Mark answering employee as busy
        if employee.status != 'busy':
            employee.status = 'busy'
            employee.save(update_fields=['status'])
            publish_to_centrifugo("employees:presence", {
                "event": "status_change",
                "employee": employee.to_dict()
            })

        return JsonResponse({
            "status": "success",
            "room_name": room_name,
            "livekit_url": settings.LIVEKIT_URL,
            "livekit_token": callee_jwt
        })

    except Exception as e:
        logger.error(f"Error in api_get_call_token: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
def api_hangup_call(request):
    """Signal call hangup/end to room participants and delete LiveKit room."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    caller_name = "المشرف"
    if not employee:
        if request.user.is_authenticated:
            caller_name = request.user.get_full_name() or request.user.username or "العميل"
        else:
            caller_name = "العميل"
    else:
        caller_name = employee.display_name

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        room_name = data.get('room_name') or data.get('call_id')
        target_employee_id = data.get('target_employee_id')

        if not room_name and not target_employee_id:
            return JsonResponse({"status": "error", "message": "room_name or target_employee_id is required"}, status=400)

        r = redis.Redis.from_url(settings.REDIS_URL)

        # 0. Check if this room is in the middle of a transfer / queue ringing
        active_transfer_id = r.get(f"room:{room_name}:transfer_id") if room_name else None
        if active_transfer_id:
            if isinstance(active_transfer_id, bytes):
                active_transfer_id = active_transfer_id.decode('utf-8')
            logger.info(f"Hangup called while transfer {active_transfer_id} is active for room {room_name}. Cancelling transfer.")
            r.set(f"transfer:{active_transfer_id}:state", "cancelled", ex=300)
            current_cand = r.get(f"transfer:{active_transfer_id}:current_candidate")
            if current_cand:
                if isinstance(current_cand, bytes):
                    current_cand = current_cand.decode('utf-8')
                publish_to_centrifugo(f"employee:{current_cand}", {
                    "event": "call_ended",
                    "transfer_id": active_transfer_id,
                    "room_name": room_name,
                    "reason": "cancelled"
                })
            try:
                async_to_sync(inngest_client.send)(
                    inngest.Event(
                        name="call_center/transfer.action",
                        data={
                            "transfer_id": active_transfer_id,
                            "action": "cancel",
                            "reason": "caller_hungup"
                        }
                    )
                )
            except Exception as inngest_err:
                logger.warning(f"Error cancelling Inngest transfer: {inngest_err}")

        # Always clear transferring keys and ringing keys when hangup is requested
        if room_name:
            r.delete(f"room:{room_name}:is_transferring")
            r.delete(f"room:{room_name}:transfer_id")
            room_ringing = r.get(f"call_center:ringing:room:{room_name}")
            if room_ringing:
                try:
                    emp_ids = json.loads(room_ringing.decode('utf-8'))
                    for eid in emp_ids:
                        r.delete(f"call_center:ringing:employee:{eid}")
                    r.delete(f"call_center:ringing:room:{room_name}")
                except Exception as re:
                    pass

        if employee:
            r.delete(f"call_center:ringing:employee:{employee.id}")

        # 1. Direct peer employee channel notification if explicitly provided
        if target_employee_id:
            publish_to_centrifugo(f"employee:{target_employee_id}", {
                "event": "call_ended",
                "room_name": room_name,
                "ended_by": caller_name
            })

        # 2. Extract peers for internal employee-to-employee calls (call_ext_{ext1}_{ext2}_{uuid})
        if room_name and room_name.startswith("call_ext_"):
            parts = room_name.split("_")
            if len(parts) >= 4:
                ext1, ext2 = parts[2], parts[3]
                peers = EmployeeProfile.objects.filter(extension__in=[ext1, ext2], is_active=True)
                for peer in peers:
                    publish_to_centrifugo(f"employee:{peer.id}", {
                        "event": "call_ended",
                        "room_name": room_name,
                        "ended_by": caller_name
                    })

        # 3. Extract queue members if queue call (queue_{code}_{uuid})
        if room_name and room_name.startswith("queue_"):
            parts = room_name.split("_")
            if len(parts) >= 2:
                q_code = parts[1]
                queue = CallQueue.objects.filter(code=q_code, is_active=True).first()
                if queue:
                    for m in queue.memberships.filter(is_active=True).select_related('employee'):
                        if m.employee:
                            publish_to_centrifugo(f"employee:{m.employee.id}", {
                                "event": "call_ended",
                                "room_name": room_name,
                                "ended_by": caller_name
                            })

        # 4. Notify customer via room channel (rooms:{room_name})
        if room_name:
            publish_to_centrifugo(f"rooms:{room_name}", {
                "event": "call_ended",
                "room_name": room_name,
                "ended_by": caller_name
            })

        # 5. Broadcast on global queues channel
        publish_to_centrifugo("queues:broadcast", {
            "event": "call_ended",
            "room_name": room_name,
            "ended_by": caller_name
        })

        # 6. Complete all open call logs for this room and notify employees + reset status
        if room_name:
            from django.utils import timezone
            from crm.models import CallSession
            import math
            now = timezone.now()
            for sess in CallSession.objects.filter(room_name=room_name, ended_at__isnull=True):
                sess.ended_at = now
                d_sec = max(int((now - sess.started_at).total_seconds()), 0)
                sess.duration_seconds = d_sec
                sess.billed_minutes = math.ceil(d_sec / 60.0) if d_sec > 0 else 0
                sess.save(update_fields=['ended_at', 'duration_seconds', 'billed_minutes'])

            open_logs = EmployeeCallLog.objects.filter(room_name=room_name, ended_at__isnull=True).select_related('employee')
            for log in open_logs:
                elapsed = int((now - log.started_at).total_seconds())
                log.ended_at = now
                log.duration_secs = max(elapsed, 0)
                # Mark missed if duration < 3 seconds (caller hung up before answer)
                if log.duration_secs < 3 and log.call_type == 'inbound':
                    log.call_type = 'missed'
                log.save(update_fields=['ended_at', 'duration_secs', 'call_type'])

                if log.employee:
                    publish_to_centrifugo(f"employee:{log.employee.id}", {
                        "event": "call_ended",
                        "room_name": room_name,
                        "ended_by": caller_name
                    })
                    if log.employee.status == 'busy':
                        log.employee.status = 'ready'
                        log.employee.save(update_fields=['status'])
                        publish_to_centrifugo("employees:presence", {
                            "event": "status_change",
                            "employee": log.employee.to_dict()
                        })

        # 7. Clean up and delete room on LiveKit server
        if room_name:
            import asyncio
            async def _delete_livekit_room():
                try:
                    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
                    await lk.room.delete_room(api.DeleteRoomRequest(room=room_name))
                    await lk.aclose()
                except Exception as lk_err:
                    logger.debug(f"LiveKit room deletion note: {lk_err}")

            try:
                asyncio.run(_delete_livekit_room())
            except Exception as e:
                logger.warning(f"Failed to delete LiveKit room {room_name}: {e}")

        # 8. Restore calling employee status to ready if caller is employee
        if employee and employee.status == 'busy':
            employee.status = 'ready'
            employee.save(update_fields=['status'])
            publish_to_centrifugo("employees:presence", {
                "event": "status_change",
                "employee": employee.to_dict()
            })

        # 9. Restore peer employees to ready if internal call
        if room_name and room_name.startswith("call_ext_"):
            parts = room_name.split("_")
            if len(parts) >= 4:
                ext1, ext2 = parts[2], parts[3]
                peers = EmployeeProfile.objects.filter(extension__in=[ext1, ext2], is_active=True)
                for peer in peers:
                    if peer.status == 'busy':
                        peer.status = 'ready'
                        peer.save(update_fields=['status'])
                        publish_to_centrifugo("employees:presence", {
                            "event": "status_change",
                            "employee": peer.to_dict()
                        })

        return JsonResponse({"status": "success", "message": "Call hung up and room cleaned up"})

    except Exception as e:
        logger.error(f"Error in api_hangup_call: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
def api_transfer_call(request):
    """
    Handle Clean Call Transfer from an active WebRTC session to another employee or call queue.
    - Closes room_A immediately on LiveKit.
    - Finalizes Employee 2's call log.
    - Puts Caller (Employee 1) on local HOLD with Centrifugo notification.
    - Triggers durable Inngest queue hunting workflow.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        room_name = data.get('room_name')
        target = str(data.get('target', '')).strip()

        if not room_name or not target:
            return JsonResponse({"status": "error", "message": "room_name و target مطلوبان"}, status=400)

        # 1. Target resolution
        target_emp = EmployeeProfile.objects.filter(
            extension=target,
            is_active=True
        ).exclude(id=employee.id).first()

        target_queue = None
        if not target_emp:
            target_queue = CallQueue.objects.filter(
                code=target,
                is_active=True
            ).first()

        if not target_emp and not target_queue:
            return JsonResponse({"status": "error", "message": f"التحويلة أو الطابور '{target}' غير موجود"}, status=404)

        if target_emp:
            target_name = target_emp.display_name
            target_type = "employee"
            target_id = target_emp.id
            q_membership = QueueMembership.objects.filter(employee=target_emp, is_active=True).first()
            queue = q_membership.queue if q_membership else CallQueue.objects.filter(is_active=True).first()
            other_cands = []
            if queue:
                other_cands = list(
                    queue.memberships.filter(is_active=True)
                    .exclude(employee_id__in=[target_emp.id, employee.id])
                    .order_by('order')
                    .values_list('employee_id', flat=True)
                )
            candidate_ids = [target_emp.id] + other_cands
        else:
            target_name = target_queue.name
            target_type = "queue"
            target_id = target_queue.id
            queue = target_queue
            candidate_ids = list(
                queue.memberships.filter(is_active=True)
                .exclude(employee_id=employee.id)
                .order_by('order')
                .values_list('employee_id', flat=True)
            )

        if not candidate_ids:
            return JsonResponse({"status": "error", "message": "لا يوجد موظفون في هذا الطابور للتحويل إليهم"}, status=400)

        # 2. Identify Caller (Employee 1, the other party in room)
        caller_id = data.get('caller_id')
        caller_name = ""
        caller_ext = ""

        if caller_id:
            caller_emp = EmployeeProfile.objects.filter(id=caller_id, is_active=True).first()
            if caller_emp:
                caller_name = caller_emp.display_name
                caller_ext = caller_emp.extension

        if not caller_ext:
            other_log = EmployeeCallLog.objects.filter(room_name=room_name).exclude(employee=employee).first()
            if other_log and other_log.employee:
                caller_id = other_log.employee.id
                caller_name = other_log.employee.display_name
                caller_ext = other_log.employee.extension

        if not caller_ext and "call_ext_" in room_name:
            parts = room_name.replace("call_ext_", "").split("_")
            if len(parts) >= 2:
                other_ext = parts[0] if parts[1] == employee.extension else parts[1]
                caller_emp = EmployeeProfile.objects.filter(extension=other_ext, is_active=True).first()
                if caller_emp:
                    caller_id = caller_emp.id
                    caller_name = caller_emp.display_name
                    caller_ext = caller_emp.extension

        if not caller_ext:
            caller_ext = "unknown"
            caller_name = "المتصل"

        # 3. Finalize Employee 2's call log
        now = timezone.now()
        my_log = EmployeeCallLog.objects.filter(room_name=room_name, employee=employee, ended_at__isnull=True).first()
        if my_log:
            elapsed = int((now - my_log.started_at).total_seconds())
            my_log.ended_at = now
            my_log.duration_secs = max(elapsed, 0)
            my_log.save(update_fields=['ended_at', 'duration_secs'])

        # Detach transferring employee immediately: set status to 'ready'
        employee.status = "ready"
        employee.save(update_fields=['status'])
        publish_to_centrifugo("employees:presence", {
            "event": "status_change",
            "employee": employee.to_dict()
        })

        # 4. Generate transfer_id and store state in Redis
        transfer_id = f"tr_{uuid.uuid4().hex[:8]}"
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.set(f"transfer:{transfer_id}:caller_id", caller_id or "", ex=300)
        r.set(f"transfer:{transfer_id}:from_id", employee.id, ex=300)
        r.set(f"transfer:{transfer_id}:state", "ringing", ex=300)
        r.set(f"room:{room_name}:is_transferring", "true", ex=120)
        r.set(f"room:{room_name}:transfer_id", transfer_id, ex=300)

        # 5. Notify Caller (Employee 1) on HOLD FIRST so their client is in HOLD state
        if caller_id:
            publish_to_centrifugo(f"employee:{caller_id}", {
                "event": "transfer_hold",
                "transfer_id": transfer_id,
                "transferred_by": employee.display_name,
                "target_name": target_name,
                "message": f"جاري تحويل مكالمتك إلى {target_name}، يرجى الانتظار...",
                "hold_audio_url": "https://assets.mixkit.co/active_storage/sfx/2874/2874-preview.mp3",
                "timestamp": time.time()
            })

        # 6. Delete old LiveKit room cleanly
        import asyncio
        async def _delete_old_room():
            await asyncio.sleep(0.3)
            try:
                lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
                await lk.room.delete_room(api.DeleteRoomRequest(room=room_name))
                await lk.aclose()
            except Exception as lk_err:
                logger.debug(f"LiveKit room deletion note: {lk_err}")
        try:
            asyncio.run(_delete_old_room())
        except Exception as e:
            logger.warning(f"Failed to delete old room {room_name}: {e}")

        # 7. Dispatch Inngest event
        ring_timeout = queue.ring_timeout_seconds if queue else 15
        total_timeout = queue.total_timeout_seconds if queue else 60
        async_to_sync(inngest_client.send)(
            inngest.Event(
                name="call_center/transfer.requested",
                data={
                    "transfer_id": transfer_id,
                    "old_room_name": room_name,
                    "from_employee_id": employee.id,
                    "from_employee_name": employee.display_name,
                    "from_employee_extension": employee.extension,
                    "caller_id": caller_id,
                    "caller_name": caller_name,
                    "caller_extension": caller_ext,
                    "candidate_ids": candidate_ids,
                    "ring_timeout_seconds": ring_timeout,
                    "total_timeout_seconds": total_timeout,
                }
            )
        )

        logger.info(f"Initiated clean call transfer {transfer_id} from {employee.extension} to {target_name} (candidates: {candidate_ids})")

        return JsonResponse({
            "status": "success",
            "message": f"جاري تحويل المكالمة إلى {target_name} ({target})",
            "transfer_id": transfer_id,
            "target": target,
            "target_name": target_name,
            "target_type": target_type,
            "caller_name": caller_name,
            "caller_extension": caller_ext
        })

    except Exception as e:
        logger.error(f"Error in api_transfer_call: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_transfer_cancel(request):
    """Cancel an ongoing call transfer and restore the call with the original caller."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        transfer_id = str(data.get('transfer_id', '')).strip()

        if not transfer_id:
            return JsonResponse({"status": "error", "message": "transfer_id مطلوب"}, status=400)

        r = redis.Redis.from_url(settings.REDIS_URL)
        r.set(f"transfer:{transfer_id}:state", "cancelled", ex=300)

        async_to_sync(inngest_client.send)(
            inngest.Event(
                name="call_center/transfer.action",
                data={
                    "transfer_id": transfer_id,
                    "employee_id": employee.id,
                    "action": "cancel"
                }
            )
        )

        logger.info(f"Transfer {transfer_id} cancelled by employee {employee.extension}")
        return JsonResponse({"status": "success", "message": "تم إلغاء التحويل واستعادة المكالمة"})

    except Exception as e:
        logger.error(f"Error in api_transfer_cancel: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_transfer_action(request):
    """Handle candidate answer or reject for a transferred call."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    employee = get_employee_from_token(request)
    if not employee:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        transfer_id = str(data.get('transfer_id', '')).strip()
        action = str(data.get('action', '')).strip()

        if not transfer_id or action not in ['answer', 'reject']:
            return JsonResponse({"status": "error", "message": "transfer_id و action ('answer' / 'reject') مطلوبان"}, status=400)

        async_to_sync(inngest_client.send)(
            inngest.Event(
                name="call_center/transfer.action",
                data={
                    "transfer_id": transfer_id,
                    "employee_id": employee.id,
                    "action": action
                }
            )
        )

        try:
            r = redis.Redis.from_url(settings.REDIS_URL)
            r.delete(f"call_center:ringing:employee:{employee.id}")
        except Exception:
            pass

        return JsonResponse({"status": "success", "action": action})

    except Exception as e:
        logger.error(f"Error in api_transfer_action: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ==================== Call Logs APIs ====================

@csrf_exempt
def api_list_call_logs(request):
    """
    GET /api/call-center/calls/logs/
    Returns call history.
    - If accessed by Employee via Bearer token:
        Returns employee's logs. If NOT employee.is_owner, recording_url is stripped.
    - If accessed by Employer/Owner via web session:
        Filtered strictly to employee__employer=request.user (unless superuser).
        Includes recording_url for playback and supports ?employee_id=, ?call_type=, ?search=, ?has_recording=.
    """
    from django.db.models import Q

    employee = get_employee_from_token(request)

    # 1. Employer / Admin session auth (Owner dashboard)
    if not employee:
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

        qs = EmployeeCallLog.objects.select_related('employee')
        if not request.user.is_superuser:
            qs = qs.filter(employee__employer=request.user)

        # Filter by specific employee
        emp_id = request.GET.get("employee_id")
        if emp_id:
            qs = qs.filter(employee_id=emp_id)

        # Filter by call type (inbound, outbound, missed, transfer)
        call_type = request.GET.get("call_type")
        if call_type and call_type in ['inbound', 'outbound', 'missed', 'transfer']:
            qs = qs.filter(call_type=call_type)

        # Filter by recording presence
        has_recording = request.GET.get("has_recording")
        if has_recording == "true":
            qs = qs.exclude(recording_url='').exclude(recording_url__isnull=True)

        # Search filter
        search = request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(other_party__icontains=search) |
                Q(extension__icontains=search) |
                Q(employee__display_name__icontains=search) |
                Q(employee__extension__icontains=search)
            )

        limit = min(int(request.GET.get("limit", 200)), 500)
        logs = qs.order_by("-started_at")[:limit]

        return JsonResponse({
            "status": "success",
            "logs": [
                {
                    **log.to_dict(),
                    "employee_name": log.employee.display_name,
                    "employee_ext": log.employee.extension,
                    "employee_department": log.employee.department,
                }
                for log in logs
            ],
            "count": len(logs)
        })

    # 2. Employee Bearer token auth (Employee Mobile/Web App)
    limit = min(int(request.GET.get("limit", 100)), 500)
    logs = EmployeeCallLog.objects.filter(employee=employee).order_by("-started_at")[:limit]

    # PRIVACY ENFORCEMENT:
    # Regular employees must NEVER see or receive audio recording links.
    sanitized_logs = []
    for log in logs:
        log_data = log.to_dict()
        if not employee.is_owner:
            log_data["recording_url"] = ""
        sanitized_logs.append(log_data)

    return JsonResponse({
        "status": "success",
        "employee": employee.to_dict(),
        "logs": sanitized_logs,
        "count": len(sanitized_logs)
    })


@csrf_exempt
def api_internal_ai_transfer(request):
    """
    Internal API called by the Voice AI agent to transfer a customer to a tenant's CallQueue.
    Uses the exact Inngest transfer workflow fn_transfer_call_queue.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    from agents.views import verify_internal_api_key
    if not verify_internal_api_key(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        room_name = str(data.get('room_name', '')).strip()
        queue_code = str(data.get('queue_code', '')).strip()
        user_id = data.get('user_id')
        caller_phone = str(data.get('caller_phone', '')).strip()
        caller_name = str(data.get('caller_name', 'العميل المتصل')).strip()
        reason = str(data.get('reason', '')).strip()

        if not room_name or not queue_code:
            return JsonResponse({"status": "error", "message": "room_name و queue_code مطلوبان"}, status=400)

        # 1. Resolve Queue for this tenant/user
        queue = None
        if user_id:
            queue = CallQueue.objects.filter(user_id=user_id, code=queue_code, is_active=True).first()
        if not queue:
            queue = CallQueue.objects.filter(code=queue_code, is_active=True).first()

        if not queue:
            return JsonResponse({"status": "error", "message": f"طابور الانتظار '{queue_code}' غير موجود أو غير نشط"}, status=404)

        candidate_ids = list(
            queue.memberships.filter(is_active=True)
            .order_by('order')
            .values_list('employee_id', flat=True)
        )

        if not candidate_ids:
            return JsonResponse({"status": "error", "message": f"لا يوجد موظفون في طابور '{queue.name}' للتحويل إليهم"}, status=400)

        # 2. Generate transfer_id and store state in Redis
        total_timeout = queue.total_timeout_seconds or 300
        ring_timeout = queue.ring_timeout_seconds or 15

        transfer_id = f"tr_{uuid.uuid4().hex[:8]}"
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.set(f"transfer:{transfer_id}:from_ai", "true", ex=total_timeout + 60)
        r.set(f"transfer:{transfer_id}:caller_phone", caller_phone, ex=total_timeout + 60)
        r.set(f"transfer:{transfer_id}:state", "ringing", ex=total_timeout + 60)
        r.set(f"room:{room_name}:is_transferring", "true", ex=total_timeout + 60)
        r.set(f"room:{room_name}:transfer_id", transfer_id, ex=total_timeout + 60)

        # 3. Notify room on Centrifugo
        publish_to_centrifugo(f"rooms:{room_name}", {
            "event": "transfer_hold",
            "transfer_id": transfer_id,
            "transferred_by": "المساعد الذكي (AI)",
            "target_name": queue.name,
            "message": f"جاري تحويل مكالمتك إلى {queue.name}، يرجى الانتظار...",
            "hold_audio_url": "https://assets.mixkit.co/active_storage/sfx/2874/2874-preview.mp3",
            "timestamp": time.time()
        })

        # 4. Dispatch Inngest event to run fn_transfer_call_queue
        async_to_sync(inngest_client.send)(
            inngest.Event(
                name="call_center/transfer.requested",
                data={
                    "transfer_id": transfer_id,
                    "old_room_name": room_name,
                    "from_employee_id": 0,
                    "from_employee_name": "المساعد الذكي (AI)",
                    "from_employee_extension": "AI",
                    "caller_id": None,
                    "caller_name": caller_name,
                    "caller_extension": caller_phone or "العميل",
                    "candidate_ids": candidate_ids,
                    "ring_timeout_seconds": ring_timeout,
                    "total_timeout_seconds": total_timeout,
                    "reason": reason,
                }
            )
        )

        logger.info(f"AI initiated call transfer {transfer_id} in room {room_name} to queue {queue.name} ({queue.code}) - candidates: {candidate_ids}")

        return JsonResponse({
            "status": "success",
            "message": f"تم بدء تحويل المكالمة إلى طابور {queue.name}",
            "transfer_id": transfer_id,
            "queue_name": queue.name,
            "queue_code": queue.code,
            "candidates_count": len(candidate_ids)
        })

    except Exception as e:
        logger.error(f"Error in api_internal_ai_transfer: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_internal_asterisk_cdr(request):
    """
    Internal Webhook called by Asterisk Hangup Handler upon completion of non-AI
    calls (inter-employee calls, transferred queue calls, direct SIP extensions).
    Logs the call into CallSession (crm) and EmployeeCallLog (call_center),
    links the audio recording file from Asterisk MixMonitor, and broadcasts real-time events.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        if request.POST:
            caller = str(request.POST.get('caller', '')).strip()
            callee = str(request.POST.get('callee', '')).strip()
            duration_str = str(request.POST.get('duration', '0')).strip()
            total_duration_str = str(request.POST.get('total_duration', '0')).strip()
            status = str(request.POST.get('status', 'ANSWERED')).strip().upper()
            uniqueid = str(request.POST.get('uniqueid', '')).strip()
            recording = str(request.POST.get('recording', '')).strip()
            context = str(request.POST.get('context', '')).strip()
        else:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
            caller = str(data.get('caller', '')).strip()
            callee = str(data.get('callee', '')).strip()
            duration_str = str(data.get('duration', '0')).strip()
            total_duration_str = str(data.get('total_duration', '0')).strip()
            status = str(data.get('status', 'ANSWERED')).strip().upper()
            uniqueid = str(data.get('uniqueid', '')).strip()
            recording = str(data.get('recording', '')).strip()
            context = str(data.get('context', '')).strip()

        try:
            duration = int(float(duration_str or 0))
        except ValueError:
            duration = 0

        try:
            total_duration = int(float(total_duration_str or 0))
        except ValueError:
            total_duration = duration

        # Ignore AI-only calls (AI agent directly connects to 999 or livekit-ai and handles its own sessions)
        if (caller == 'livekit-ai' and callee == '999') or (callee == '999' and not caller):
            return JsonResponse({"status": "ignored", "message": "Handled by LiveKit AI"})

        # Resolve tenant user and employee profiles
        from telephony.models import resolve_tenant_from_context_and_ext
        tenant_user, caller_emp, _ = resolve_tenant_from_context_and_ext(context, caller)

        # Callee lookup
        callee_emp = None
        if callee:
            callee_emp = EmployeeProfile.objects.filter(extension=callee, is_active=True).select_related('employer', 'user').first()

        # If tenant_user was not found from caller, try finding it via callee
        if not tenant_user and callee_emp:
            tenant_user = callee_emp.employer or callee_emp.user

        # Fallback to first admin user if still unresolved
        if not tenant_user:
            tenant_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        if not tenant_user:
            logger.error("api_internal_asterisk_cdr: No tenant user could be resolved.")
            return JsonResponse({"status": "error", "message": "No tenant user found"}, status=400)

        # Check recording file on disk
        rec_url = ""
        if uniqueid:
            local_wav_path = os.path.join(settings.MEDIA_ROOT, 'recordings', f"{uniqueid}.wav")
            if os.path.exists(local_wav_path) and os.path.getsize(local_wav_path) > 44:
                rec_url = f"/media/recordings/{uniqueid}.wav"
            elif recording and not recording.startswith('http'):
                rec_url = recording
            elif recording:
                rec_url = recording

        now = timezone.now()
        started_at = now - datetime.timedelta(seconds=total_duration) if total_duration > 0 else now

        room_name = f"ast_{uniqueid}" if uniqueid else f"ast_{caller}_{callee}_{int(now.timestamp())}"
        billed_minutes = math.ceil(duration / 60.0) if duration > 0 else 0

        caller_name = caller_emp.display_name if caller_emp else f"التحويلة {caller}"
        callee_name = callee_emp.display_name if callee_emp else f"التحويلة {callee}"

        # 1. Create or update CallSession in crm
        from crm.models import CallSession
        session, created = CallSession.objects.update_or_create(
            room_name=room_name,
            defaults={
                'user': tenant_user,
                'direction': 'internal_employee',
                'caller_phone': caller or 'Unknown',
                'destination_phone': callee or 'Unknown',
                'caller_extension': caller,
                'started_at': started_at,
                'ended_at': now,
                'duration_seconds': duration,
                'billed_minutes': billed_minutes,
                'cost': 0.0000,
                'summary': f"مكالمة هاتفية داخلية بين {caller_name} و {callee_name} ({status})",
                'transcript_text': f"مكالمة هاتفية داخلية عبر سنترال Wazo/Asterisk بين {caller_name} و {callee_name}.\nالحالة: {status} | المدة: {duration} ثانية.",
                'recording_url': rec_url,
            }
        )

        # 2. Create EmployeeCallLog for Caller
        if caller_emp:
            EmployeeCallLog.objects.create(
                employee=caller_emp,
                other_party=callee_name,
                extension=callee,
                room_name=room_name,
                call_type='outbound',
                started_at=started_at,
                ended_at=now,
                duration_secs=duration,
                recording_url=rec_url
            )
            if caller_emp.status == 'busy':
                caller_emp.status = 'ready'
                caller_emp.save(update_fields=['status'])
                publish_to_centrifugo("employees:presence", {
                    "event": "status_change",
                    "employee": caller_emp.to_dict()
                })

        # 3. Create EmployeeCallLog for Callee
        if callee_emp:
            c_type = 'inbound' if (duration > 0 or status == 'ANSWERED') else 'missed'
            EmployeeCallLog.objects.create(
                employee=callee_emp,
                other_party=caller_name,
                extension=caller,
                room_name=room_name,
                call_type=c_type,
                started_at=started_at,
                ended_at=now,
                duration_secs=duration,
                recording_url=rec_url
            )
            if callee_emp.status == 'busy':
                callee_emp.status = 'ready'
                callee_emp.save(update_fields=['status'])
                publish_to_centrifugo("employees:presence", {
                    "event": "status_change",
                    "employee": callee_emp.to_dict()
                })

        # 4. Notify tenant via Centrifugo
        publish_to_centrifugo(f"tenant_{tenant_user.id}:calls", {
            "event": "new_call_session",
            "session": session.to_dict()
        })

        logger.info(f"api_internal_asterisk_cdr logged: caller={caller}, callee={callee}, dur={duration}s, status={status}, rec={rec_url}, session_id={session.id}")

        return JsonResponse({
            "status": "success",
            "session_id": session.id,
            "room_name": room_name,
            "duration": duration,
            "recording_url": rec_url
        })

    except Exception as e:
        logger.error(f"Error in api_internal_asterisk_cdr: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
