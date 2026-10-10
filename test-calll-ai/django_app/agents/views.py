import re
import json
import asyncio
import logging
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone

from .models import AgentProfile, UserMCPServer, SystemSetting, TenantLiveContext

logger = logging.getLogger(__name__)

GOOGLE_VOICES = [
    # Female Voices (15)
    {"name": "Aoede", "gender": "female", "style": "Brisk & Breezy (نشيطة وسريعة)", "tag": "افتراضي"},
    {"name": "Kore", "gender": "female", "style": "Firm & Confident (واثقة وحازمة)", "tag": "رسمي"},
    {"name": "Leda", "gender": "female", "style": "Youthful & Friendly (شابة وودودة)", "tag": "ودود"},
    {"name": "Callisto", "gender": "female", "style": "Warm & Comforting (دافئة ومريحة)", "tag": "دافئ"},
    {"name": "Sulafat", "gender": "female", "style": "Gentle & Clear (رقيقة وواضحة)", "tag": "رقيق"},
    {"name": "Autonoe", "gender": "female", "style": "Bright & Enthusiastic (مشرقة ومتحمسة)", "tag": "حيوي"},
    {"name": "Achernar", "gender": "female", "style": "Soft & Calming (ناعمة ومطمئنة)", "tag": "هادئ"},
    {"name": "Erinome", "gender": "female", "style": "Resonant & Authoritative (رنانة ومتمكنة)", "tag": "رسمي"},
    {"name": "Laomedeia", "gender": "female", "style": "Expressive & Engaging (تعبيرية وتفاعلية)", "tag": "تفاعلي"},
    {"name": "Gacrux", "gender": "female", "style": "Welcoming & Hospitable (مرحبة ومضيافة)", "tag": "مضياف"},
    {"name": "Vindemiatrix", "gender": "female", "style": "Sophisticated & Polished (أنيقة وراقية)", "tag": "فاخر"},
    {"name": "Despina", "gender": "female", "style": "Clear & Direct (واضحة ومباشرة)", "tag": "مباشر"},
    {"name": "Galatea", "gender": "female", "style": "Melodic & Elegant (نقية وأنيقة)", "tag": "أنيق"},
    {"name": "Larissa", "gender": "female", "style": "Pleasant & Friendly (مبهجة ولطيفة)", "tag": "لطيف"},
    {"name": "Naiad", "gender": "female", "style": "Smooth & Natural (سلسة وعفوية)", "tag": "طبيعي"},

    # Male Voices (15)
    {"name": "Puck", "gender": "male", "style": "Cheerful & Upbeat (مرح وحيوي)", "tag": "حيوي"},
    {"name": "Charon", "gender": "male", "style": "Calm & Informative (هادئ ووقور)", "tag": "هادئ"},
    {"name": "Fenrir", "gender": "male", "style": "Deep & Authoritative (عميق وجهوري)", "tag": "رسمي"},
    {"name": "Zephyr", "gender": "male", "style": "Bright & Crisp (منعش ومشرق)", "tag": "منعش"},
    {"name": "Orus", "gender": "male", "style": "Firm & Direct (حازم ومباشر)", "tag": "حازم"},
    {"name": "Umbriel", "gender": "male", "style": "Easy-going & Casual (تلقائي وعفوي)", "tag": "تلقائي"},
    {"name": "Schedar", "gender": "male", "style": "Clear & Articulate (واضح ورصين)", "tag": "رصين"},
    {"name": "Achird", "gender": "male", "style": "Crisp & Practical (عملي وسريع)", "tag": "عملي"},
    {"name": "Sadachbia", "gender": "male", "style": "Lively & Engaging (متفاعل وحيوي)", "tag": "حيوي"},
    {"name": "Zubenelgenubi", "gender": "male", "style": "Casual & Grounded (واقعي وبسيط)", "tag": "واقعي"},
    {"name": "Thalassa", "gender": "male", "style": "Reassuring & Steady (مطمئن ومتزن)", "tag": "مطمئن"},
    {"name": "Proteus", "gender": "male", "style": "Dynamic & Confident (ديناميكي ومتمكن)", "tag": "متمكن"},
    {"name": "Neso", "gender": "male", "style": "Youthful & Tech-savvy (شاب وتقني)", "tag": "تقني"},
    {"name": "Halimede", "gender": "male", "style": "Smooth & Polite (مهذب وسلس)", "tag": "مهذب"},
    {"name": "Sao", "gender": "male", "style": "Direct & Concise (مختصر وموجز)", "tag": "موجز"},
]

