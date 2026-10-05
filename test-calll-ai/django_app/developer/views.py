import os
import io
import time
import json
import logging
import secrets
import requests
import jwt
import asyncio
import csv
from urllib.parse import urlparse, unquote
from django.core.files.base import ContentFile
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse as _DjangoJsonResponse

def JsonResponse(data, *args, **kwargs):
    dumps_params = kwargs.pop('json_dumps_params', None)
    if dumps_params is None:
        dumps_params = {'ensure_ascii': False}
    else:
        dumps_params.setdefault('ensure_ascii', False)
    return _DjangoJsonResponse(data, *args, json_dumps_params=dumps_params, **kwargs)

def get_full_recording_url(request, rec_url):
    if not rec_url:
        return ""
    if rec_url.startswith("http://") or rec_url.startswith("https://"):
        return rec_url
    return request.build_absolute_uri(rec_url)

from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from livekit import api
from google import genai
from google.genai import types
from pgvector.django import CosineDistance

from rest_framework.decorators import api_view, parser_classes, authentication_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.views import SpectacularAPIView
from .models import UserApiKey
from .decorators import user_api_key_required
from .user_openapi_spec import get_user_openapi_spec
from .serializers import (
    UserAccountResponseSerializer,
    AgentProfileSerializer,
    AgentProfileCreateRequestSerializer,
    AgentProfilesListResponseSerializer,
    AgentStudioMetadataResponseSerializer,
    CustomerMemorySerializer,
    CustomerMemoryCreateRequestSerializer,
    DocumentSerializer,
    DocumentUploadRequestSerializer,
    RAGQueryRequestSerializer,
    RAGQueryResponseSerializer,
    MCPServerSerializer,
    MCPServerCreateRequestSerializer,
    SIPTrunkSerializer,
    TelephonyNumberSerializer,
    EmployeeSerializer,
    EmployeeCreateRequestSerializer,
    QueueSerializer,
    QueueCreateRequestSerializer,
    WebRTCTokenResponseSerializer,
    DialCallRequestSerializer,
    DialCallResponseSerializer,
    HangupCallRequestSerializer,
    CallSessionSerializer,
    WebhookEventSerializer,
    BaseSuccessResponseSerializer,
    BaseErrorResponseSerializer,
    CampaignSerializer,
    CampaignCreateRequestSerializer,
    CampaignDetailResponseSerializer,
    CampaignsListResponseSerializer,
    CampaignActionResponseSerializer,
)
import inngest
from asgiref.sync import async_to_sync

from agents.models import AgentProfile, UserMCPServer, SystemSetting
from agents.views import fetch_mcp_tools_sync
from agents.mcp_service import test_mcp_connection_sync, test_mcp_tool_sync
from billing.models import UserWallet, BillingConfig, BillingTransaction
from call_center.models import EmployeeProfile, EmployeeCallLog, CallQueue, QueueMembership
from crm.models import CustomerMemory, CallSession, OutboundCampaign, CampaignContact, UserCampaignLimit
from crm.inngest_jobs import inngest_client, broadcast_campaign_update
from knowledge.models import Document, DocumentChunk
from telephony.models import OutboundSIPTrunk, InboundPBXTrunk, BusinessHoursSchedule
from telephony.services import initiate_outbound_call
from django.utils import timezone
from crm.file_parser import parse_leads_file, normalize_phone, is_valid_phone
from knowledge.rag_utils import extract_text_from_file, chunk_text, get_embeddings_batch

logger = logging.getLogger(__name__)


# =========================================================================
# Web UI Dashboard Endpoints for Managing User API Keys
# =========================================================================

@login_required(login_url='/login/')
def get_developer_keys(request):
    """
    GET /api/v1/developer/keys/
    Returns active API keys for the logged-in user, generating a default one if none exists.
    """
    keys = UserApiKey.objects.filter(user=request.user, is_active=True).order_by('-created_at')
    if not keys.exists():
        default_key = UserApiKey.generate_for_user(user=request.user, name="مفتاح التطبيق الرئيسي")
        keys = [default_key]

    return JsonResponse({
        "status": "success",
        "keys": [k.to_dict() for k in keys]
    })


@login_required(login_url='/login/')
@csrf_exempt
def rotate_developer_key(request):
    """
    POST /api/v1/developer/keys/rotate/
    Deactivates existing keys and generates a fresh API key for the user.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    name = "مفتاح التطبيق (مُحدّث)"
    if request.body:
        try:
            data = json.loads(request.body.decode('utf-8'))
            name = data.get('name', name).strip() or name
        except Exception:
            pass

    # Deactivate older keys
    UserApiKey.objects.filter(user=request.user, is_active=True).update(is_active=False)

    # Generate brand new key
    new_key = UserApiKey.generate_for_user(user=request.user, name=name)

    return JsonResponse({
        "status": "success",
        "message": "تم توليد مفتاح API جديد بنجاح وإلغاء تفعيل المفاتيح السابقة.",
        "key": new_key.to_dict()
    })


# =========================================================================
# Documentation Portal Views (Scalar)
# =========================================================================

def api_user_docs(request):
    """
    GET /api/v1/docs/
    Interactive Scalar Reference for User Developer API (Burgundy & Warm Off-White Theme).
    Supports bilingual Arabic & English switching (?lang=ar | ?lang=en).
    """
    lang = request.GET.get('lang', 'ar').lower().strip()
    if lang not in ('ar', 'en'):
        lang = 'ar'

    user_api_key = ''
    if request.user.is_authenticated:
        key_obj = UserApiKey.objects.filter(user=request.user, is_active=True).first()
        if not key_obj:
            key_obj = UserApiKey.generate_for_user(user=request.user, name="مفتاح التطبيق الرئيسي")
        user_api_key = key_obj.key

    return render(request, 'developer/scalar_docs.html', {
        'user_api_key': user_api_key,
        'base_url': request.build_absolute_uri('/')[:-1],
        'current_lang': lang,
        'is_ar': (lang == 'ar'),
    })


class UserSpectacularSchemaView(SpectacularAPIView):
    """
    OpenAPI 3.1 Schema generator powered by drf-spectacular for User Developer API.
    Provides isolated schema for /api/v1/ endpoints and feeds Scalar Docs directly.
    """
    custom_settings = {
        'TITLE': 'واجهات المطورين المباشرة - User Developer API (v1)',
        'DESCRIPTION': 'واجهات برمجة التطبيقات للمطورين للتحكم في المساعد الصوتي، المكالمات الحية WebRTC، الشخصيات، واستدعاء أدوات FastMCP.',
        'VERSION': '1.0.0',
        'PREPROCESSING_HOOKS': ['developer.openapi_hooks.filter_user_endpoints'],
    }

    def get(self, request, *args, **kwargs):
        lang = request.GET.get('lang', 'ar').lower().strip()
        if lang not in ('ar', 'en'):
            lang = 'ar'

        resp = super().get(request, *args, **kwargs)
        spec = resp.data if hasattr(resp, 'data') else {}

        # 1. Normalize paths: Django's root URLconf has '/api/v1/', but the OpenAPI server base URL
        # is already '/api/v1'. Stripping '/api/v1' prevents duplicate '/api/v1/api/v1/...' in Scalar.
        cleaned_paths = {}
        for path_key, path_data in spec.get('paths', {}).items():
            clean_path = path_key
            if clean_path.startswith('/api/v1/'):
                clean_path = clean_path[7:]  # strips '/api/v1' while keeping leading '/'
            elif clean_path == '/api/v1':
                clean_path = '/'
            cleaned_paths[clean_path] = path_data
        spec['paths'] = cleaned_paths

        legacy_spec = get_user_openapi_spec(server_url='/api/v1', lang=lang)
        if not spec.get('paths'):
            spec['paths'] = legacy_spec.get('paths', {})
        else:
            for path_key, path_data in legacy_spec.get('paths', {}).items():
                if path_key not in spec['paths']:
                    spec['paths'][path_key] = path_data

        for k in ('info', 'servers'):
            if k not in spec or not spec[k]:
                spec[k] = legacy_spec.get(k, {})

        if 'components' not in spec or not spec['components']:
            spec['components'] = legacy_spec.get('components', {})
        else:
            for sub_k in ('schemas', 'securitySchemes', 'responses', 'parameters'):
                if sub_k in legacy_spec.get('components', {}):
                    spec['components'].setdefault(sub_k, {})
                    for item_k, item_v in legacy_spec['components'][sub_k].items():
                        if item_k not in spec['components'][sub_k]:
                            spec['components'][sub_k][item_k] = item_v

        # Use curated ordered tags from user_openapi_spec
        spec['tags'] = legacy_spec.get('tags', [])

        if lang == 'en':
            if 'info' in spec:
                spec['info']['title'] = 'User Developer REST API (v1)'
                spec['info']['description'] = 'Developer REST API for Voice Assistant, LiveKit WebRTC, and FastMCP tools.'
            # Translate tags on paths if English
            for p_key, p_methods in spec.get('paths', {}).items():
                for m_verb, m_data in p_methods.items():
                    if isinstance(m_data, dict) and 'tags' in m_data:
                        m_data['tags'] = [
                            "1. Account & Balance" if t == "1. الحساب والرصيد (Account & Balance)" else
                            ("10. Outbound Campaigns" if t == "10. حملات الاتصال والعملاء (Campaigns)" else t)
                            for t in m_data['tags']
                        ]

        return JsonResponse(spec, json_dumps_params={'ensure_ascii': False, 'indent': 2})


api_user_openapi_spec = UserSpectacularSchemaView.as_view()


# =========================================================================
# User RESTful Developer API Endpoints (Authenticated via X-API-Key)
# =========================================================================

@extend_schema(
    summary="بيانات الحساب والرصيد المالي",
    description="استرجاع تفاصيل الحساب، الرصيد المالي الحالي بالدولار، والشخصية المفعلة وإحصائيات النظام.",
    responses={200: UserAccountResponseSerializer},
    tags=["1. الحساب والرصيد (Account & Balance)"]
)
@api_view(['GET'])
@authentication_classes([])
@user_api_key_required
def api_user_account(request):
    """
    GET /api/v1/account/
    Returns current user profile, wallet balance, active voice persona, and account stats.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    wallet, _ = UserWallet.objects.get_or_create(user=request.user)
    active_profile = AgentProfile.objects.filter(user=request.user, is_active=True).first()

    return JsonResponse({
        "status": "success",
        "user_id": request.user.id,
        "username": request.user.username,
        "email": request.user.email,
        "wallet_balance": float(wallet.balance),
        "active_profile": active_profile.to_dict() if active_profile else None,
        "total_calls": CallSession.objects.filter(user=request.user).count(),
        "total_documents": Document.objects.filter(user=request.user).count(),
        "total_employees": EmployeeProfile.objects.filter(user=request.user).count(),
        "total_mcp_servers": UserMCPServer.objects.filter(user=request.user, is_active=True).count(),
    })


