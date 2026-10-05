import json
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from .models import UserApiKey

def user_api_key_required(view_func):
    """
    Decorator ensuring request is authenticated with a valid, active User API Key.
    Reads X-API-Key header or Bearer token.
    Attaches request.user and request.api_key_obj.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.method == 'OPTIONS':
            return view_func(request, *args, **kwargs)

        api_key = request.headers.get('X-API-Key')
        if not api_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                api_key = auth_header.split(' ', 1)[1].strip()

        if not api_key:
            return JsonResponse({
                "status": "error",
                "message": "Missing user API key (X-API-Key header or Bearer token required)"
            }, status=401)

        key_obj = UserApiKey.objects.filter(key=api_key, is_active=True).select_related('user').first()
        if not key_obj:
            return JsonResponse({
                "status": "error",
                "message": "Invalid or inactive API key"
            }, status=403)

        # Update last used timestamp
        UserApiKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())

        request.user = key_obj.user
        request.api_key_obj = key_obj
        return view_func(request, *args, **kwargs)
    return _wrapped
