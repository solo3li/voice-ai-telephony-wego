"""Session Bridge & ForwardAuth Verifier for Trinity and External SPAs."""
import logging
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from agents.models import DigitalCoworkerConfig

logger = logging.getLogger(__name__)


@csrf_exempt
def verify_session_view(request: HttpRequest) -> HttpResponse:
    """
    Traefik ForwardAuth & Frontend Session Verification Endpoint.
    
    Verifies that the incoming request carries an active, valid Django session cookie (sessionid).
    If authenticated:
      - Injects user and tenant context in HTTP response headers for Traefik to pass to Trinity.
      - Returns 200 OK with user profile JSON.
    If unauthenticated:
      - If browser navigation (HTML): redirects to /login/.
      - If API call: returns 401 Unauthorized.
    """
    if getattr(request, 'user', None) and request.user.is_authenticated:
        user = request.user
        coworker_cfg = DigitalCoworkerConfig.get_or_create_config(user)
        
        response_data = {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
            },
            "coworker_config": coworker_cfg.to_dict(),
        }
        resp = JsonResponse(response_data, status=200)
        
        # Injected ForwardAuth headers for Traefik to forward to Trinity upstream
        resp['X-Forwarded-User'] = user.username
        resp['X-User-Id'] = str(user.id)
        resp['X-User-Name'] = user.username
        resp['X-User-Email'] = user.email or f"{user.username}@local.voice"
        resp['X-Tenant-Id'] = str(user.id)
        resp['X-Service-Mode'] = coworker_cfg.service_mode
        resp['X-Coworker-Role'] = coworker_cfg.coworker_role
        resp['X-Autonomy-Level'] = coworker_cfg.autonomy_level
        return resp

    # Unauthenticated handling
    accept_header = request.headers.get('Accept', '')
    if 'text/html' in accept_header and not request.path.startswith('/api/'):
        return redirect(f"/login/?next={request.path}")

    return JsonResponse(
        {
            "authenticated": False,
            "error": "Unauthorized session. Please login to access the platform.",
            "login_url": "/login/"
        },
        status=401
    )


@csrf_exempt
def sso_token_exchange_view(request: HttpRequest) -> JsonResponse:
    """Exchange active Django session for Trinity API token payload."""
    if not (getattr(request, 'user', None) and request.user.is_authenticated):
        return JsonResponse({"error": "Authentication required"}, status=401)

    user = request.user
    coworker_cfg = DigitalCoworkerConfig.get_or_create_config(user)
    
    return JsonResponse({
        "status": "success",
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "service_mode": coworker_cfg.service_mode,
        "coworker_role": coworker_cfg.coworker_role,
        "autonomy_level": coworker_cfg.autonomy_level,
        "session_key": request.session.session_key,
    })