LANGUAGE_DIALECTS_MAP = {
    'arabic': [
        {'id': 'egyptian', 'label': 'لهجة مصرية عامية (مصر)'},
        {'id': 'saudi', 'label': 'لهجة سعودية / نجدية وحجازية (السعودية)'},
        {'id': 'emirati', 'label': 'لهجة إماراتية / خليجية (الإمارات)'},
        {'id': 'kuwaiti', 'label': 'لهجة كويتية (الكويت)'},
        {'id': 'levantine', 'label': 'لهجة شامية (سوريا ولبنان)'},
        {'id': 'jordanian_palestinian', 'label': 'لهجة أردنية وفلسطينية (الأردن وفلسطين)'},
        {'id': 'moroccan', 'label': 'لهجة مغربية / دارجة (المغرب)'},
        {'id': 'algerian', 'label': 'لهجة جزائرية (الجزائر)'},
        {'id': 'tunisian', 'label': 'لهجة تونسية (تونس)'},
        {'id': 'iraqi', 'label': 'لهجة عراقية (العراق)'},
        {'id': 'sudanese', 'label': 'لهجة سودانية (السودان)'},
        {'id': 'yemeni', 'label': 'لهجة يمنية (اليمن)'},
        {'id': 'fusha', 'label': 'عربية فصحى معاصرة (رسمية)'},
    ],
    'english': [
        {'id': 'english_us', 'label': 'American English (US)'},
        {'id': 'english_uk', 'label': 'British English (UK)'},
        {'id': 'english_aus', 'label': 'Australian English (Australia)'},
        {'id': 'english_ind', 'label': 'Indian English (India)'},
        {'id': 'english', 'label': 'General English'},
    ],
    'french': [
        {'id': 'french_fr', 'label': 'Français Métropolitain (France)'},
        {'id': 'french_ca', 'label': 'Français Canadien (Canada)'},
    ],
    'spanish': [
        {'id': 'spanish_es', 'label': 'Español de España (Spain)'},
        {'id': 'spanish_latam', 'label': 'Español Latinoamericano'},
    ],
    'german': [
        {'id': 'german_de', 'label': 'Standarddeutsch (Germany & Austria)'},
    ],
    'italian': [
        {'id': 'italian_it', 'label': 'Italiano Standard (Italy)'},
    ],
    'turkish': [
        {'id': 'turkish_tr', 'label': 'Türkçe (Turkey)'},
    ],
    'russian': [
        {'id': 'russian_ru', 'label': 'Русский язык (Russia)'},
    ],
    'urdu': [
        {'id': 'urdu_pk', 'label': 'اردو (Pakistan & India)'},
    ],
    'hindi': [
        {'id': 'hindi_in', 'label': 'हिन्दी (India)'},
    ],
    'chinese': [
        {'id': 'chinese_zh', 'label': '普通话 (Mandarin Chinese)'},
    ],
}
from common.auth import verify_internal_api_key

# ==================== Agent Profiles Management ====================

