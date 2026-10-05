import json
from functools import wraps
from django.http import JsonResponse
from .models import PartnerProfile, PartnerClientRelationship


def partner_required(view_func):
    """
    Decorator ensuring the request is authenticated with a valid, approved Partner API Key.
    Reads X-Partner-Key header or Bearer token.
    Attaches request.partner (PartnerProfile).
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        api_key = request.headers.get('X-Partner-Key')
        if not api_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                api_key = auth_header.split(' ', 1)[1].strip()
        
        if not api_key:
            return JsonResponse({"status": "error", "message": "Missing partner API key (X-Partner-Key header required)"}, status=401)
        
        partner = PartnerProfile.objects.filter(api_key=api_key).first()
        if not partner:
            return JsonResponse({"status": "error", "message": "Invalid partner API key"}, status=403)
        
        if partner.status != 'approved':
            return JsonResponse({
                "status": "error",
                "message": f"Partner account is not active (current status: {partner.get_status_display()})"
            }, status=403)
        
        request.partner = partner
        return view_func(request, *args, **kwargs)
    return _wrapped


def partner_client_access_required(view_func):
    """
    Decorator ensuring tenant isolation:
    1. Validates partner_required.
    2. Validates client_id from kwargs, GET, or POST.
    3. Verifies client strictly belongs to request.partner.
    Attaches request.client_rel and request.client_user.
    """
    @wraps(view_func)
    @partner_required
    def _wrapped(request, *args, **kwargs):
        client_id = kwargs.get('client_id') or request.GET.get('client_id')
        if not client_id and request.body:
            try:
                body_data = json.loads(request.body)
                client_id = body_data.get('client_id')
            except Exception:
                pass
        
        if not client_id:
            return JsonResponse({"status": "error", "message": "client_id parameter is required"}, status=400)
        
        from django.db.models import Q
        q_filter = Q(client_id=client_id)
        if str(client_id).isdigit():
            q_filter |= Q(id=int(client_id))
        client_rel = PartnerClientRelationship.objects.select_related('client').filter(
            q_filter,
            partner=request.partner
        ).first()

        if not client_rel:
            return JsonResponse({
                "status": "error",
                "message": f"Access denied: Client ID '{client_id}' does not belong to your partner account."
            }, status=404)
        
        request.client_rel = client_rel
        request.client_user = client_rel.client
        return view_func(request, *args, **kwargs)
    return _wrapped
