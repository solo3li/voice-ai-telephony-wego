from django.urls import path
from . import views

app_name = 'telephony'

urlpatterns = [
    path('trunk/', views.get_outbound_trunk, name='get_outbound_trunk'),
    path('trunk/save/', views.save_outbound_trunk, name='save_outbound_trunk'),
    path('trunk/<int:trunk_id>/delete/', views.delete_outbound_trunk, name='delete_outbound_trunk'),
    path('ai-call/', views.trigger_ai_outbound_call, name='trigger_ai_outbound_call'),
    path('outbound-gateways/', views.list_outbound_gateways, name='list_outbound_gateways'),
    path('pbx-trunks/', views.list_pbx_trunks, name='list_pbx_trunks'),
    path('pbx-trunks/save/', views.save_pbx_trunk, name='save_pbx_trunk'),
    path('pbx-trunks/<int:trunk_id>/delete/', views.delete_pbx_trunk, name='delete_pbx_trunk'),
]
