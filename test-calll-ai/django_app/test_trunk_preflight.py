import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from telephony.models import OutboundSIPTrunk, InboundPBXTrunk
from telephony.services import check_has_active_outbound_gateway
from crm.models import OutboundCampaign, CampaignContact
from crm.campaign_views import (
    api_list_campaigns,
    api_get_campaign_detail,
    api_start_campaign,
    api_dial_single_contact,
    api_reset_campaign_contacts
)

rf = RequestFactory()
user = User.objects.get(username='admin')

print("=" * 70)
print("TESTING PRE-FLIGHT OUTBOUND GATEWAY VALIDATION (STRICT CLI TESTING)")
print("=" * 70)

# Step 1: Ensure no active trunks exist
OutboundSIPTrunk.objects.filter(user=user).delete()
InboundPBXTrunk.objects.filter(user=user).delete()

has_gw, trunk_id, trunk_name, caller_id, err_msg = check_has_active_outbound_gateway(user=user)
print(f"[1] Direct Gateway Check without Trunk: has_gw={has_gw}, error='{err_msg}'")
assert has_gw is False, "Expected has_gw to be False when no trunks are configured"

# Step 2: Test API List Campaigns returns has_outbound_gateway=False
req = rf.get('/api/crm/campaigns/')
req.user = user
resp = api_list_campaigns(req)
import json
data = json.loads(resp.content)
print(f"[2] api_list_campaigns: has_outbound_gateway={data.get('has_outbound_gateway')}")
assert data.get('has_outbound_gateway') is False

# Step 3: Get Campaign #4 (or any available campaign)
campaign = OutboundCampaign.objects.filter(user=user).last()
assert campaign is not None, "Need at least one campaign"
print(f"[3] Selected Campaign #{campaign.id}: '{campaign.name}', status='{campaign.status}'")

# Ensure all contacts are currently pending
contact = campaign.contacts.filter(call_status='pending').first()
assert contact is not None, "Expected pending contact in campaign"
initial_status = contact.call_status
initial_retries = contact.retries_count

# Step 4: Attempt to start campaign without SIP Trunk -> MUST return 422 & NOT touch contacts
req_start = rf.post(f'/api/crm/campaigns/{campaign.id}/start/')
req_start.user = user
resp_start = api_start_campaign(req_start, campaign.id)
print(f"[4] api_start_campaign status code: {resp_start.status_code}")
assert resp_start.status_code == 422, f"Expected HTTP 422 but got {resp_start.status_code}"
start_data = json.loads(resp_start.content)
print(f"    Error code: {start_data.get('code')}")
print(f"    Message: {start_data.get('message')}")
assert start_data.get('code') == 'no_outbound_gateway'

# Verify campaign and contact remained unchanged!
campaign.refresh_from_db()
contact.refresh_from_db()
print(f"    Campaign status after blocked start: '{campaign.status}' (expected draft)")
print(f"    Contact status after blocked start: '{contact.call_status}' (expected pending)")
print(f"    Contact retries after blocked start: {contact.retries_count} (expected {initial_retries})")
assert campaign.status == 'draft'
assert contact.call_status == 'pending'
assert contact.retries_count == initial_retries

# Step 5: Attempt to dial single contact without SIP Trunk -> MUST return 422
req_dial = rf.post(f'/api/crm/campaigns/contacts/{contact.id}/dial/')
req_dial.user = user
resp_dial = api_dial_single_contact(req_dial, contact.id)
print(f"[5] api_dial_single_contact status code: {resp_dial.status_code}")
assert resp_dial.status_code == 422
dial_data = json.loads(resp_dial.content)
print(f"    Error code: {dial_data.get('code')}")
assert dial_data.get('code') == 'no_outbound_gateway'
contact.refresh_from_db()
assert contact.call_status == 'pending'

# Step 6: Test Reset Endpoint
# Temporarily mark a contact as failed
contact.call_status = 'failed'
contact.retries_count = 2
contact.call_summary = 'failed test'
contact.save()
assert campaign.contacts.filter(call_status='failed').count() > 0

req_reset = rf.post(f'/api/crm/campaigns/{campaign.id}/reset/')
req_reset.user = user
resp_reset = api_reset_campaign_contacts(req_reset, campaign.id)
assert resp_reset.status_code == 200
reset_data = json.loads(resp_reset.content)
print(f"[6] api_reset_campaign_contacts: {reset_data.get('message')}")
contact.refresh_from_db()
assert contact.call_status == 'pending'
assert contact.retries_count == 0
assert contact.call_summary == ''
print("    Contact successfully reset back to 'pending' with 0 retries.")

# Step 7: Simulate having an active SIP Trunk
test_trunk = OutboundSIPTrunk.objects.create(
    user=user,
    name="Test Cloud Gateway",
    sip_host="sip.example.com",
    sip_port=5060,
    livekit_outbound_trunk_id="ST_simulated_test_trunk_123",
    is_active=True
)
has_gw_active, _, t_name, _, _ = check_has_active_outbound_gateway(user=user)
print(f"[7] Direct Gateway Check with Active Trunk: has_gw={has_gw_active}, trunk='{t_name}'")
assert has_gw_active is True

# Clean up simulated trunk so environment remains clean
test_trunk.delete()
has_gw_cleaned, _, _, _, _ = check_has_active_outbound_gateway(user=user)
assert has_gw_cleaned is False
print("[8] Cleanup: simulated trunk deleted. State is clean.")

print("=" * 70)
print("🎉 ALL PRE-FLIGHT OUTBOUND GATEWAY VERIFICATIONS PASSED 100%!")
print("=" * 70)
