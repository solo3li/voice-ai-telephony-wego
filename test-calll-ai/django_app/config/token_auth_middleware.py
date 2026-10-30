# SPDX-License-Identifier: Apache-2.0
"""
API Token & Embed Session Authentication Middleware.
Binds tenant user to request.user if valid developer API key (UserApiKey)
or Partner API key (PartnerProfile) is supplied in query string,
Authorization header, or X-API-Key / X-Partner-Key headers.
"""
from django.utils import timezone


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

            if token:
                try:
                    from developer.models import UserApiKey
                    from partners.models import PartnerProfile, PartnerClientRelationship

                    key_obj = UserApiKey.objects.filter(key=token, is_active=True).select_related('user').first()
                    if key_obj:
                        request.user = key_obj.user
                        request.api_key_obj = key_obj
                        # Update last used timestamp async-safe
                        UserApiKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())
                    else:
                        partner = PartnerProfile.objects.filter(api_key=token).select_related('user').first()
                        if partner:
                            client_id = request.GET.get('client_id')
                            if client_id:
                                rel = PartnerClientRelationship.objects.filter(partner=partner, client_id=client_id).select_related('client').first()
                                if rel:
                                    request.user = rel.client
                            if not getattr(request, 'user', None) or not request.user.is_authenticated:
                                request.user = partner.user
                except Exception:
                    pass

        response = self.get_response(request)
        return response
