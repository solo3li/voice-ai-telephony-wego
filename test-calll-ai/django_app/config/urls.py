from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
import inngest.django
from common.inngest_client import inngest_client
from crm.inngest_jobs import all_inngest_functions as crm_inngest_functions
from call_center.inngest_jobs import all_call_center_inngest_functions
from knowledge.inngest_jobs import all_knowledge_inngest_functions
from partners.inngest_jobs import all_partner_inngest_functions
from agents.inngest_jobs import all_agent_inngest_functions

combined_inngest_functions = (
    list(crm_inngest_functions)
    + list(all_call_center_inngest_functions)
    + list(all_knowledge_inngest_functions)
    + list(all_partner_inngest_functions)
    + list(all_agent_inngest_functions)
)

import os
from django.http import FileResponse, Http404


def serve_favicon_ico(request):
    for dir_path in [settings.STATIC_ROOT, *(getattr(settings, 'STATICFILES_DIRS', []) or [])]:
        if dir_path:
            p = os.path.join(str(dir_path), 'favicon.ico')
            if os.path.exists(p):
                return FileResponse(open(p, 'rb'), content_type='image/x-icon')
    return Http404()


def serve_favicon_svg(request):
    for dir_path in [settings.STATIC_ROOT, *(getattr(settings, 'STATICFILES_DIRS', []) or [])]:
        if dir_path:
            p = os.path.join(str(dir_path), 'favicon.svg')
            if os.path.exists(p):
                return FileResponse(open(p, 'rb'), content_type='image/svg+xml')
    return Http404()


urlpatterns = [
    path('favicon.ico', serve_favicon_ico, name='favicon_ico'),
    path('favicon.svg', serve_favicon_svg, name='favicon_svg'),
    inngest.django.serve(
        inngest_client,
        combined_inngest_functions,
        serve_origin="http://django:8000",
        serve_path="/api/inngest/",
    ),
    path('admin/', admin.site.urls),
    path('api/knowledge/', include('knowledge.urls')),
    path('api/agents/', include('agents.urls')),
    path('api/call-center/', include('call_center.urls')),
    path('api/telephony/', include('telephony.urls')),
    path('api/crm/', include('crm.urls')),
    path('api/billing/', include('billing.urls')),
    path('api/partner/v1/', include('partners.urls')),
    path('api/v1/', include('developer.urls')),
    path('', include('voice_assistant.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