@csrf_exempt
@user_api_key_required
def api_user_profiles_studio(request):
    """
    GET /api/v1/profiles/studio/
    Returns full studio customization metadata:
    - 30 Google HD studio voices with styles and gender classifications
    - 11 Supported languages
    - 29 Regional dialects grouped hierarchically
    - Sample roles and styles for inspiration
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    from agents.views import GOOGLE_VOICES, LANGUAGE_DIALECTS_MAP
    return JsonResponse({
        "status": "success",
        "google_voices": GOOGLE_VOICES,
        "languages": [{"id": l[0], "label": l[1]} for l in AgentProfile.LANGUAGE_CHOICES],
        "language_dialects_map": LANGUAGE_DIALECTS_MAP,
        "genders": [{"id": g[0], "label": g[1]} for g in AgentProfile.GENDER_CHOICES],
        "verbosities": [
            {"id": "concise", "label": "مختصر ⚡ (ردود مباشرة في 1-2 جملة)", "description": "10-25 كلمة، رد مباشر وسريع بدون حشو أو أسئلة زائدة"},
            {"id": "balanced", "label": "متوازن ⚖️ (رد طبيعي ومهذب)", "description": "2-3 جمل طبيعية توازن بين السرعة واللطف"},
            {"id": "detailed", "label": "مفصل 📖 (شرح وافٍ واستشاري)", "description": "تفاصيل وخطوات وخيارات واقتراحات"}
        ],
        "sample_roles": [
            "ممثل خدمة عملاء محترف لمتجر الكتروني",
            "مستشار تسويق ومبيعات عقارية خبير في الفلل والأراضي",
            "مساعد شخصي ذكي وودود لحجز المواعيد وتنظيم المهام",
            "مستشار دعم فني وتقني متخصص لحل المشاكل التقنية"
        ],
        "sample_styles": [
            "ودود ولطيف ومرح، يبعث على الراحة والابتسامة في الحديث",
            "رسمي ومهني وجاد، خالٍ من المزاح المفرط، ويركز على الوقار والاحترام",
            "مباشر وسريع وموجز، يقدم الإجابة بكلمات قليلة ومفيدة دون إطالة",
            "حماسي ونشيط ومتفائل، يظهر طاقة إيجابية عالية في الرد"
        ]
    })


@csrf_exempt
@user_api_key_required
def api_user_profiles(request):
    """
    GET & POST /api/v1/profiles/
    List all voice agent profiles or create a new persona.
    """
    if request.method == 'GET':
        qs = AgentProfile.objects.filter(user=request.user).order_by('-updated_at')
        is_active_filter = request.GET.get('is_active')
        if is_active_filter is not None:
            qs = qs.filter(is_active=(is_active_filter.lower() in ('true', '1')))

        active_prof = AgentProfile.objects.filter(user=request.user, is_active=True).first()
        return JsonResponse({
            "status": "success",
            "total": qs.count(),
            "count": qs.count(),
            "active_profile": active_prof.to_dict() if active_prof else None,
            "profiles": [p.to_dict() for p in qs]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({"status": "error", "message": "name is required"}, status=400)

        profile = AgentProfile.objects.create(
            user=request.user,
            name=name,
            voice_name=data.get('voice_name', 'Aoede').strip(),
            gender=data.get('gender', 'female'),
            language=data.get('language', 'arabic').strip(),
            dialect=data.get('dialect', 'egyptian').strip(),
            persona_role=data.get('persona_role', 'خدمة عملاء ومبيعات المتجر').strip(),
            speaking_style=data.get('speaking_style', 'ودود ولطيف ومرح').strip(),
            verbosity=data.get('verbosity', 'balanced').strip(),
            custom_instructions=data.get('custom_instructions', '').strip(),
            welcome_message=data.get('welcome_message', '').strip(),
            is_welcome_message_enabled=bool(data.get('is_welcome_message_enabled', True)),
            is_active=bool(data.get('is_active', True))
        )
        return JsonResponse({
            "status": "success",
            "message": "Voice profile created successfully",
            "profile": profile.to_dict()
        }, status=201)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_profile_detail(request, profile_id):
    """
    GET, PUT, PATCH, DELETE /api/v1/profiles/<int:profile_id>/
    Manage single voice persona.
    """
    profile = get_object_or_404(AgentProfile, id=profile_id, user=request.user)

    if request.method == 'GET':
        return JsonResponse({"status": "success", "profile": profile.to_dict()})

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        for field in ['name', 'voice_name', 'gender', 'language', 'dialect', 'persona_role', 'speaking_style', 'verbosity', 'custom_instructions', 'welcome_message', 'off_topic_response']:
            if field in data:
                setattr(profile, field, str(data[field]).strip())
        if 'is_welcome_message_enabled' in data:
            profile.is_welcome_message_enabled = bool(data['is_welcome_message_enabled'])
        if 'is_active' in data:
            profile.is_active = bool(data['is_active'])

        profile.save()
        return JsonResponse({"status": "success", "message": "Profile updated successfully", "profile": profile.to_dict()})

    elif request.method == 'DELETE':
        profile.delete()
        return JsonResponse({"status": "success", "message": "Profile deleted successfully"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_profile_activate(request, profile_id):
    """
    POST /api/v1/profiles/<int:profile_id>/activate/
    Activates the target persona and deactivates all other profiles for this user.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    profile = get_object_or_404(AgentProfile, id=profile_id, user=request.user)
    AgentProfile.objects.filter(user=request.user, is_active=True).exclude(pk=profile.pk).update(is_active=False)
    profile.is_active = True
    profile.save(update_fields=['is_active'])

    return JsonResponse({
        "status": "success",
        "message": f"Profile '{profile.name}' is now the active agent persona.",
        "active_profile": profile.to_dict(),
        "profile": profile.to_dict()
    })