@login_required(login_url='/login/')
def list_profiles(request):
    """List all agent profiles for user, active profile, and options metadata."""
    profiles = list(AgentProfile.objects.filter(user=request.user))
    if not profiles:
        default_prof = AgentProfile.objects.create(
            user=request.user,
            name="نورهان - خدمة عملاء مصرية",
            voice_name="Aoede",
            gender="female",
            language="arabic",
            dialect="egyptian",
            persona_role="customer_support",
            speaking_style="friendly",
            is_active=True
        )
        profiles = [default_prof]

    active_p = next((p for p in profiles if p.is_active), profiles[0])

    return JsonResponse({
        "status": "success",
        "profiles": [p.to_dict() for p in profiles],
        "active_profile": active_p.to_dict(),
        "google_voices": GOOGLE_VOICES,
        "languages": [{"id": l[0], "label": l[1]} for l in AgentProfile.LANGUAGE_CHOICES],
        "language_dialects_map": LANGUAGE_DIALECTS_MAP,
        "dialects": [{"id": d[0], "label": d[1]} for d in AgentProfile.DIALECT_CHOICES],
        "roles": [{"id": r[0], "label": r[1]} for r in AgentProfile.ROLE_CHOICES],
        "styles": [{"id": s[0], "label": s[1]} for s in AgentProfile.STYLE_CHOICES],
        "genders": [{"id": g[0], "label": g[1]} for g in AgentProfile.GENDER_CHOICES],
        "verbosities": [{"id": v[0], "label": v[1]} for v in AgentProfile.VERBOSITY_CHOICES],
    })

