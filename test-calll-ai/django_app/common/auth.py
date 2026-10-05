"""Centralized authentication and security verification helpers."""
import secrets
from django.conf import settings
from django.http import HttpRequest


def verify_internal_api_key(request: HttpRequest) -> bool:
    """
    Validate that an incoming request originates from the trusted AI Voice Agent service.
    
    Checks X-Internal-API-Key or Authorization Bearer header against settings.INTERNAL_API_KEY
    using constant-time comparison to protect against timing attacks.
    Only allows staff/superusers if authenticating via user session (preventing regular user privilege escalation).
    """
    expected_key = getattr(settings, 'INTERNAL_API_KEY', 'voice-internal-secret-token-key-12345')
    if not expected_key:
        return False

    auth_header = request.headers.get('X-Internal-API-Key') or request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    else:
        token = auth_header.strip()

    if token and secrets.compare_digest(token, expected_key):
        return True

    # Allow authenticated staff or superuser sessions only
    if getattr(request, 'user', None) and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return True

    return False