@csrf_exempt
@user_api_key_required
def api_user_memory(request):
    """
    GET & POST /api/v1/memory/
    List, search, and paginate customer context memories or upsert by phone.
    """
    if request.method == 'GET':
        raw_phone = request.GET.get('phone') or request.GET.get('phone_number')
        if raw_phone:
            phone = str(raw_phone).strip()
            if not phone.startswith('+') and phone.isdigit() and len(phone) >= 9:
                phone = '+' + phone

            mem = CustomerMemory.objects.filter(user=request.user, phone_number=phone).first()
            if not mem:
                alt_phone = phone[1:] if phone.startswith('+') else ('+' + phone)
                mem = CustomerMemory.objects.filter(user=request.user, phone_number=alt_phone).first()

            if not mem:
                return JsonResponse({"status": "error", "message": "Customer memory not found for this phone"}, status=404)
            return JsonResponse({
                "status": "success",
                "memory": mem.to_dict(),
                "customer": mem.to_dict()
            })

        qs = CustomerMemory.objects.filter(user=request.user).order_by('-updated_at')
        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(customer_name__icontains=q) | Q(phone_number__icontains=q))

        try:
            page_num = max(1, int(request.GET.get('page', 1)))
            limit = min(100, max(1, int(request.GET.get('limit', 20))))
        except Exception:
            page_num, limit = 1, 20

        paginator = Paginator(qs, limit)
        page_obj = paginator.get_page(page_num)

        return JsonResponse({
            "status": "success",
            "total": paginator.count,
            "page": page_num,
            "limit": limit,
            "total_pages": paginator.num_pages,
            "memories": [m.to_dict() for m in page_obj.object_list]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        phone = data.get('phone_number', '').strip()
        if not phone:
            return JsonResponse({"status": "error", "message": "phone_number is required"}, status=400)

        mem, created = CustomerMemory.objects.get_or_create(user=request.user, phone_number=phone)
        if 'customer_name' in data:
            mem.customer_name = data['customer_name']
        if 'permanent_profile' in data:
            mem.permanent_profile = data['permanent_profile']
        if 'immediate_notes' in data:
            mem.immediate_notes = data['immediate_notes']
        if 'total_calls_count' in data:
            mem.total_calls_count = int(data['total_calls_count'])

        mem.save()
        return JsonResponse({
            "status": "success",
            "message": "Memory created successfully" if created else "Memory updated successfully",
            "memory": mem.to_dict()
        }, status=201 if created else 200)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_memory_detail(request, memory_id):
    """
    GET, PUT, DELETE /api/v1/memory/<int:memory_id>/
    Manage single customer context memory record.
    """
    mem = get_object_or_404(CustomerMemory, id=memory_id, user=request.user)

    if request.method == 'GET':
        return JsonResponse({"status": "success", "memory": mem.to_dict()})

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        for field in ['customer_name', 'permanent_profile', 'immediate_notes']:
            if field in data:
                setattr(mem, field, data[field])
        if 'total_calls_count' in data:
            mem.total_calls_count = int(data['total_calls_count'])

        mem.save()
        return JsonResponse({"status": "success", "message": "Memory updated successfully", "memory": mem.to_dict()})

    elif request.method == 'DELETE':
        mem.delete()
        return JsonResponse({"status": "success", "message": "Memory deleted successfully"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@extend_schema(
    methods=['GET'],
    operation_id="list_user_documents",
    summary="استعراض قائمة المستندات المعرفية المفهرسة بالـ RAG",
    description="استعراض قائمة المستندات والمقاطع المفهرسة بالمتجهات في قاعدة المعرفة.",
    tags=["4. قواعد المعرفة والاستعلام الدلالي (RAG)"]
)
@extend_schema(
    methods=['POST'],
    operation_id="upload_user_document",
    summary="رفع مستند أو رابط وتوليد المتجهات (RAG Ingestion)",
    description="فهرسة مستند جديد عبر رفع ملف مباشر، رابط خارجي (file_url)، أو نص مباشر، وتقطيعه وتوليد Embeddings بالمتجهات عبر Gemini.",
    request=DocumentUploadRequestSerializer,
    tags=["4. قواعد المعرفة والاستعلام الدلالي (RAG)"]
)
@extend_schema(
    methods=['DELETE'],
    operation_id="delete_user_document",
    summary="حذف مستند من قاعدة المعرفة",
    description="حذف المستند وكافة المتجهات التابعة له من قاعدة المعرفة.",
    tags=["4. قواعد المعرفة والاستعلام الدلالي (RAG)"]
)
@api_view(['GET', 'POST', 'DELETE'])
@authentication_classes([])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@user_api_key_required
def api_user_documents(request):
    """
    GET, POST & DELETE /api/v1/documents/
    List indexed documents, upload new knowledge content (via file, file_url, or text), or delete a document.
    """
    if request.method == 'GET':
        docs = Document.objects.filter(user=request.user).order_by('-created_at')
        return JsonResponse({
            "status": "success",
            "count": docs.count(),
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "file_type": d.file_type or "text",
                    "file_size": d.file_size,
                    "created_at": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else None,
                    "chunks_count": d.chunks.count()
                }
                for d in docs
            ]
        })

    elif request.method == 'POST':
        try:
            data = request.data if hasattr(request, 'data') and request.data else {}
            if request.FILES:
                return JsonResponse({
                    "status": "error",
                    "code": "direct_file_upload_disabled",
                    "message": "تم إلغاء رفع الملفات الثنائية المباشرة من الـ API. يرجى تزويد رابط خارجي مباشر عبر 'file_url' أو إرسال النص مباشرة عبر 'content'."
                }, status=400)

            file_url = str(data.get('file_url') or '').strip()
            title = str(data.get('title') or '').strip()
            content = str(data.get('content') or data.get('text') or '').strip()

            if not file_url and not content:
                return JsonResponse({
                    "status": "error",
                    "code": "missing_payload",
                    "message": "يجب تزويد رابط مباشر للمستند (file_url) أو إرسال نص المحتوى مباشرة (content)."
                }, status=400)

            from agents.models import SystemSetting
            from knowledge.models import Document, DocumentChunk

            allowed_exts = ['.pdf', '.docx', '.doc', '.txt', '.md', '.csv', '.json']

            if file_url:
                try:
                    parsed_url = urlparse(file_url)
                    url_path = unquote(parsed_url.path)
                    filename = os.path.basename(url_path) or f"document_{secrets.token_hex(4)}"
                    ext = os.path.splitext(filename)[1].lower()

                    resp = requests.get(file_url, stream=True, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
                    if resp.status_code != 200:
                        return JsonResponse({
                            "status": "error",
                            "message": f"فشل تحميل الملف من الرابط (رمز الاستجابة: {resp.status_code})"
                        }, status=400)

                    content_bytes = bytearray()
                    max_bytes = 25 * 1024 * 1024
                    for chunk in resp.iter_content(chunk_size=65536):
                        content_bytes.extend(chunk)
                        if len(content_bytes) > max_bytes:
                            return JsonResponse({
                                "status": "error",
                                "message": "حجم الملف يتجاوز الحد الأقصى المسموح به (25 ميجابايت)"
                            }, status=400)

                    if not ext:
                        ct = resp.headers.get('Content-Type', '').lower()
                        if 'pdf' in ct:
                            ext = '.pdf'
                        elif 'csv' in ct:
                            ext = '.csv'
                        elif 'json' in ct:
                            ext = '.json'
                        elif 'word' in ct or 'docx' in ct:
                            ext = '.docx'
                        else:
                            ext = '.txt'
                        filename = f"{filename}{ext}"

                    if ext not in allowed_exts:
                        return JsonResponse({
                            "status": "error",
                            "code": "unsupported_file_type",
                            "message": f"صيغة الملف المسترجع '{ext}' غير مدعومة. الصيغ المدعومة هي: PDF, DOCX, TXT, MD, CSV, JSON"
                        }, status=400)

                    file_bytes_io = io.BytesIO(bytes(content_bytes))
                    title = title or filename
                    extracted_text = extract_text_from_file(file_bytes_io, filename)
                    file_size = len(content_bytes)
                    file_type = ext.lstrip('.')
                    saved_file = ContentFile(bytes(content_bytes), name=filename)
                except Exception as dl_err:
                    logger.error(f"Error downloading document from file_url {file_url}: {dl_err}", exc_info=True)
                    return JsonResponse({"status": "error", "message": f"تعذر تحميل الملف من الرابط: {str(dl_err)}"}, status=400)

            else:
                title = title or "مستند نصي معرفي"
                extracted_text = content.strip()
                file_size = len(extracted_text.encode('utf-8'))
                file_type = "txt"
                saved_file = None

            if not extracted_text:
                return JsonResponse({
                    "status": "error",
                    "code": "empty_document",
                    "message": "لم يتم العثور على أي نصوص صالحة داخل المستند أو النص المدخل."
                }, status=400)

            doc = Document.objects.create(
                user=request.user,
                title=title,
                file=saved_file,
                file_type=file_type,
                file_size=file_size,
                status='ready'
            )

            # Chunk text and generate embeddings
            chunks = chunk_text(extracted_text, chunk_size=500, overlap=50)
            if not chunks:
                return JsonResponse({"status": "error", "message": "فشل تقطيع نصوص المستند."}, status=400)

            client = genai.Client(api_key=SystemSetting.get_gemini_api_key())
            embeddings = get_embeddings_batch(client, chunks, batch_size=50)

            chunk_objs = [
                DocumentChunk(
                    document=doc,
                    user=request.user,
                    chunk_index=i,
                    content=c,
                    embedding=emb
                )
                for i, (c, emb) in enumerate(zip(chunks, embeddings))
            ]
            DocumentChunk.objects.bulk_create(chunk_objs)

            return JsonResponse({
                "status": "success",
                "message": f"تم رفع المستند '{title}' وفهرسته بالمتجهات بنجاح.",
                "document": {
                    "id": doc.id,
                    "title": doc.title,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "status": "ready",
                    "chunks_count": len(chunks),
                    "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M")
                }
            }, status=201)

        except Exception as e:
            logger.error(f"Error creating user document: {e}", exc_info=True)
            return JsonResponse({"status": "error", "message": f"حدث خطأ أثناء فهرسة المستند: {str(e)}"}, status=500)

    elif request.method == 'DELETE':
        data = request.data if hasattr(request, 'data') and request.data else {}
        doc_id = request.GET.get('document_id') or data.get('document_id')
        if not doc_id:
            return JsonResponse({"status": "error", "message": "document_id is required"}, status=400)
        doc = Document.objects.filter(id=doc_id, user=request.user).first()
        if not doc:
            return JsonResponse({"status": "error", "message": "Document not found"}, status=404)
        doc.delete()
        return JsonResponse({"status": "success", "message": "تم حذف المستند من قاعدة المعرفة بنجاح."})


@csrf_exempt
@user_api_key_required
def api_user_rag_query(request):
    """
    POST /api/v1/rag/query/
    Semantic vector search against indexed documents using pgvector and Gemini.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        query = str(data.get('query', '')).strip()
        top_k = int(data.get('top_k', 3))

        if not query:
            return JsonResponse({"status": "error", "message": "query is required"}, status=400)

        client = genai.Client(api_key=SystemSetting.get_gemini_api_key())
        embed_res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=query,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        if not embed_res or not embed_res.embeddings:
            return JsonResponse({"status": "error", "message": "Failed to generate query embedding"}, status=500)

        query_vec = embed_res.embeddings[0].values
        chunks = DocumentChunk.objects.filter(user=request.user) \
            .annotate(distance=CosineDistance('embedding', query_vec)) \
            .filter(distance__lte=0.55) \
            .order_by('distance')[:top_k]

        results = []
        for c in chunks:
            similarity = round(1.0 - float(c.distance), 4) if hasattr(c, 'distance') and c.distance is not None else 1.0
            results.append({
                "chunk_id": c.id,
                "document_id": c.document_id,
                "document_title": c.document.title if c.document else "",
                "content": c.content,
                "similarity": similarity
            })

        return JsonResponse({
            "status": "success",
            "query": query,
            "total_matches": len(results),
            "results": results
        })
    except Exception as e:
        logger.error(f"Error in user RAG query: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@user_api_key_required
def api_user_mcp(request):
    """
    GET & POST /api/v1/mcp/
    List or register FastMCP servers for the user.
    """
    if request.method == 'GET':
        servers = UserMCPServer.objects.filter(user=request.user).order_by('-updated_at')
        return JsonResponse({
            "status": "success",
            "count": servers.count(),
            "servers": [s.to_dict() for s in servers]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        name = data.get('name', 'خادم FastMCP الرئيسي').strip()
        server_url = data.get('server_url', '').strip()
        auth_token = data.get('auth_token', '').strip()

        if not server_url:
            return JsonResponse({"status": "error", "message": "server_url is required"}, status=400)

        server = UserMCPServer.objects.create(
            user=request.user,
            name=name,
            server_url=server_url,
            auth_token=auth_token,
            is_active=bool(data.get('is_active', True))
        )

        # Trigger initial handshake
        try:
            tools = fetch_mcp_tools_sync(server_url, auth_token, timeout=5.0)
            if tools:
                server.cached_tools = tools
                server.save(update_fields=['cached_tools'])
        except Exception as e:
            logger.warning(f"Initial tool sync failed for MCP {server.id}: {e}")

        return JsonResponse({
            "status": "success",
            "message": "MCP server registered successfully",
            "server": server.to_dict()
        }, status=201)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_mcp_sync(request, mcp_id):
    """
    POST /api/v1/mcp/<int:mcp_id>/sync/
    Triggers on-demand tool synchronization for the designated MCP server.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    server = get_object_or_404(UserMCPServer, id=mcp_id, user=request.user)
    try:
        tools = fetch_mcp_tools_sync(server.server_url, server.auth_token, timeout=8.0)
        server.cached_tools = tools
        server.save(update_fields=['cached_tools'])
        return JsonResponse({
            "status": "success",
            "message": f"Successfully synchronized {len(tools)} tools from MCP server.",
            "server": server.to_dict(),
            "tools_count": len(tools),
            "tools": tools
        })
    except Exception as e:
        logger.error(f"Failed to sync user MCP server {server.id}: {e}")
        return JsonResponse({"status": "error", "message": f"MCP sync failed: {str(e)}"}, status=502)


@csrf_exempt
@user_api_key_required
def api_user_mcp_detail(request, mcp_id):
    """
    GET, PATCH, DELETE /api/v1/mcp/<int:mcp_id>/
    Inspect, update, or remove an MCP server.
    """
    server = get_object_or_404(UserMCPServer, id=mcp_id, user=request.user)

    if request.method == 'GET':
        return JsonResponse({"status": "success", "server": server.to_dict()})

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        for field in ['name', 'server_url', 'auth_token']:
            if field in data:
                setattr(server, field, str(data[field]).strip())
        if 'is_active' in data:
            server.is_active = bool(data['is_active'])

        server.save()
        return JsonResponse({"status": "success", "message": "MCP server updated successfully", "server": server.to_dict()})

    elif request.method == 'DELETE':
        server.delete()
        return JsonResponse({"status": "success", "message": "MCP server deleted successfully"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_mcp_test(request):
    """
    POST /api/v1/mcp/test/
    Pre-flight or on-demand test of an MCP server connection and tool discovery.
    Accepts:
    - { "server_url": "...", "auth_token": "...", "timeout": 6.0 }
    - OR { "mcp_id": 123 }
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

    mcp_id = data.get('mcp_id') or data.get('id')
    server_url = (data.get('server_url') or '').strip()
    auth_token = (data.get('auth_token') or '').strip()
    try:
        timeout = float(data.get('timeout', 6.0))
    except (ValueError, TypeError):
        timeout = 6.0

    server = None
    if mcp_id:
        server = get_object_or_404(UserMCPServer, id=mcp_id, user=request.user)
        server_url = server_url or server.server_url
        if 'auth_token' not in data:
            auth_token = server.auth_token

    if not server_url:
        return JsonResponse({"status": "error", "message": "server_url is required"}, status=400)

    result = test_mcp_connection_sync(server_url, auth_token, timeout=timeout)
    if server and result.get("ok"):
        try:
            server.cached_tools = result.get("tools", [])
            server.last_synced_at = timezone.now()
            server.save(update_fields=['cached_tools', 'last_synced_at'])
            result["server"] = server.to_dict()
        except Exception as e:
            logger.warning(f"Failed to auto-update tools for MCP {server.id}: {e}")

    http_status = 200 if result.get("ok") else 400
    return JsonResponse(result, status=http_status)


@csrf_exempt
@user_api_key_required
def api_user_mcp_test_tool(request, mcp_id=None):
    """
    POST /api/v1/mcp/<int:mcp_id>/test-tool/
    POST /api/v1/mcp/test-tool/
    Executes a test tool call on the specified MCP server.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

    target_id = mcp_id or data.get('mcp_id') or data.get('id')
    server_url = (data.get('server_url') or '').strip()
    auth_token = (data.get('auth_token') or '').strip()
    tool_name = (data.get('tool_name') or '').strip()
    arguments = data.get('arguments', {})
    try:
        timeout = float(data.get('timeout', 8.0))
    except (ValueError, TypeError):
        timeout = 8.0

    if target_id:
        server = get_object_or_404(UserMCPServer, id=target_id, user=request.user)
        server_url = server_url or server.server_url
        if 'auth_token' not in data:
            auth_token = server.auth_token

    if not server_url:
        return JsonResponse({"status": "error", "message": "server_url is required"}, status=400)

    if not tool_name:
        return JsonResponse({"status": "error", "message": "tool_name is required"}, status=400)

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return JsonResponse({"status": "error", "message": "arguments must be valid JSON"}, status=400)

    if not isinstance(arguments, dict):
        arguments = {}

    result = test_mcp_tool_sync(server_url, auth_token, tool_name, arguments, timeout=timeout)
    http_status = 200 if result.get("ok") else 400
    return JsonResponse(result, status=http_status)


@csrf_exempt
@user_api_key_required
def api_user_telephony(request):
    """
    GET & POST /api/v1/telephony/
    List or register PBX and SIP trunks for the user.
    """
    if request.method == 'GET':
        pbx = InboundPBXTrunk.objects.filter(user=request.user)
        sip = OutboundSIPTrunk.objects.filter(user=request.user)
        return JsonResponse({
            "status": "success",
            "pbx_trunks": [t.to_dict() for t in pbx],
            "sip_trunks": [t.to_dict() for t in sip]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        trunk_type = data.get('trunk_type', 'pbx').lower()
        name = data.get('name', '').strip()
        host = data.get('host', '').strip()

        if not name or not host:
            return JsonResponse({"status": "error", "message": "name and host are required"}, status=400)

        if trunk_type == 'pbx':
            trunk = InboundPBXTrunk.objects.create(
                user=request.user,
                name=name,
                host=host,
                port=int(data.get('port', 5060)),
                username=data.get('username', '').strip(),
                secret=data.get('secret', '').strip(),
                is_active=bool(data.get('is_active', True))
            )
        else:
            trunk = OutboundSIPTrunk.objects.create(
                user=request.user,
                name=name,
                host=host,
                port=int(data.get('port', 5060)),
                username=data.get('username', '').strip(),
                password=data.get('secret', '').strip(),
                is_active=bool(data.get('is_active', True))
            )

        return JsonResponse({
            "status": "success",
            "message": f"{trunk_type.upper()} trunk registered successfully",
            "trunk": trunk.to_dict()
        }, status=201)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_numbers(request):
    """
    GET & POST /api/v1/telephony/numbers/
    List or assign phone numbers / DIDs for the user's PBX.
    """
    from call_center.models import PhoneNumber
    if request.method == 'GET':
        nums = PhoneNumber.objects.filter(user=request.user)
        return JsonResponse({
            "status": "success",
            "count": nums.count(),
            "numbers": [n.to_dict() for n in nums]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        phone_num = data.get('phone_number', '').strip()
        pbx_id = data.get('pbx_trunk_id')

        if not phone_num:
            return JsonResponse({"status": "error", "message": "phone_number is required"}, status=400)

        pbx = get_object_or_404(InboundPBXTrunk, id=pbx_id, user=request.user) if pbx_id else None
        num, created = PhoneNumber.objects.get_or_create(
            phone_number=phone_num,
            defaults={
                'user': request.user,
                'inbound_trunk': pbx,
                'description': data.get('description', '')
            }
        )
        if not created:
            num.user = request.user
            if pbx:
                num.inbound_trunk = pbx
            num.save()

        return JsonResponse({
            "status": "success",
            "message": "Phone number assigned successfully",
            "number": num.to_dict()
        }, status=201 if created else 200)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_employees(request):
    """
    GET & POST /api/v1/employees/
    List staff extensions or create an employee profile.
    """
    if request.method == 'GET':
        employees = EmployeeProfile.objects.filter(Q(employer=request.user) | Q(user=request.user)).order_by('extension')
        return JsonResponse({
            "status": "success",
            "count": employees.count(),
            "employees": [e.to_dict() for e in employees]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        name = (data.get('display_name') or data.get('name') or '').strip()
        extension = data.get('extension', '').strip()

        if not name or not extension:
            return JsonResponse({"status": "error", "message": "name and extension are required"}, status=400)

        # If an employee with this extension already exists for this employer, update and return
        emp = EmployeeProfile.objects.filter(employer=request.user, extension=extension).first()
        if emp:
            emp.display_name = name
            if 'department' in data:
                emp.department = str(data['department']).strip()
            if 'status' in data:
                emp.status = str(data['status']).strip()
            emp.save()
            return JsonResponse({
                "status": "success",
                "message": "Employee updated successfully",
                "employee": emp.to_dict()
            }, status=200)

        emp_username = f"emp_{request.user.id}_{extension}_{secrets.token_hex(3)}"
        emp_user = User.objects.create_user(
            username=emp_username,
            password=secrets.token_urlsafe(16),
            first_name=name
        )

        emp = EmployeeProfile.objects.create(
            employer=request.user,
            user=emp_user,
            display_name=name,
            extension=extension,
            department=data.get('department', 'المبيعات').strip(),
            status=data.get('status', 'ready'),
            avatar_url=f"https://api.dicebear.com/7.x/bottts/png?seed={extension}"
        )
        return JsonResponse({
            "status": "success",
            "message": "Employee created successfully",
            "employee": emp.to_dict()
        }, status=201)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_employee_detail(request, employee_id):
    """
    GET, PATCH, DELETE /api/v1/employees/<int:employee_id>/
    Manage single employee record.
    """
    emp = EmployeeProfile.objects.filter(Q(employer=request.user) | Q(user=request.user), id=employee_id).first()
    if not emp:
        return JsonResponse({"status": "error", "message": "Employee not found"}, status=404)

    if request.method == 'GET':
        return JsonResponse({"status": "success", "employee": emp.to_dict()})

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        for field in ['display_name', 'extension', 'department', 'status']:
            if field in data:
                setattr(emp, field, str(data[field]).strip())
        if 'name' in data:
            emp.display_name = str(data['name']).strip()
        emp.save()
        return JsonResponse({"status": "success", "message": "Employee updated successfully", "employee": emp.to_dict()})

    elif request.method == 'DELETE':
        emp.delete()
        return JsonResponse({"status": "success", "message": "Employee deleted successfully"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_queues(request):
    """
    GET & POST /api/v1/queues/
    List or create call center queues with strategy, timeouts, and fallback action.
    """
    if request.method == 'GET':
        queues = CallQueue.objects.filter(user=request.user).order_by('code')
        return JsonResponse({
            "status": "success",
            "count": queues.count(),
            "queues": [q.to_dict() for q in queues]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        name = data.get('name', '').strip() or 'طابور خدمة العملاء'
        code = str(data.get('code', '')).strip()
        if not code:
            existing_codes = set(CallQueue.objects.filter(user=request.user).values_list('code', flat=True))
            cand = 200
            while str(cand) in existing_codes:
                cand += 10
            code = str(cand)
        elif not code.isdigit():
            return JsonResponse({"status": "error", "message": "Queue code must be numeric (e.g. 200, 300)"}, status=400)
        elif CallQueue.objects.filter(user=request.user, code=code).exists():
            return JsonResponse({"status": "error", "message": f"Queue code '{code}' already exists for this account"}, status=400)

        description = str(data.get('description', '')).strip()
        strategy = str(data.get('strategy', 'round_robin')).strip()
        if strategy not in ('round_robin', 'ring_all'):
            strategy = 'round_robin'
        ring_timeout = int(data.get('ring_timeout_seconds', 15))
        total_timeout = int(data.get('total_timeout_seconds', 60))
        fallback_action = str(data.get('fallback_action', 'ai_assistant')).strip()
        if fallback_action not in ('ai_assistant', 'hangup'):
            fallback_action = 'ai_assistant'

        queue = CallQueue.objects.create(
            user=request.user,
            name=name,
            code=code,
            description=description,
            strategy=strategy,
            ring_timeout_seconds=ring_timeout,
            total_timeout_seconds=total_timeout,
            fallback_action=fallback_action,
            is_active=bool(data.get('is_active', True))
        )

        members = data.get('members') or data.get('member_ids')
        if isinstance(members, list):
            for idx, emp_id in enumerate(members):
                emp = EmployeeProfile.objects.filter(Q(employer=request.user) | Q(user=request.user), id=emp_id).first()
                if emp:
                    QueueMembership.objects.create(queue=queue, employee=emp, order=idx)

        return JsonResponse({
            "status": "success",
            "message": "Queue created successfully",
            "queue": queue.to_dict()
        }, status=201)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_queue_detail(request, queue_id):
    """
    GET, PUT/PATCH, & DELETE /api/v1/queues/<int:queue_id>/
    Manage single call center queue.
    """
    queue = get_object_or_404(CallQueue, id=queue_id, user=request.user)

    if request.method == 'GET':
        return JsonResponse({"status": "success", "queue": queue.to_dict()})

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        if 'name' in data:
            queue.name = str(data['name']).strip() or queue.name
        if 'code' in data:
            new_code = str(data['code']).strip()
            if new_code != queue.code:
                if not new_code.isdigit():
                    return JsonResponse({"status": "error", "message": "Queue code must be numeric"}, status=400)
                if CallQueue.objects.filter(user=request.user, code=new_code).exclude(id=queue.id).exists():
                    return JsonResponse({"status": "error", "message": f"Queue code '{new_code}' already exists"}, status=400)
                queue.code = new_code
        if 'description' in data:
            queue.description = str(data['description']).strip()
        if 'strategy' in data:
            strat = str(data['strategy']).strip()
            if strat in ('round_robin', 'ring_all'):
                queue.strategy = strat
        if 'ring_timeout_seconds' in data:
            queue.ring_timeout_seconds = int(data['ring_timeout_seconds'])
        if 'total_timeout_seconds' in data:
            queue.total_timeout_seconds = int(data['total_timeout_seconds'])
        if 'fallback_action' in data:
            fb = str(data['fallback_action']).strip()
            if fb in ('ai_assistant', 'hangup'):
                queue.fallback_action = fb
        if 'is_active' in data:
            queue.is_active = bool(data['is_active'])

        queue.save()

        members = data.get('members') or data.get('member_ids')
        if isinstance(members, list):
            queue.memberships.all().delete()
            for idx, emp_id in enumerate(members):
                emp = EmployeeProfile.objects.filter(Q(employer=request.user) | Q(user=request.user), id=emp_id).first()
                if emp:
                    QueueMembership.objects.create(queue=queue, employee=emp, order=idx)

        return JsonResponse({
            "status": "success",
            "message": "Queue updated successfully",
            "queue": queue.to_dict()
        })

    elif request.method == 'DELETE':
        queue.delete()
        return JsonResponse({"status": "success", "message": "Queue deleted successfully"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_queue_members(request, queue_id):
    """
    GET, POST, DELETE /api/v1/queues/<int:queue_id>/members/
    Manage employee memberships in a specific call queue.
    """
    queue = get_object_or_404(CallQueue, id=queue_id, user=request.user)

    if request.method == 'GET':
        members = queue.memberships.select_related('employee').all()
        return JsonResponse({
            "status": "success",
            "queue_id": queue.id,
            "queue_name": queue.name,
            "total_members": members.count(),
            "members": [m.to_dict() for m in members]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        emp_id = data.get('employee_id')
        if not emp_id:
            return JsonResponse({"status": "error", "message": "employee_id is required"}, status=400)

        emp = EmployeeProfile.objects.filter(Q(employer=request.user) | Q(user=request.user), id=emp_id).first()
        if not emp:
            return JsonResponse({"status": "error", "message": "Employee not found"}, status=404)
        order = int(data.get('order', queue.memberships.count()))

        membership, created = QueueMembership.objects.get_or_create(
            queue=queue,
            employee=emp,
            defaults={'order': order, 'is_active': True}
        )
        if not created:
            membership.is_active = True
            membership.order = order
            membership.save()

        return JsonResponse({
            "status": "success",
            "message": f"Employee '{emp.name}' added to queue '{queue.name}'",
            "member": membership.to_dict()
        }, status=201 if created else 200)

    elif request.method == 'DELETE':
        emp_id = request.GET.get('employee_id')
        if not emp_id and request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
                emp_id = data.get('employee_id')
            except Exception:
                pass

        if not emp_id:
            return JsonResponse({"status": "error", "message": "employee_id is required"}, status=400)

        membership = queue.memberships.filter(employee_id=emp_id).first()
        if not membership:
            return JsonResponse({"status": "error", "message": "Membership not found in this queue"}, status=404)

        membership.delete()
        return JsonResponse({
            "status": "success",
            "message": f"Employee removed from queue '{queue.name}'"
        })

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@api_view(['POST'])
@authentication_classes([])
@parser_classes([JSONParser, FormParser, MultiPartParser])
@user_api_key_required
def api_user_token(request):
    """
    Deprecated: POST /api/v1/token/
    WebRTC token issuing endpoint has been removed from developer API.
    To test AI calls, please use the employee app (employee_expo57) by dialing extension 000 or clicking the AI test button.
    """
    return JsonResponse({
        "status": "error",
        "code": "endpoint_removed",
        "message": "تم إزالة مسار التوكن من الـ API. لتجربة المساعد الصوتي يرجى استخدام تطبيق الموظف (employee_expo57) بالاتصال بالتحويلة 000 أو الضغط على زر تجربة المساعد الذكي."
    }, status=404)


@csrf_exempt
@user_api_key_required
def api_user_calls(request):
    """
    GET /api/v1/calls/
    Returns call logs, duration, cost, recordings, and AI conversation summaries.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    qs = CallSession.objects.filter(user=request.user).order_by('-started_at')
    
    phone = request.GET.get('phone', '').strip()
    if phone:
        qs = qs.filter(Q(caller_phone__icontains=phone) | Q(destination_phone__icontains=phone))

    direction = request.GET.get('direction', '').strip()
    if direction:
        qs = qs.filter(direction=direction)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(Q(caller_phone__icontains=search) | Q(destination_phone__icontains=search) | Q(room_name__icontains=search) | Q(call_goal__icontains=search) | Q(summary__icontains=search))

    limit = min(int(request.GET.get('limit', 50)), 200)
    offset = max(int(request.GET.get('offset', 0)), 0)
    total = qs.count()
    calls = qs[offset:offset+limit]

    calls_list = []
    for call in calls:
        calls_list.append({
            "call_id": call.room_name,
            "session_id": call.id,
            "direction": call.direction,
            "direction_display": call.get_direction_display(),
            "caller_phone": call.caller_phone or "",
            "destination_phone": call.destination_phone or "",
            "call_goal": call.call_goal or "",
            "started_at": call.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_at": call.ended_at.strftime("%Y-%m-%d %H:%M:%S") if call.ended_at else None,
            "duration_seconds": call.duration_seconds,
            "billed_minutes": call.billed_minutes,
            "cost": float(call.cost),
            "summary": call.summary or "",
            "transcript_text": call.transcript_text or "",
            "recording_url": get_full_recording_url(request, call.recording_url),
            "transferred_recording_url": get_full_recording_url(request, call.transferred_recording_url),
            "transferred_to_extension": call.transferred_to_extension or "",
            "is_transferred": bool(call.transferred_recording_url or call.transferred_to_extension),
            "caller_extension": call.caller_extension or "",
            "is_internal_test": call.is_internal_test,
            "dialogue_turns": call.dialogue_turns,
        })

    return JsonResponse({
        "status": "success",
        "total": total,
        "limit": limit,
        "offset": offset,
        "calls": calls_list
    })


@csrf_exempt
@user_api_key_required
def api_user_call_detail(request, call_id):
    """
    GET /api/v1/calls/<call_id>/
    Returns single AI call session detail with transcript, dialogue turns, summary, cost, and recording URL.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    call = CallSession.objects.filter(
        Q(room_name=call_id) | Q(id=call_id if str(call_id).isdigit() else -1),
        user=request.user
    ).first()

    if not call:
        return JsonResponse({"status": "error", "message": "Call not found"}, status=404)

    return JsonResponse({
        "status": "success",
        "call": {
            "call_id": call.room_name,
            "session_id": call.id,
            "direction": call.direction,
            "direction_display": call.get_direction_display(),
            "caller_phone": call.caller_phone or "",
            "destination_phone": call.destination_phone or "",
            "call_goal": call.call_goal or "",
            "started_at": call.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_at": call.ended_at.strftime("%Y-%m-%d %H:%M:%S") if call.ended_at else None,
            "duration_seconds": call.duration_seconds,
            "billed_minutes": call.billed_minutes,
            "cost": float(call.cost),
            "summary": call.summary or "",
            "transcript_text": call.transcript_text or "",
            "recording_url": get_full_recording_url(request, call.recording_url),
            "transferred_recording_url": get_full_recording_url(request, call.transferred_recording_url),
            "transferred_to_extension": call.transferred_to_extension or "",
            "is_transferred": bool(call.transferred_recording_url or call.transferred_to_extension),
            "caller_extension": call.caller_extension or "",
            "is_internal_test": call.is_internal_test,
            "dialogue_turns": call.dialogue_turns,
        }
    })


@csrf_exempt
@user_api_key_required
def api_user_call_hangup(request):
    """
    POST /api/v1/calls/hangup/
    Terminate an active call session immediately (hang up caller and AI/employee, clean up LiveKit room).
    Accepts:
    {
        "call_id": "room_name_or_call_session_id"
    }
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use POST."}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

    room_name = str(data.get('call_id') or data.get('room_name') or '').strip()
    if not room_name:
        return JsonResponse({"status": "error", "message": "call_id or room_name is required"}, status=400)

    from call_center.views import api_hangup_call
    return api_hangup_call(request)


@csrf_exempt
@user_api_key_required
def api_user_webhooks(request):
    """
    GET & POST /api/v1/webhooks/
    Get or set user webhook configuration.
    """
    from .models import UserWebhookEndpoint
    endpoint, _ = UserWebhookEndpoint.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return JsonResponse({
            "status": "success",
            "webhook_url": endpoint.url,
            "has_secret": bool(endpoint.secret),
            "is_active": endpoint.is_active
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        url = data.get('webhook_url', '').strip()
        endpoint.url = url
        if 'webhook_secret' in data:
            endpoint.secret = data['webhook_secret'].strip()
        if 'is_active' in data:
            endpoint.is_active = bool(data['is_active'])
        endpoint.save()

        return JsonResponse({
            "status": "success",
            "message": "Webhook configuration saved successfully",
            "webhook_url": endpoint.url,
            "has_secret": bool(endpoint.secret),
            "is_active": endpoint.is_active
        })

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_call_dial(request):
    """
    POST /api/v1/calls/dial/
    Trigger an autonomous AI outbound phone call to an external customer or internal PBX extension.
    Accepts:
    {
        "phone_number": "+201012345678",  // or PBX extension "101"
        "call_goal": "تأكيد الطلب رقم 1005",
        "profile_id": 1,                   // optional agent profile ID
        "gateway_type": "auto",            // "auto" | "pbx" | "cloud"
        "gateway_id": 2                    // optional PBX trunk ID
    }
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use POST."}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body format"}, status=400)

    phone_number = str(data.get('phone_number') or '').strip()
    if not phone_number:
        return JsonResponse({"status": "error", "message": "phone_number is required"}, status=400)

    call_goal = str(data.get('call_goal') or '').strip()
    profile_id = data.get('profile_id')
    gateway_type = str(data.get('gateway_type') or 'auto').strip()
    gateway_id = data.get('gateway_id')

    try:
        res = initiate_outbound_call(
            user=request.user,
            phone_number=phone_number,
            call_goal=call_goal,
            profile_id=profile_id,
            gateway_type=gateway_type,
            gateway_id=gateway_id,
        )
        http_status = res.pop('http_status', 201)
        return JsonResponse(res, status=http_status)
    except Exception as e:
        logger.exception(f"Error in api_user_call_dial for user {request.user.id}: {e}")
        return JsonResponse({"status": "error", "message": f"Outbound call initiation failed: {str(e)}"}, status=500)


# =========================================================================
# User RESTful Campaigns API (Inngest Powered)
# =========================================================================

@extend_schema(
    methods=['GET'],
    operation_id="list_user_campaigns",
    summary="استعراض قائمة حملات الاتصال الآلي (Campaigns)",
    description="استعراض قائمة حملات الاتصال الصادرة وإحصائيات التقدم ومؤشرات العملاء المهتمين.",
    responses={200: CampaignsListResponseSerializer},
    tags=["10. حملات الاتصال والعملاء (Campaigns)"]
)
@extend_schema(
    methods=['POST'],
    operation_id="create_user_campaign",
    summary="إنشاء حملة اتصال آلي جديدة مع جهات الاتصال",
    description="إنشاء حملة جديدة وتزويدها بقائمة جهات الاتصال والسيناريو المخصص.",
    request=CampaignCreateRequestSerializer,
    responses={201: CampaignActionResponseSerializer},
    tags=["10. حملات الاتصال والعملاء (Campaigns)"]
)
@api_view(['GET', 'POST'])
@authentication_classes([])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@user_api_key_required
def api_user_campaigns(request):
    """
    GET & POST /api/v1/campaigns/
    List all outbound campaigns or create a new campaign with target contacts (via file upload or JSON array).
    """
    if request.method == 'GET':
        qs = OutboundCampaign.objects.filter(user=request.user).order_by('-created_at')
        return JsonResponse({
            "status": "success",
            "total": qs.count(),
            "campaigns": [c.to_dict() for c in qs]
        })

    elif request.method == 'POST':
        data = request.data if hasattr(request, 'data') and request.data else {}
        if not data and request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                pass

        if request.FILES:
            return JsonResponse({
                "status": "error",
                "code": "direct_file_upload_disabled",
                "message": "تم إلغاء رفع الملفات المباشرة للحملات من الـ API. يرجى تزويد رابط خارجي مباشر لملف Excel/CSV عبر 'file_url' أو إرسال مصفوفة جهات الاتصال عبر 'contacts'."
            }, status=400)

        name = str(data.get('name') or '').strip()
        file_url = str(data.get('file_url') or '').strip()
        contacts_to_create = []

        if file_url:
            try:
                parsed_url = urlparse(file_url)
                url_path = unquote(parsed_url.path)
                url_filename = os.path.basename(url_path) or f"leads_{secrets.token_hex(4)}.csv"

                resp = requests.get(file_url, stream=True, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
                if resp.status_code != 200:
                    return JsonResponse({"status": "error", "message": f"فشل تحميل ملف الحملة من الرابط (رمز الاستجابة: {resp.status_code})"}, status=400)

                content_bytes = bytearray()
                max_bytes = 25 * 1024 * 1024
                for chunk in resp.iter_content(chunk_size=65536):
                    content_bytes.extend(chunk)
                    if len(content_bytes) > max_bytes:
                        return JsonResponse({"status": "error", "message": "حجم ملف جهات الاتصال يتجاوز الحد الأقصى المسموح به (25 ميجابايت)"}, status=400)

                parse_res = parse_leads_file(bytes(content_bytes), url_filename)
                if parse_res.get("status") != "success":
                    return JsonResponse({"status": "error", "message": parse_res.get("message", "فشل تحليل ملف جهات الاتصال من الرابط")}, status=400)
                valid_contacts = parse_res.get("valid_contacts", [])
                if not valid_contacts:
                    return JsonResponse({"status": "error", "message": "لم يتم العثور على أي أرقام هواتف صالحة داخل الملف المسترجع من الرابط."}, status=400)
                contacts_to_create = valid_contacts
                if not name:
                    name = f"حملة {url_filename} - {timezone.now().strftime('%Y/%m/%d %H:%M')}"
            except Exception as e:
                logger.error(f"Error fetching campaign file from url {file_url}: {e}", exc_info=True)
                return JsonResponse({"status": "error", "message": f"تعذر تحميل ملف الحملة من الرابط: {str(e)}"}, status=400)
        else:
            raw_contacts = data.get('contacts')
            if isinstance(raw_contacts, str):
                try:
                    raw_contacts = json.loads(raw_contacts)
                except Exception:
                    raw_contacts = []
            if isinstance(raw_contacts, list) and raw_contacts:
                for item in raw_contacts:
                    if not isinstance(item, dict):
                        continue
                    phone = normalize_phone(item.get('phone_number') or item.get('phone') or '')
                    if not is_valid_phone(phone):
                        phone = str(item.get('phone_number') or item.get('phone') or '').strip()
                    if not phone:
                        continue
                    name_val = str(item.get('name') or item.get('customer_name') or '').strip()
                    contacts_to_create.append({
                        "customer_name": name_val or f"عميل ({phone})",
                        "phone_number": phone,
                        "attributes": item.get('attributes') or {}
                    })

        if not contacts_to_create:
            return JsonResponse({
                "status": "error",
                "message": "يجب تزويد رابط مباشر لملف جهات الاتصال (file_url) بصيغة Excel/CSV، أو مصفوفة جهات الاتصال (contacts) تحتوي على أرقام هواتف صالحة."
            }, status=400)

        if not name:
            name = f"حملة جهات اتصال - {timezone.now().strftime('%Y/%m/%d %H:%M')}"

        call_prompt = str(data.get('call_prompt') or '').strip()
        profile_id = data.get('agent_profile_id')
        agent_profile = AgentProfile.objects.filter(id=profile_id, user=request.user).first() if profile_id else None

        gateway_type = str(data.get('gateway_type') or 'auto').strip()
        gateway_id = data.get('gateway_id')
        gateway_id_int = int(gateway_id) if gateway_id and str(gateway_id).isdigit() else None

        try:
            max_retries = max(0, min(5, int(data.get('max_retries', 1))))
        except (ValueError, TypeError):
            max_retries = 1

        try:
            retry_delay_minutes = max(1, min(1440, int(data.get('retry_delay_minutes', 15))))
        except (ValueError, TypeError):
            retry_delay_minutes = 15

        campaign = OutboundCampaign.objects.create(
            user=request.user,
            name=name,
            agent_profile=agent_profile,
            call_prompt=call_prompt,
            max_retries=max_retries,
            retry_delay_minutes=retry_delay_minutes,
            gateway_type=gateway_type,
            gateway_id=gateway_id_int,
            status='draft'
        )

        contact_objs = [
            CampaignContact(
                campaign=campaign,
                customer_name=c.get("customer_name") or f"عميل ({c.get('phone_number')})",
                phone_number=c.get("phone_number"),
                attributes=c.get("attributes", {}),
                call_status='pending',
                interest_level='uncontacted'
            )
            for c in contacts_to_create
        ]
        CampaignContact.objects.bulk_create(contact_objs)
        campaign.update_metrics()

        return JsonResponse({
            "status": "success",
            "message": "تم إنشاء حملة الاتصال بنجاح",
            "campaign": campaign.to_dict()
        }, status=201)


@extend_schema(
    methods=['GET'],
    operation_id="get_user_campaign_detail",
    summary="تفاصيل حملة اتصال محددة وقائمة العملاء",
    description="استرجاع بيانات الحملة التفصيلية وقائمة العملاء المستهدفين وتصنيفات الذكاء الاصطناعي.",
    responses={200: CampaignDetailResponseSerializer},
    tags=["10. حملات الاتصال والعملاء (Campaigns)"]
)
@extend_schema(
    methods=['DELETE'],
    operation_id="delete_user_campaign",
    summary="حذف حملة اتصال",
    description="حذف الحملة وكافة جهات الاتصال التابعة لها.",
    responses={200: BaseSuccessResponseSerializer},
    tags=["10. حملات الاتصال والعملاء (Campaigns)"]
)
@api_view(['GET', 'DELETE'])
@authentication_classes([])
@user_api_key_required
def api_user_campaign_detail(request, campaign_id):
    """
    GET & DELETE /api/v1/campaigns/<campaign_id>/
    """
    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)

    if request.method == 'GET':
        contacts = campaign.contacts.all().order_by('id')
        return JsonResponse({
            "status": "success",
            "campaign": campaign.to_dict(),
            "contacts": [c.to_dict() for c in contacts],
            "total_contacts_count": contacts.count()
        })

    elif request.method == 'DELETE':
        campaign.delete()
        return JsonResponse({
            "status": "success",
            "message": "تم حذف الحملة بنجاح"
        })


@extend_schema(
    operation_id="start_user_campaign",
    summary="بدء إطلاق الاتصال الآلي للحملة عبر Inngest",
    description="تفعيل الحملة وبدء محرك الاتصال الآلي المتوازي عبر Inngest بحسب الحدود المسموحة للحساب.",
    request=None,
    responses={200: CampaignActionResponseSerializer},
    tags=["10. حملات الاتصال والعملاء (Campaigns)"]
)
@api_view(['POST'])
@authentication_classes([])
@user_api_key_required
def api_user_campaign_start(request, campaign_id):
    """
    POST /api/v1/campaigns/<campaign_id>/start/
    """
    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    has_gw = OutboundSIPTrunk.objects.filter(user=campaign.user, is_active=True).exists()
    if not has_gw and not getattr(settings, 'DEBUG', False):
        return JsonResponse({
            "status": "error",
            "code": "no_outbound_gateway",
            "message": "لا يمكن بدء الحملة: لا يوجد خط اتصال صادر (SIP Trunk) مفعل في حسابك."
        }, status=422)

    limit = UserCampaignLimit.get_limit_for_user(request.user)
    campaign.status = 'running'
    campaign.save(update_fields=['status', 'updated_at'])

    pending_contacts = list(campaign.contacts.filter(call_status='pending').values_list('id', flat=True))
    if pending_contacts:
        try:
            events = [
                inngest.Event(
                    name="campaign/contact.dial",
                    data={
                        "campaign_id": campaign.id,
                        "contact_id": cid,
                        "user_id": campaign.user_id,
                        "concurrency_limit": limit
                    }
                )
                for cid in pending_contacts
            ]
            async_to_sync(inngest_client.send)(events)
        except Exception as e:
            logger.warning(f"Inngest dispatch notice for campaign {campaign.id}: {e}")

        broadcast_campaign_update(campaign.id, "campaign_started", {
            "queued": len(pending_contacts),
            "concurrency_limit": limit
        })

    return JsonResponse({
        "status": "success",
        "message": "تم بدء تشغيل الحملة والاتصال الآلي بنجاح",
        "campaign": campaign.to_dict()
    })


@extend_schema(
    operation_id="pause_user_campaign",
    summary="إيقاف الحملة مؤقتاً",
    description="إيقاف الاتصال الآلي للحملة مؤقتاً مع الحفاظ على تقدم المكالمات السابقة.",
    request=None,
    responses={200: CampaignActionResponseSerializer},
    tags=["10. حملات الاتصال والعملاء (Campaigns)"]
)
@api_view(['POST'])
@authentication_classes([])
@user_api_key_required
def api_user_campaign_pause(request, campaign_id):
    """
    POST /api/v1/campaigns/<campaign_id>/pause/
    """
    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    campaign.status = 'paused'
    campaign.save(update_fields=['status', 'updated_at'])
    broadcast_campaign_update(campaign.id, "campaign_paused", {})

    return JsonResponse({
        "status": "success",
        "message": "تم إيقاف الحملة مؤقتاً بنجاح",
        "campaign": campaign.to_dict()
    })


@api_view(['GET', 'POST', 'PUT', 'PATCH'])
@authentication_classes([])
@user_api_key_required
def api_user_business_hours(request):
    """
    GET, POST, PUT, PATCH /api/v1/business-hours/
    Retrieve or update business hours schedule and off-hours behavior.
    API strictly accepts file_url or ai_message (no binary uploads).
    """
    from telephony.models import BusinessHoursSchedule
    sched, _ = BusinessHoursSchedule.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return JsonResponse({
            "status": "success",
            "schedule": sched.to_dict(request)
        })

    # Reject binary multipart uploads
    if request.FILES:
        return JsonResponse({
            "status": "error",
            "message": "Binary file uploads are disabled in developer API. Please provide 'file_url' or 'audio_file_url' instead."
        }, status=400)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

    if 'is_enabled' in data:
        sched.is_enabled = bool(data['is_enabled'])

    if 'timezone' in data and str(data['timezone']).strip():
        sched.timezone = str(data['timezone']).strip()

    if 'days_config' in data and isinstance(data['days_config'], dict):
        sched.days_config = data['days_config']

    if 'action_type' in data and data['action_type'] in ('ai_message', 'audio_file'):
        sched.action_type = data['action_type']

    if 'ai_message' in data:
        sched.ai_message = str(data['ai_message']).strip()

    # Accept file_url or audio_file_url
    audio_url = data.get('audio_file_url') or data.get('file_url')
    if audio_url is not None:
        sched.audio_file_url = str(audio_url).strip()

    sched.save()

    return JsonResponse({
        "status": "success",
        "message": "Business hours schedule updated successfully",
        "schedule": sched.to_dict(request)
    })


# =========================================================================
# Billing & Wallet Admin CRUD APIs
# =========================================================================

@csrf_exempt
@user_api_key_required
def api_user_billing_wallet(request):
    """
    GET /api/v1/billing/wallet/
    Returns current user wallet balance, currency, deposit/spend totals, and per-minute rates.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use GET."}, status=405)

    config = BillingConfig.get_config()
    wallet, _ = UserWallet.objects.get_or_create(
        user=request.user,
        defaults={
            "balance": config.initial_welcome_credit,
            "currency": config.currency,
            "total_deposited": config.initial_welcome_credit,
            "total_spent": 0,
        }
    )

    return JsonResponse({
        "status": "success",
        "wallet": wallet.to_dict(),
        "rates": {
            "cost_per_minute": float(config.cost_per_minute),
            "currency": config.currency,
            "currency_symbol": config.get_currency_symbol(),
            "rounding_mode": config.rounding_mode,
            "min_balance_to_call": float(config.min_balance_to_call)
        }
    })


@csrf_exempt
@user_api_key_required
def api_user_billing_transactions(request):
    """
    GET /api/v1/billing/transactions/
    Paginated financial ledger documenting credit deductions, top-ups, and adjustments.
    Filters: type, limit, offset.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use GET."}, status=405)

    qs = BillingTransaction.objects.filter(wallet__user=request.user).order_by('-created_at')

    tx_type = request.GET.get('type', '').strip()
    if tx_type:
        qs = qs.filter(transaction_type=tx_type)

    limit = min(int(request.GET.get('limit', 50)), 200)
    offset = max(int(request.GET.get('offset', 0)), 0)
    total = qs.count()
    txs = qs[offset:offset+limit]

    return JsonResponse({
        "status": "success",
        "total": total,
        "limit": limit,
        "offset": offset,
        "transactions": [tx.to_dict() for tx in txs]
    })


# =========================================================================
# CRM Customers CRUD APIs
# =========================================================================

@csrf_exempt
@user_api_key_required
def api_user_crm_customers(request):
    """
    GET & POST /api/v1/crm/customers/
    GET: Search and list CRM customer memories and permanent profiles.
    POST: Create or update customer record / permanent profile / notes.
    """
    if request.method == 'GET':
        query = (request.GET.get('search') or request.GET.get('q') or '').strip()
        qs = CustomerMemory.objects.filter(user=request.user).order_by('-updated_at')

        if query:
            qs = qs.filter(
                Q(phone_number__icontains=query) |
                Q(customer_name__icontains=query) |
                Q(last_interaction_summary__icontains=query)
            )

        limit = min(int(request.GET.get('limit', 50)), 200)
        offset = max(int(request.GET.get('offset', 0)), 0)
        total = qs.count()
        customers = qs[offset:offset+limit]

        return JsonResponse({
            "status": "success",
            "total": total,
            "limit": limit,
            "offset": offset,
            "customers": [c.to_dict() for c in customers]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        phone_number = str(data.get('phone_number') or data.get('phone') or '').strip()
        if not phone_number:
            return JsonResponse({"status": "error", "message": "phone_number is required"}, status=400)

        memory, created = CustomerMemory.objects.get_or_create(user=request.user, phone_number=phone_number)
        if 'customer_name' in data:
            memory.customer_name = str(data['customer_name']).strip()
        if 'permanent_profile' in data and isinstance(data['permanent_profile'], dict):
            memory.permanent_profile = data['permanent_profile']
        if 'last_interaction_summary' in data:
            memory.last_interaction_summary = str(data['last_interaction_summary']).strip()
        if 'notes' in data:
            prof = memory.permanent_profile or {}
            prof['notes'] = str(data['notes']).strip()
            memory.permanent_profile = prof

        memory.save()
        return JsonResponse({
            "status": "success",
            "message": "Customer memory saved successfully",
            "customer": memory.to_dict()
        }, status=201 if created else 200)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_crm_customer_delete(request, phone):
    """
    GET, PUT, PATCH, DELETE /api/v1/crm/customers/<phone>/
    GET: Single customer memory card with recent call history.
    PUT/PATCH: Update customer profile, name, and notes.
    DELETE: Delete customer memory record.
    """
    phone = str(phone).strip()
    memory = CustomerMemory.objects.filter(user=request.user, phone_number=phone).first()

    if request.method == 'GET':
        if not memory:
            return JsonResponse({"status": "error", "message": f"Customer with phone '{phone}' not found"}, status=404)

        recent_calls = CallSession.objects.filter(
            Q(caller_phone=phone) | Q(destination_phone=phone),
            user=request.user
        ).order_by('-started_at')[:10]

        return JsonResponse({
            "status": "success",
            "customer": memory.to_dict(),
            "recent_calls": [
                {
                    "call_id": c.room_name,
                    "direction": c.direction,
                    "direction_display": c.get_direction_display(),
                    "started_at": c.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": c.duration_seconds,
                    "billed_minutes": c.billed_minutes,
                    "cost": float(c.cost),
                    "summary": c.summary or "",
                    "recording_url": get_full_recording_url(request, c.recording_url),
                    "transferred_recording_url": get_full_recording_url(request, c.transferred_recording_url),
                    "transferred_to_extension": c.transferred_to_extension or "",
                    "is_transferred": bool(c.transferred_recording_url or c.transferred_to_extension),
                }
                for c in recent_calls
            ]
        })

    elif request.method in ('PUT', 'PATCH'):
        if not memory:
            return JsonResponse({"status": "error", "message": f"Customer with phone '{phone}' not found"}, status=404)
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        if 'customer_name' in data:
            memory.customer_name = str(data['customer_name']).strip()
        if 'permanent_profile' in data and isinstance(data['permanent_profile'], dict):
            memory.permanent_profile = data['permanent_profile']
        if 'last_interaction_summary' in data:
            memory.last_interaction_summary = str(data['last_interaction_summary']).strip()
        if 'notes' in data:
            prof = memory.permanent_profile or {}
            prof['notes'] = str(data['notes']).strip()
            memory.permanent_profile = prof

        memory.save()
        return JsonResponse({
            "status": "success",
            "message": "Customer memory updated successfully",
            "customer": memory.to_dict()
        })

    elif request.method == 'DELETE':
        if not memory:
            return JsonResponse({"status": "error", "message": f"Customer with phone '{phone}' not found"}, status=404)
        memory.delete()
        return JsonResponse({
            "status": "success",
            "message": f"Customer memory for '{phone}' deleted successfully"
        })

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


# =========================================================================
# Employee Call Logs Admin API
# =========================================================================

@csrf_exempt
@user_api_key_required
def api_user_employee_calls(request):
    """
    GET /api/v1/employees/calls/
    Returns call logs for all employees managed by the authenticated account owner.
    Supports filters: employee_id, extension, call_type, search, limit, offset.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use GET."}, status=405)

    qs = EmployeeCallLog.objects.filter(employee__employer=request.user).select_related('employee').order_by('-started_at')

    employee_id = request.GET.get('employee_id')
    if employee_id and str(employee_id).isdigit():
        qs = qs.filter(employee_id=int(employee_id))

    extension = request.GET.get('extension', '').strip()
    if extension:
        qs = qs.filter(Q(extension=extension) | Q(employee__extension=extension))

    call_type = request.GET.get('call_type', '').strip()
    if call_type and call_type != 'all':
        qs = qs.filter(call_type=call_type)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(other_party__icontains=search) |
            Q(employee__display_name__icontains=search) |
            Q(room_name__icontains=search)
        )

    limit = min(int(request.GET.get('limit', 50)), 200)
    offset = max(int(request.GET.get('offset', 0)), 0)
    total = qs.count()
    logs = qs[offset:offset+limit]

    logs_list = []
    for log in logs:
        logs_list.append({
            "id": log.id,
            "employee_id": log.employee_id,
            "employee_name": log.employee.display_name if log.employee else "",
            "employee_extension": log.employee.extension if log.employee else "",
            "other_party": log.other_party,
            "extension": log.extension,
            "room_name": log.room_name,
            "call_type": log.call_type,
            "call_type_display": log.get_call_type_display(),
            "started_at": log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else "",
            "ended_at": log.ended_at.strftime("%Y-%m-%d %H:%M:%S") if log.ended_at else None,
            "duration_secs": log.duration_secs,
            "recording_url": get_full_recording_url(request, log.recording_url),
        })

    return JsonResponse({
        "status": "success",
        "total": total,
        "limit": limit,
        "offset": offset,
        "calls": logs_list
    })


# =========================================================================
# Telephony Inbound & PBX Trunks Admin CRUD APIs
# =========================================================================

@csrf_exempt
@user_api_key_required
def api_user_pbx_trunks(request):
    """
    GET & POST /api/v1/telephony/pbx-trunks/
    GET: List all Inbound/Bidirectional PBX Trunks (Issabel / Asterisk) with generated Issabel config.
    POST: Create a new PBX Trunk and provision inbound/outbound SIP trunks in LiveKit.
    """
    from telephony.views import _async_create_pbx_inbound_trunk_and_rule
    host_domain = getattr(settings, 'SIP_PUBLIC_DOMAIN', request.get_host().split(':')[0])

    if request.method == 'GET':
        trunks = InboundPBXTrunk.objects.filter(user=request.user).select_related('target_queue', 'target_profile')
        return JsonResponse({
            "status": "success",
            "total": trunks.count(),
            "host_domain": host_domain,
            "sip_port": 5060,
            "trunks": [t.to_dict(host_domain=host_domain) for t in trunks]
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        name = str(data.get('name') or 'سنترال الشركة (Issabel PBX)').strip()
        auth_mode = str(data.get('auth_mode') or 'ip').strip()
        pbx_ip = str(data.get('pbx_ip') or '').strip()
        auth_username = str(data.get('auth_username') or '').strip()
        auth_password = str(data.get('auth_password') or '').strip()
        inbound_numbers = str(data.get('inbound_numbers') or '').strip()
        destination_type = str(data.get('destination_type') or 'ai_assistant').strip()
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
            return JsonResponse({"status": "error", "message": "auth_mode must be 'ip' or 'credentials'"}, status=400)

        if auth_mode == 'ip' and not pbx_ip:
            return JsonResponse({"status": "error", "message": "pbx_ip is required for IP authentication"}, status=400)

        if auth_mode == 'credentials' and not auth_username:
            return JsonResponse({"status": "error", "message": "auth_username is required for credentials authentication"}, status=400)

        target_queue = None
        if destination_type == 'call_queue':
            if not target_queue_id:
                return JsonResponse({"status": "error", "message": "target_queue_id is required when destination_type is call_queue"}, status=400)
            target_queue = CallQueue.objects.filter(id=target_queue_id, user=request.user).first()
            if not target_queue:
                return JsonResponse({"status": "error", "message": "Target queue not found"}, status=404)

        target_profile = None
        if target_profile_id:
            target_profile = AgentProfile.objects.filter(id=target_profile_id, user=request.user).first()

        if is_default_outbound:
            InboundPBXTrunk.objects.filter(user=request.user).update(is_default_outbound=False)

        if auth_mode == 'credentials' and not auth_password:
            auth_password = secrets.token_hex(6)

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

        # Provision in LiveKit SIP
        try:
            target_queue_code = target_queue.code if target_queue else None
            lk_trunk_id, lk_rule_id, lk_out_id = asyncio.run(_async_create_pbx_inbound_trunk_and_rule(
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
                enable_outbound=trunk.enable_outbound,
                outbound_port=trunk.outbound_port,
                outbound_transport=trunk.outbound_transport
            ))
            trunk.livekit_trunk_id = lk_trunk_id
            trunk.livekit_rule_id = lk_rule_id
            trunk.livekit_outbound_trunk_id = lk_out_id
            trunk.save(update_fields=['livekit_trunk_id', 'livekit_rule_id', 'livekit_outbound_trunk_id'])
        except Exception as lk_err:
            logger.warning(f"Could not provision LiveKit SIP trunk for PBX {trunk.id}: {lk_err}")

        return JsonResponse({
            "status": "success",
            "message": "PBX Trunk created and configured successfully",
            "trunk": trunk.to_dict(host_domain=host_domain)
        }, status=201)

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_pbx_trunk_detail(request, trunk_id):
    """
    GET, PUT, PATCH, DELETE /api/v1/telephony/pbx-trunks/<trunk_id>/
    GET: Retrieve single PBX Trunk with full Issabel configuration.
    PUT/PATCH: Update PBX Trunk and re-sync with LiveKit.
    DELETE: Delete PBX Trunk and release LiveKit SIP resources.
    """
    from telephony.views import _async_create_pbx_inbound_trunk_and_rule, _async_delete_pbx_trunk_and_rule
    trunk = get_object_or_404(InboundPBXTrunk, id=trunk_id, user=request.user)
    host_domain = getattr(settings, 'SIP_PUBLIC_DOMAIN', request.get_host().split(':')[0])

    if request.method == 'GET':
        return JsonResponse({
            "status": "success",
            "trunk": trunk.to_dict(host_domain=host_domain)
        })

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        if 'name' in data:
            trunk.name = str(data['name']).strip()
        if 'auth_mode' in data and data['auth_mode'] in ['ip', 'credentials']:
            trunk.auth_mode = data['auth_mode']
        if 'pbx_ip' in data:
            trunk.pbx_ip = str(data['pbx_ip']).strip()
        if 'auth_username' in data:
            trunk.auth_username = str(data['auth_username']).strip()
        if 'auth_password' in data and str(data['auth_password']).strip():
            trunk.set_auth_password(str(data['auth_password']).strip())
        if 'inbound_numbers' in data:
            trunk.inbound_numbers = str(data['inbound_numbers']).strip()
        if 'destination_type' in data:
            dtype = str(data['destination_type']).strip()
            if dtype in ('ai', 'ai_assistant'):
                trunk.destination_type = 'ai_assistant'
            elif dtype in ('queue', 'call_queue'):
                trunk.destination_type = 'call_queue'
        if 'target_queue_id' in data:
            tq_id = data['target_queue_id']
            trunk.target_queue = CallQueue.objects.filter(id=tq_id, user=request.user).first() if tq_id else None
        if 'target_profile_id' in data:
            tp_id = data['target_profile_id']
            trunk.target_profile = AgentProfile.objects.filter(id=tp_id, user=request.user).first() if tp_id else None
        if 'enable_outbound' in data:
            trunk.enable_outbound = bool(data['enable_outbound'])
        if 'outbound_port' in data:
            trunk.outbound_port = int(data['outbound_port'] or 5060)
        if 'outbound_transport' in data:
            trunk.outbound_transport = str(data['outbound_transport']).strip().upper()
        if 'is_default_outbound' in data:
            is_def = bool(data['is_default_outbound'])
            if is_def:
                InboundPBXTrunk.objects.filter(user=request.user).update(is_default_outbound=False)
            trunk.is_default_outbound = is_def
        if 'is_active' in data:
            trunk.is_active = bool(data['is_active'])

        trunk.save()

        # Re-provision in LiveKit
        try:
            target_queue_code = trunk.target_queue.code if trunk.target_queue else None
            lk_trunk_id, lk_rule_id, lk_out_id = asyncio.run(_async_create_pbx_inbound_trunk_and_rule(
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
            trunk.livekit_trunk_id = lk_trunk_id
            trunk.livekit_rule_id = lk_rule_id
            trunk.livekit_outbound_trunk_id = lk_out_id
            trunk.save(update_fields=['livekit_trunk_id', 'livekit_rule_id', 'livekit_outbound_trunk_id'])
        except Exception as lk_err:
            logger.warning(f"Could not re-provision LiveKit SIP trunk for PBX {trunk.id}: {lk_err}")

        return JsonResponse({
            "status": "success",
            "message": "PBX Trunk updated successfully",
            "trunk": trunk.to_dict(host_domain=host_domain)
        })

    elif request.method == 'DELETE':
        try:
            asyncio.run(_async_delete_pbx_trunk_and_rule(
                trunk.livekit_trunk_id,
                trunk.livekit_rule_id,
                trunk.livekit_outbound_trunk_id
            ))
        except Exception as lk_err:
            logger.warning(f"Error releasing LiveKit SIP resources for PBX {trunk.id}: {lk_err}")

        trunk.delete()
        return JsonResponse({
            "status": "success",
            "message": "PBX Trunk deleted successfully"
        })

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


# =========================================================================
# Campaign Action & Contact Admin APIs
# =========================================================================

@csrf_exempt
@user_api_key_required
def api_user_campaign_reset(request, campaign_id):
    """
    POST /api/v1/campaigns/<campaign_id>/reset/
    Resets failed, busy, or unreached contacts in a campaign back to 'pending',
    zeroes retries, and returns the campaign status to 'draft'.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use POST."}, status=405)

    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    campaign.status = 'draft'
    campaign.save(update_fields=['status', 'updated_at'])

    updated_count = campaign.contacts.filter(
        call_status__in=['failed', 'busy', 'no_answer', 'in_progress']
    ).update(
        call_status='pending',
        interest_level='uncontacted',
        retries_count=0,
        call_summary='',
        extracted_data={}
    )
    campaign.update_metrics()

    return JsonResponse({
        "status": "success",
        "message": f"Successfully reset {updated_count} contacts back to pending",
        "reset_count": updated_count,
        "campaign": campaign.to_dict()
    })


@csrf_exempt
@user_api_key_required
def api_user_campaign_export(request, campaign_id):
    """
    GET /api/v1/campaigns/<campaign_id>/export/?format=json|csv|xlsx&filter=all|hot|hot_warm|answered
    Export campaign contacts and AI classification results.
    Default format is 'json'.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use GET."}, status=405)

    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    filter_mode = request.GET.get('filter', 'all').strip().lower()
    export_format = request.GET.get('format', 'json').strip().lower()

    contacts_qs = campaign.contacts.all()
    if filter_mode == 'hot':
        contacts_qs = contacts_qs.filter(interest_level='hot')
    elif filter_mode == 'hot_warm':
        contacts_qs = contacts_qs.filter(interest_level__in=['hot', 'warm'])
    elif filter_mode == 'answered':
        contacts_qs = contacts_qs.filter(call_status='answered')

    if export_format == 'json':
        return JsonResponse({
            "status": "success",
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "filter": filter_mode,
            "total_contacts": contacts_qs.count(),
            "contacts": [c.to_dict() for c in contacts_qs]
        })

    elif export_format == 'csv':
        timestamp_str = timezone.now().strftime('%Y%m%d_%H%M')
        filename = f"campaign_{campaign.id}_{filter_mode}_{timestamp_str}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')
        writer = csv.writer(response)

        headers = [
            "اسم العميل", "رقم الهاتف", "حالة الاتصال", "تصنيف الاهتمام",
            "ملخص المكالمة", "مدة المكالمة (ثواني)", "عدد المحاولات", "تاريخ آخر اتصال"
        ]
        writer.writerow(headers)
        for c in contacts_qs:
            writer.writerow([
                c.customer_name,
                c.phone_number,
                c.get_call_status_display(),
                c.get_interest_level_display(),
                c.call_summary,
                c.duration_seconds,
                c.retries_count,
                c.last_attempt_at.strftime('%Y-%m-%d %H:%M') if c.last_attempt_at else ""
            ])
        return response

    elif export_format == 'xlsx':
        from crm.campaign_views import api_export_campaign_contacts
        return api_export_campaign_contacts(request, campaign_id)

    return JsonResponse({"status": "error", "message": "Invalid format. Supported: json, csv, xlsx"}, status=400)


@csrf_exempt
@user_api_key_required
def api_user_campaign_contact_detail(request, campaign_id, contact_id):
    """
    GET, PUT, PATCH, DELETE /api/v1/campaigns/<campaign_id>/contacts/<contact_id>/
    GET: Retrieve contact detail with call status and AI extracted data.
    PUT/PATCH: Update contact details (name, phone, attributes, interest_level, call_status).
    DELETE: Remove contact from campaign and update metrics.
    """
    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    contact = get_object_or_404(CampaignContact, id=contact_id, campaign=campaign)

    if request.method == 'GET':
        return JsonResponse({
            "status": "success",
            "contact": contact.to_dict()
        })

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

        if 'customer_name' in data:
            contact.customer_name = str(data['customer_name']).strip()
        if 'phone_number' in data:
            contact.phone_number = str(data['phone_number']).strip()
        if 'attributes' in data and isinstance(data['attributes'], dict):
            contact.attributes = data['attributes']
        if 'call_status' in data:
            contact.call_status = str(data['call_status']).strip()
        if 'interest_level' in data:
            contact.interest_level = str(data['interest_level']).strip()
        if 'call_summary' in data:
            contact.call_summary = str(data['call_summary']).strip()

        contact.save()
        campaign.update_metrics()
        return JsonResponse({
            "status": "success",
            "message": "Contact updated successfully",
            "contact": contact.to_dict()
        })

    elif request.method == 'DELETE':
        contact.delete()
        campaign.update_metrics()
        return JsonResponse({
            "status": "success",
            "message": "Contact deleted successfully"
        })

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@user_api_key_required
def api_user_campaign_contact_dial(request, campaign_id, contact_id):
    """
    POST /api/v1/campaigns/<campaign_id>/contacts/<contact_id>/dial/
    Trigger an immediate outbound call to a single specific contact in the campaign.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed. Use POST."}, status=405)

    from crm.campaign_views import api_dial_single_contact
    return api_dial_single_contact(request, contact_id)


@csrf_exempt
@user_api_key_required
def api_user_live_context(request):
    """
    GET, PUT, POST, DELETE /api/v1/context/
    Structured Live Context API for real-time restaurant/business data (menus, branches, delivery zones, out of stock).
    - GET: Retrieve current structured context and Redis cache status.
    - PUT/POST: Atomically overwrite and save structured context into PostgreSQL and Redis.
    - DELETE: Atomically clear structured context.
    """
    from agents.live_context_service import (
        get_user_live_context_cached,
        set_user_live_context,
        delete_user_live_context,
        get_redis_client,
        REDIS_KEY_TEMPLATE
    )
    from agents.models import TenantLiveContext

    if request.method == 'GET':
        ctx_obj = TenantLiveContext.objects.filter(user=request.user).first()
        r = get_redis_client()
        redis_key = REDIS_KEY_TEMPLATE.format(user_id=request.user.id)
        cached_in_redis = bool(r and r.exists(redis_key))
        return JsonResponse({
            "status": "success",
            "user_id": request.user.id,
            "context": ctx_obj.to_dict() if ctx_obj else {"data": {}, "size_bytes": 0, "updated_at": None},
            "cached_in_redis": cached_in_redis
        })

    elif request.method in ('PUT', 'POST'):
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
            context_data = body.get('data') if ('data' in body and isinstance(body['data'], dict)) else body
            if not isinstance(context_data, dict):
                return JsonResponse({
                    "status": "error",
                    "message": "Payload must be a JSON object containing your structured data."
                }, status=400)

            result = set_user_live_context(request.user.id, context_data)
            return JsonResponse({
                "status": "success",
                "message": "Structured live context updated and synced to in-memory Redis successfully.",
                "context": result
            })
        except ValueError as ve:
            return JsonResponse({"status": "error", "message": str(ve)}, status=400)
        except Exception as e:
            logger.error(f"Error in api_user_live_context: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    elif request.method == 'DELETE':
        delete_user_live_context(request.user.id)
        return JsonResponse({
            "status": "success",
            "message": "Structured live context deleted successfully from database and Redis."
        })

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)




