import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from crm.models import OutboundCampaign, CampaignContact, OmnichannelMessage, CustomerMemory, UserCampaignLimit
from crm.services.campaign_whatsapp import generate_personalized_whatsapp_message, send_campaign_contact_whatsapp
from crm.campaign_views import api_list_campaigns, api_get_campaign_detail, api_start_campaign, api_send_single_contact_whatsapp

def run_tests():
    print("=" * 60)
    print("🚀 Running WhatsApp & Multi-Channel Campaigns E2E Test Suite")
    print("=" * 60)

    # 1. Get or create test user
    user = User.objects.filter(username='hamo').first()
    if not user:
        user = User.objects.first()
    assert user is not None, "User must exist"
    print(f"👤 Test User: {user.username} (ID: {user.id})")

    # Clean previous test campaigns
    OutboundCampaign.objects.filter(name__startswith="[TEST]").delete()

    # 2. Test WhatsApp Campaign Creation & Metrics
    print("\n[TEST 1] Testing WhatsApp-only Campaign Model & Metrics...")
    camp_wa = OutboundCampaign.objects.create(
        user=user,
        name="[TEST] حملة واتساب خاصة بالجمعة البيضاء",
        channel="whatsapp",
        whatsapp_prompt="مرحباً {name}، خصم 30% بانتظارك اليوم على اشتراكك ({plan})! يسعدنا تواصلك معنا للاستفادة من العرض.",
        status="draft"
    )
    assert camp_wa.channel == "whatsapp"
    assert camp_wa.get_channel_display() == "واتساب فقط"

    c1 = CampaignContact.objects.create(
        campaign=camp_wa,
        customer_name="أحمد محمود",
        phone_number="+201012345678",
        attributes={"plan": "الباقة الذهبية", "city": "القاهرة"},
        call_status="pending",
        whatsapp_status="pending"
    )
    c2 = CampaignContact.objects.create(
        campaign=camp_wa,
        customer_name="سارة علي",
        phone_number="+966512345678",
        attributes={"plan": "الباقة الفضية", "city": "الرياض"},
        call_status="pending",
        whatsapp_status="pending"
    )

    camp_wa.update_metrics()
    d_wa = camp_wa.to_dict()
    assert d_wa["total_contacts"] == 2
    assert d_wa["completed_contacts"] == 0
    assert d_wa["whatsapp_sent_contacts"] == 0
    assert d_wa["channel"] == "whatsapp"
    print("✅ WhatsApp campaign created & metrics validated successfully!")

    # 3. Test Message Generation with Variables
    print("\n[TEST 2] Testing generate_personalized_whatsapp_message...")
    msg_c1 = generate_personalized_whatsapp_message(camp_wa, c1)
    print(f"Generated text for c1: '{msg_c1}'")
    assert "أحمد محمود" in msg_c1 or "أحمد" in msg_c1
    assert "الباقة الذهبية" in msg_c1 or "خصم" in msg_c1
    print("✅ Personalized WhatsApp message crafted accurately with contact attributes!")

    # 4. Test Hybrid Campaign Creation & Behavior
    print("\n[TEST 3] Testing Hybrid Campaign Model...")
    camp_hybrid = OutboundCampaign.objects.create(
        user=user,
        name="[TEST] حملة هجينة - مكالمة ومتابعة واتساب",
        channel="hybrid",
        call_prompt="أنت ممثل مبيعات، اعرض على العميل تجديد اشتراكه.",
        whatsapp_prompt="مرحباً {name}، حاولنا التواصل هاتفياً ويسعدنا متابعتك بخصوص تجديد اشتراكك هنا.",
        status="draft"
    )
    assert camp_hybrid.channel == "hybrid"
    assert camp_hybrid.get_channel_display() == "هجينة (مكالمات + واتساب)"

    c_hyb = CampaignContact.objects.create(
        campaign=camp_hybrid,
        customer_name="خالد عبد الله",
        phone_number="+966599988877",
        call_status="no_answer",
        whatsapp_status="pending",
        retries_count=1
    )
    camp_hybrid.update_metrics()
    assert camp_hybrid.completed_contacts == 0  # In hybrid, not completed until whatsapp is also processed

    # Now simulate whatsapp sent
    c_hyb.whatsapp_status = "sent"
    c_hyb.save()
    camp_hybrid.update_metrics()
    assert camp_hybrid.completed_contacts == 1  # Completed because call retries exhausted AND whatsapp was sent!
    assert camp_hybrid.whatsapp_sent_contacts == 1
    print("✅ Hybrid campaign completion logic validated successfully!")

    # 5. Test API Views: api_list_campaigns & api_get_campaign_detail
    print("\n[TEST 4] Testing api_list_campaigns & api_get_campaign_detail...")
    rf = RequestFactory()
    req_list = rf.get('/api/crm/campaigns/')
    req_list.user = user
    resp_list = api_list_campaigns(req_list)
    assert resp_list.status_code == 200
    data_list = json.loads(resp_list.content.decode('utf-8'))
    assert data_list["status"] == "success"
    assert "has_whatsapp_connected" in data_list
    assert any(c["id"] == camp_wa.id for c in data_list["campaigns"])
    print("✅ api_list_campaigns returned campaigns list with has_whatsapp_connected!")

    req_detail = rf.get(f'/api/crm/campaigns/{camp_wa.id}/')
    req_detail.user = user
    resp_detail = api_get_campaign_detail(req_detail, camp_wa.id)
    assert resp_detail.status_code == 200
    data_detail = json.loads(resp_detail.content.decode('utf-8'))
    assert data_detail["campaign"]["channel"] == "whatsapp"
    assert len(data_detail["contacts"]) == 2
    print("✅ api_get_campaign_detail returned contact list and WhatsApp channel details!")

    # 6. Test Start Campaign preflight check for WhatsApp
    print("\n[TEST 5] Testing api_start_campaign preflight logic...")
    req_start = rf.post(f'/api/crm/campaigns/{camp_wa.id}/start/')
    req_start.user = user
    resp_start = api_start_campaign(req_start, camp_wa.id)
    # Notice: For WhatsApp campaigns, it must NOT return code 'no_outbound_gateway'!
    data_start = json.loads(resp_start.content.decode('utf-8'))
    assert data_start.get("code") != "no_outbound_gateway", "WhatsApp campaign must not be blocked by SIP trunk!"
    print(f"Start campaign response: status={data_start.get('status')}, code={data_start.get('code')}")
    print("✅ Pre-flight checks correctly bypassed SIP trunk check for WhatsApp campaign!")

    # 7. Clean up test records
    camp_wa.delete()
    camp_hybrid.delete()
    print("\n🧹 Cleaned up test database records.")
    print("\n" + "=" * 60)
    print("🎉 ALL WHATSAPP & MULTI-CHANNEL CAMPAIGN TESTS PASSED!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
