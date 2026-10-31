# SPDX-License-Identifier: Apache-2.0
"""
API Token & Embed Session Authentication Middleware.
Binds tenant user to request.user if valid developer API key (UserApiKey)
or Partner API key (PartnerProfile) is supplied in query string,
Authorization header, X-API-Key / X-Partner-Key headers, or session.
Guarantees API endpoints never return HTML login redirects.
"""
from django.utils import timezone
from django.http import JsonResponse


class ApiTokenAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            token = request.GET.get('token') or request.GET.get('key')
            if not token:
                auth = request.headers.get('Authorization', '')
                if auth.startswith('Bearer '):
                    token = auth.split(' ', 1)[1].strip()
                elif request.headers.get('X-API-Key'):
                    token = request.headers.get('X-API-Key').strip()
                elif request.headers.get('X-Partner-Key'):
                    token = request.headers.get('X-Partner-Key').strip()
                elif hasattr(request, 'session') and request.session.get('embed_token'):
                    token = request.session.get('embed_token')

            if token:
                try:
                    from developer.models import UserApiKey
                    from partners.models import PartnerProfile, PartnerClientRelationship

                    key_obj = UserApiKey.objects.filter(key=token, is_active=True).select_related('user').first()
                    if key_obj:
                        request.user = key_obj.user
                        request.user.backend = 'django.contrib.auth.backends.ModelBackend'
                        request.api_key_obj = key_obj
                        UserApiKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())
                        if hasattr(request, 'session'):
                            request.session['_auth_user_id'] = str(key_obj.user.pk)
                            request.session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
                            request.session['embed_token'] = token
                    else:
                        partner = PartnerProfile.objects.filter(api_key=token).select_related('user').first()
                        if partner and partner.status == 'approved':
                            client_id = request.GET.get('client_id') or request.headers.get('X-Client-ID')
                            if not client_id and hasattr(request, 'session'):
                                client_id = request.session.get('embed_client_id')

                            if client_id:
                                rel = PartnerClientRelationship.objects.filter(partner=partner, client_id=client_id).select_related('client').first()
                                if rel and rel.is_active and rel.client.is_active:
                                    request.user = rel.client
                                    request.user.backend = 'django.contrib.auth.backends.ModelBackend'
                                    request.partner_client_rel = rel
                                    if hasattr(request, 'session'):
                                        request.session['_auth_user_id'] = str(rel.client.pk)
                                        request.session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
                                        request.session['embed_token'] = token
                                        request.session['embed_client_id'] = str(client_id)

                            if not getattr(request, 'user', None) or not request.user.is_authenticated:
                                if not client_id:
                                    request.user = partner.user
                                    request.user.backend = 'django.contrib.auth.backends.ModelBackend'
                                    if hasattr(request, 'session'):
                                        request.session['_auth_user_id'] = str(partner.user.pk)
                                        request.session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
                                        request.session['embed_token'] = token
                except Exception:
                    pass

        response = self.get_response(request)

        # Guarantee: Never return HTML login redirect for API endpoints
        if request.path.startswith('/api/') and response.status_code == 302:
            location = response.get('Location', '')
            if '/login/' in location or '/accounts/login/' in location:
                api_resp = JsonResponse({
                    "status": "error",
                    "code": "unauthorized",
                    "message": "Authentication required. Provide a valid Bearer token, ?token= parameter, or active session."
                }, status=401)
                api_resp['Content-Security-Policy'] = "frame-ancestors *"
                api_resp['X-Frame-Options'] = "ALLOWALL"
                return api_resp

        return response