@login_required(login_url='/login/')
def create_profile(request):
    """Create a new agent persona profile for user."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        name = data.get('name', '').strip() or 'بروفايل مخصص'
        voice_name = data.get('voice_name', 'Aoede').strip()
        gender = data.get('gender', 'female')
        language = data.get('language', '').strip() or 'arabic'
        dialect = data.get('dialect', 'egyptian')
        persona_role = str(data.get('persona_role', 'خدمة عملاء ومبيعات المتجر')).strip()
        speaking_style = str(data.get('speaking_style', 'ودود ولطيف ومرح')).strip()
        verbosity = str(data.get('verbosity', 'balanced')).strip() or 'balanced'
        custom_instructions = data.get('custom_instructions', '').strip()
        welcome_message = str(data.get('welcome_message', '')).strip()
        is_welcome_message_enabled = bool(data.get('is_welcome_message_enabled', True))
        off_topic_response = str(data.get('off_topic_response', '')).strip()
        is_active = bool(data.get('is_active', True))

        profile = AgentProfile.objects.create(
            user=request.user,
            name=name,
            voice_name=voice_name,
            gender=gender,
            language=language,
            dialect=dialect,
            persona_role=persona_role,
            speaking_style=speaking_style,
            verbosity=verbosity,
            custom_instructions=custom_instructions,
            welcome_message=welcome_message,
            is_welcome_message_enabled=is_welcome_message_enabled,
            off_topic_response=off_topic_response,
            is_active=is_active
        )
        return JsonResponse({
            "status": "success",
            "message": f"تم حفظ البروفايل '{profile.name}' بنجاح.",
            "profile": profile.to_dict()
        }, status=201)
    except Exception as e:
        logger.error(f"Error creating agent profile: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required(login_url='/login/')
def update_profile(request, profile_id):
    """Update an existing agent persona profile."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    profile = get_object_or_404(AgentProfile, id=profile_id, user=request.user)
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        if 'name' in data and data['name'].strip():
            profile.name = data['name'].strip()
        if 'voice_name' in data and data['voice_name'].strip():
            profile.voice_name = data['voice_name'].strip()
        if 'gender' in data:
            profile.gender = data['gender']
        if 'language' in data and data['language'].strip():
            profile.language = data['language'].strip()
        if 'dialect' in data:
            profile.dialect = data['dialect']
        if 'persona_role' in data:
            profile.persona_role = str(data['persona_role']).strip()
        if 'speaking_style' in data:
            profile.speaking_style = str(data['speaking_style']).strip()
        if 'verbosity' in data and str(data['verbosity']).strip():
            profile.verbosity = str(data['verbosity']).strip()
        if 'custom_instructions' in data:
            profile.custom_instructions = data['custom_instructions'].strip()
        if 'welcome_message' in data:
            profile.welcome_message = str(data['welcome_message']).strip()
        if 'is_welcome_message_enabled' in data:
            profile.is_welcome_message_enabled = bool(data['is_welcome_message_enabled'])
        if 'off_topic_response' in data:
            profile.off_topic_response = str(data['off_topic_response']).strip()
        if 'is_active' in data:
            profile.is_active = bool(data['is_active'])

        profile.save()
        return JsonResponse({
            "status": "success",
            "message": f"تم تحديث البروفايل '{profile.name}' بنجاح.",
            "profile": profile.to_dict()
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required(login_url='/login/')
def activate_profile(request, profile_id):
    """Set a specific profile as the active one for future calls."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    profile = get_object_or_404(AgentProfile, id=profile_id, user=request.user)
    profile.is_active = True
    profile.save()
    return JsonResponse({
        "status": "success",
        "message": f"تم تفعيل البروفايل '{profile.name}' للمكالمات القادمة.",
        "profile": profile.to_dict()
    })

@login_required(login_url='/login/')
def delete_profile(request, profile_id):
    """Delete an agent persona profile."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    profile = get_object_or_404(AgentProfile, id=profile_id, user=request.user)
    was_active = profile.is_active
    name = profile.name
    profile.delete()

    if was_active:
        fallback = AgentProfile.objects.filter(user=request.user).first()
        if fallback:
            fallback.is_active = True
            fallback.save()

    return JsonResponse({"status": "success", "message": f"تم حذف البروفايل '{name}' بنجاح."})

# ==================== User Custom Actions ====================

from .mcp_service import (
    test_mcp_connection_sync,
    test_mcp_tool_sync,
    test_mcp_connection_async,
    test_mcp_tool_async
)

def fetch_mcp_tools_sync(url: str, auth_token: str = "", timeout: float = 6.0):
    """Fetch tool list from an external MCP SSE server synchronously with timeout."""
    res = test_mcp_connection_sync(url, auth_token, timeout=timeout)
    if not res.get("ok"):
        raise RuntimeError(res.get("error_message") or "Failed to connect to MCP server")
    return res.get("tools", [])

@login_required(login_url='/login/')
def get_mcp_server(request):
    """Get the current user's MCP servers list and aggregated statistics."""
    servers = list(UserMCPServer.objects.filter(user=request.user).order_by('-created_at'))
    if not servers:
        # Create default store MCP server if none exists
        default_server = UserMCPServer.objects.create(
            user=request.user,
            name="خادم المتجر الرئيسي (FastMCP)",
            server_url="http://mock-store:8002/sse",
            is_active=True
        )
        try:
            tools = fetch_mcp_tools_sync(default_server.server_url, default_server.auth_token)
            default_server.cached_tools = tools
            default_server.last_synced_at = timezone.now()
            default_server.save()
        except Exception as e:
            logger.warning(f"Initial MCP sync failed: {e}")
        servers = [default_server]

    server_list = [s.to_dict() for s in servers]
    active_count = sum(1 for s in servers if s.is_active)
    total_tools = sum(len(s.cached_tools or []) for s in servers if s.is_active)

    return JsonResponse({
        "status": "success",
        "servers": server_list,
        "server": server_list[0] if server_list else None,
        "total_servers": len(servers),
        "active_servers": active_count,
        "total_tools": total_tools
    })

@login_required(login_url='/login/')
def save_mcp_server(request):
    """Create or update an MCP server configuration and trigger an automatic handshake sync."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        server_id = data.get('id') or data.get('server_id')
        name = data.get('name', '').strip() or 'خادم FastMCP'
        server_url = data.get('server_url', '').strip()
        auth_token = data.get('auth_token', '').strip()
        is_active = bool(data.get('is_active', True))

        if not server_url:
            return JsonResponse({"status": "error", "message": "رابط الخادم مطلوب."}, status=400)

        if server_id:
            server = get_object_or_404(UserMCPServer, id=server_id, user=request.user)
            server.name = name
            server.server_url = server_url
            server.auth_token = auth_token
            server.is_active = is_active
        else:
            server = UserMCPServer.objects.create(
                user=request.user,
                name=name,
                server_url=server_url,
                auth_token=auth_token,
                is_active=is_active
            )

        try:
            tools = fetch_mcp_tools_sync(server_url, auth_token, timeout=5.0)
            server.cached_tools = tools
            server.last_synced_at = timezone.now()
            sync_msg = f"تم الاتصال واكتشاف {len(tools)} أداة بنجاح."
        except Exception as sync_err:
            sync_msg = f"تم حفظ الرابط، ولكن تعذر الاتصال بالخادم: {sync_err}"

        server.save()
        return JsonResponse({
            "status": "success",
            "message": f"تم حفظ إعدادات MCP بنجاح. {sync_msg}",
            "server": server.to_dict()
        })
    except Exception as e:
        logger.error(f"Error saving MCP server: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required(login_url='/login/')
def sync_mcp_server(request):
    """Trigger an on-demand re-sync of MCP tools from remote server(s)."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if (request.body and request.content_type == 'application/json') else request.POST
    except Exception:
        data = {}

    server_id = data.get('id') or data.get('server_id') or request.GET.get('id')
    if server_id:
        server = get_object_or_404(UserMCPServer, id=server_id, user=request.user)
        try:
            tools = fetch_mcp_tools_sync(server.server_url, server.auth_token, timeout=8.0)
            server.cached_tools = tools
            server.last_synced_at = timezone.now()
            server.save()
            return JsonResponse({
                "status": "success",
                "message": f"تم تحديث أدوات '{server.name}' بنجاح. تم اكتشاف {len(tools)} أداة.",
                "server": server.to_dict()
            })
        except Exception as e:
            logger.error(f"Failed to sync MCP tools from {server.server_url}: {e}")
            return JsonResponse({
                "status": "error",
                "message": f"فشل الاتصال بخادم '{server.name}': {str(e)}"
            }, status=502)
    else:
        # Sync all active servers for user
        servers = UserMCPServer.objects.filter(user=request.user)
        if not servers.exists():
            return JsonResponse({"status": "error", "message": "لا يوجد خادم MCP مسجل."}, status=404)
        total_discovered = 0
        errors = []
        for s in servers:
            try:
                tools = fetch_mcp_tools_sync(s.server_url, s.auth_token, timeout=6.0)
                s.cached_tools = tools
                s.last_synced_at = timezone.now()
                s.save()
                total_discovered += len(tools)
            except Exception as e:
                errors.append(f"{s.name}: {e}")
        
        msg = f"تم تحديث الأدوات بنجاح. إجمالي الأدوات المكتشفة: {total_discovered} أداة."
        if errors:
            msg += f" (تعذر الاتصال بـ: {', '.join(errors)})"
        return JsonResponse({
            "status": "success",
            "message": msg,
            "servers": [s.to_dict() for s in UserMCPServer.objects.filter(user=request.user)]
        })

@login_required(login_url='/login/')
def toggle_mcp_server(request):
    """Toggle whether a specific MCP server is enabled for voice calls."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if (request.body and request.content_type == 'application/json') else request.POST
    except Exception:
        data = {}

    server_id = data.get('id') or data.get('server_id') or request.GET.get('id')
    if server_id:
        server = get_object_or_404(UserMCPServer, id=server_id, user=request.user)
    else:
        server = UserMCPServer.objects.filter(user=request.user).first()

    if not server:
        return JsonResponse({"status": "error", "message": "لا يوجد خادم مسجل."}, status=404)

    server.is_active = not server.is_active
    server.save()
    status_str = "تفعيل" if server.is_active else "تعطيل"
    return JsonResponse({
        "status": "success",
        "message": f"تم {status_str} خادم '{server.name}' بنجاح.",
        "is_active": server.is_active,
        "server": server.to_dict()
    })

@login_required(login_url='/login/')
def delete_mcp_server(request):
    """Delete a specific MCP server configuration."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if (request.body and request.content_type == 'application/json') else request.POST
    except Exception:
        data = {}

    server_id = data.get('id') or data.get('server_id') or request.GET.get('id')
    if server_id:
        server = get_object_or_404(UserMCPServer, id=server_id, user=request.user)
        server_name = server.name
        server.delete()
        return JsonResponse({"status": "success", "message": f"تم حذف خادم '{server_name}' بنجاح."})
    else:
        server = UserMCPServer.objects.filter(user=request.user).first()
        if server:
            server_name = server.name
            server.delete()
            return JsonResponse({"status": "success", "message": f"تم حذف خادم '{server_name}' بنجاح."})
        return JsonResponse({"status": "error", "message": "لا يوجد خادم لحذفه."}, status=404)

@login_required(login_url='/login/')
def test_mcp_connection_view(request):
    """
    Test connection to an MCP SSE server.
    Accepts:
    1. { "server_url": "...", "auth_token": "..." } (for pre-flight test before save)
    2. { "id": 123 } (for testing existing server)
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if (request.body and request.content_type == 'application/json') else request.POST
    except Exception:
        data = {}

    server_id = data.get('id') or data.get('server_id')
    server_url = (data.get('server_url') or '').strip()
    auth_token = (data.get('auth_token') or '').strip()
    try:
        timeout = float(data.get('timeout', 6.0))
    except (ValueError, TypeError):
        timeout = 6.0

    server_obj = None
    if server_id:
        if request.user.is_staff:
            server_obj = get_object_or_404(UserMCPServer, id=server_id)
        else:
            server_obj = get_object_or_404(UserMCPServer, id=server_id, user=request.user)
        server_url = server_url or server_obj.server_url
        if 'auth_token' not in data:
            auth_token = server_obj.auth_token

    if not server_url:
        return JsonResponse({"status": "error", "message": "رابط الخادم (server_url) مطلوب."}, status=400)

    result = test_mcp_connection_sync(server_url, auth_token, timeout=timeout)

    # If this was an existing saved server and connection succeeded, auto-sync cached_tools
    if server_obj and result.get("ok"):
        try:
            # Preserve existing test_results for tools that still exist
            existing_tests = {}
            if isinstance(server_obj.cached_tools, list):
                for old_t in server_obj.cached_tools:
                    if isinstance(old_t, dict) and old_t.get("name") and old_t.get("test_result"):
                        existing_tests[old_t["name"]] = old_t["test_result"]

            new_tools = result.get("tools", [])
            for nt in new_tools:
                if nt.get("name") in existing_tests:
                    nt["test_result"] = existing_tests[nt["name"]]

            server_obj.cached_tools = new_tools
            server_obj.last_synced_at = timezone.now()
            server_obj.save(update_fields=['cached_tools', 'last_synced_at'])
            result["tools"] = new_tools
            result["server"] = server_obj.to_dict()
        except Exception as e:
            logger.warning(f"Failed to auto-update cached_tools on server {server_obj.id}: {e}")

    http_status = 200 if result.get("ok") else 400
    return JsonResponse(result, status=http_status)


@login_required(login_url='/login/')
def test_mcp_tool_view(request):
    """
    Execute a test call on a specific MCP tool with custom arguments.
    Accepts:
    - server_url & auth_token OR id
    - tool_name: str
    - arguments: dict or JSON string
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if (request.body and request.content_type == 'application/json') else request.POST
    except Exception:
        data = {}

    server_id = data.get('id') or data.get('server_id')
    server_url = (data.get('server_url') or '').strip()
    auth_token = (data.get('auth_token') or '').strip()
    tool_name = (data.get('tool_name') or '').strip()
    arguments = data.get('arguments', {})
    try:
        timeout = float(data.get('timeout', 8.0))
    except (ValueError, TypeError):
        timeout = 8.0

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return JsonResponse({"status": "error", "message": "صيغة المعاملات (arguments) غير صحيحة، يجب أن تكون JSON صالح."}, status=400)

    if not isinstance(arguments, dict):
        arguments = {}

    server_obj = None
    if server_id:
        if request.user.is_staff:
            server_obj = get_object_or_404(UserMCPServer, id=server_id)
        else:
            server_obj = get_object_or_404(UserMCPServer, id=server_id, user=request.user)
        server_url = server_url or server_obj.server_url
        if 'auth_token' not in data:
            auth_token = server_obj.auth_token

    if not server_url:
        return JsonResponse({"status": "error", "message": "رابط الخادم (server_url) مطلوب."}, status=400)

    if not tool_name:
        return JsonResponse({"status": "error", "message": "اسم الأداة (tool_name) مطلوب لتنفيذ الاختبار."}, status=400)

    result = test_mcp_tool_sync(server_url, auth_token, tool_name, arguments, timeout=timeout)

    # Persist test_result in cached_tools if server exists
    if server_obj and isinstance(server_obj.cached_tools, list):
        try:
            test_info = {
                "status": "success" if result.get("ok") else "error",
                "execution_time_ms": result.get("execution_time_ms", 0),
                "tested_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
                "error_type": result.get("error_type", "none"),
                "error_message": result.get("error_message", "")
            }
            updated = False
            for t_item in server_obj.cached_tools:
                if isinstance(t_item, dict) and t_item.get("name") == tool_name:
                    t_item["test_result"] = test_info
                    updated = True
                    break
            if updated:
                server_obj.save(update_fields=['cached_tools'])
                result["test_result"] = test_info
        except Exception as e:
            logger.warning(f"Failed to persist tool test result on server {server_obj.id}: {e}")

    http_status = 200 if result.get("ok") else 400
    return JsonResponse(result, status=http_status)

# ==================== Internal AI Agent Bootstrap API ====================

@csrf_exempt
def api_internal_agent_bootstrap(request):
    """
    Consolidated internal bootstrap API for AI Voice Agent session.
    Fetches active profile, custom HTTP actions, MCP servers, and customer memory in a single fast call.
    Accepts: { user_id: int }
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not verify_internal_api_key(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        user_id = data.get('user_id')
        wazo_ctx = data.get('wazo_context') or data.get('context')
        caller_ext = data.get('caller_extension') or data.get('extension')
        room_name = data.get('room_name')

        is_internal_test = False
        if room_name:
            try:
                import redis
                r = redis.Redis.from_url(settings.REDIS_URL)
                is_internal_test = bool(r.get(f"is_internal_test:{room_name}"))
                if not caller_ext:
                    c_ext = r.get(f"caller_ext:{room_name}")
                    if c_ext:
                        caller_ext = c_ext.decode() if isinstance(c_ext, bytes) else str(c_ext)
            except Exception:
                pass

        if not user_id and (wazo_ctx or caller_ext):
            from telephony.models import resolve_tenant_from_context_and_ext
            tenant_u, emp_prof, ext_prof = resolve_tenant_from_context_and_ext(wazo_ctx, caller_ext)
            if tenant_u:
                user_id = tenant_u.id
                is_internal_test = True

        if not user_id:
            return JsonResponse({"status": "error", "message": "user_id is required"}, status=400)
        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({"status": "error", "message": f"User #{user_id} not found"}, status=404)

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
        except Exception:
            pass

        # 3. Customer Memory (Lazy import to avoid circular dependency)
        from crm.models import CustomerMemory
        caller_phone = str(data.get('caller_phone') or 'web_dashboard').strip()
        memory = CustomerMemory.objects.filter(user=user, phone_number=caller_phone).first()
        if not memory and caller_phone != 'web_dashboard' and len(caller_phone) >= 7:
            memory = CustomerMemory.objects.filter(user=user, phone_number__endswith=caller_phone[-8:]).first()
        memory_data = memory.to_dict() if memory else {
            "phone_number": caller_phone,
            "customer_name": "",
            "permanent_profile": {},
            "last_interaction_summary": "",
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
        from agents.live_context_service import get_user_live_context_cached, format_live_context_for_prompt
        live_ctx_data = get_user_live_context_cached(user.id)

        # 6. Knowledge Documents Manifest (titles of indexed documents)
        knowledge_manifest = []
        try:
            from knowledge.models import Document
            docs = Document.objects.filter(user=user, status='ready').values('id', 'title')[:15]
            knowledge_manifest = [{"id": d["id"], "title": d["title"]} for d in docs]
        except Exception as k_err:
            logger.warning(f"Error loading knowledge manifest for user {user.id}: {k_err}")

        return JsonResponse({
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
            "caller_extension": caller_ext or ""
        })

    except Exception as e:
        logger.error(f"Error in api_internal_agent_bootstrap: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@csrf_exempt
def api_user_live_context_web(request):
    """Internal Web endpoint for managing user's structured live context from dashboard UI."""
    from agents.live_context_service import (
        get_user_live_context_cached,
        set_user_live_context,
        delete_user_live_context,
        get_redis_client,
        REDIS_KEY_TEMPLATE
    )
    user = request.user

    if request.method == 'GET':
        ctx_obj = TenantLiveContext.objects.filter(user=user).first()
        r = get_redis_client()
        redis_key = REDIS_KEY_TEMPLATE.format(user_id=user.id)
        cached_in_redis = bool(r and r.exists(redis_key))
        return JsonResponse({
            "status": "success",
            "context": ctx_obj.to_dict() if ctx_obj else {"data": {}, "size_bytes": 0, "updated_at": None},
            "cached_in_redis": cached_in_redis
        })

    elif request.method in ('POST', 'PUT'):
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
            # Allow { data: {...} } or direct {...}
            context_data = body.get('data') if ('data' in body and isinstance(body['data'], dict)) else body
            if not isinstance(context_data, dict):
                return JsonResponse({"status": "error", "message": "يجب أن تكون البيانات كائن JSON صالح (Object/Dictionary)"}, status=400)

            result = set_user_live_context(user.id, context_data)
            return JsonResponse({
                "status": "success",
                "message": "تم حفظ واستبدال الذاكرة المنظمة الحية وتحديث كاش الـ Redis بنجاح",
                "context": result
            })
        except ValueError as ve:
            return JsonResponse({"status": "error", "message": str(ve)}, status=400)
        except Exception as e:
            logger.error(f"Error updating live context for user #{user.id}: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    elif request.method == 'DELETE':
        delete_user_live_context(user.id)
        return JsonResponse({
            "status": "success",
            "message": "تم مسح الذاكرة المنظمة الحية من قاعدة البيانات وكاش الـ Redis بنجاح"
        })

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@login_required
@csrf_exempt
def api_user_live_context_preview_web(request):
    """Generate compiled prompt preview for how the AI agent reads the structured context."""
    from agents.live_context_service import format_live_context_for_prompt, get_user_live_context_cached
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
        context_data = body.get('data') if ('data' in body and isinstance(body['data'], dict)) else body
        if not context_data:
            context_data = get_user_live_context_cached(request.user.id)

        compiled_prompt = format_live_context_for_prompt(context_data or {})
        return JsonResponse({
            "status": "success",
            "preview": compiled_prompt or "لا توجد بيانات منظمة مدخلة حالياً لتوليد التوجيهات."
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
