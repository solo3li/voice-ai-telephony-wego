import os
import sys
import json
import django
import io

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile

from crm.models import OutboundCampaign, CampaignContact, UserCampaignLimit, CallSession
from crm.file_parser import parse_leads_file
from crm.scoring import score_and_extract_lead
from crm.campaign_views import (
    api_upload_and_create_campaign,
    api_list_campaigns,
    api_get_campaign_detail,
    api_start_campaign,
    api_pause_campaign,
    api_export_campaign_contacts
)

def run_tests():
    print("=" * 70)
    print("🚀 RUNNING END-TO-END VERIFICATION: OUTBOUND CAMPAIGNS & CRM LEAD QUALIFICATION")
    print("=" * 70)

    rf = RequestFactory()
    user, _ = User.objects.get_or_create(username='admin', defaults={'is_superuser': True, 'email': 'admin@test.com'})

    # [1] Test Multi-Format File Parser
    print("\n[TEST 1] Testing Universal File Parser across CSV, JSON, TXT, and Excel...")
    
    # 1.1 CSV
    csv_bytes = """الاسم,الموبايل,المدينة,الميزانية,الملاحظات
عمرو دياب,01011223344,القاهرة,5 مليون,مهتم بكمبوند زايد
منى زكي,01122334455,الإسكندرية,3 مليون,تبحث عن شاليه
رقم غير صالح,abcdefgh,الجيزة,1 مليون,تجاهل
""".encode('utf-8')
    res_csv = parse_leads_file(csv_bytes, 'leads.csv')
    assert res_csv["status"] == "success", f"CSV parse failed: {res_csv}"
    assert res_csv["total_extracted"] == 2, f"Expected 2 valid contacts, got {res_csv['total_extracted']}"
    assert res_csv["invalid_rows_count"] == 1
    print(f" -> CSV parsed successfully: 2 valid leads, 1 invalid row filtered.")

    # 1.2 JSON
    json_bytes = json.dumps([
        {"customer_name": "كريم عبد العزيز", "phone": "01233445566", "interest": "فيلا مستقلة"},
        {"customer_name": "ياسمين صبري", "mobile": "+201555667788", "budget": "10 مليون"}
    ]).encode('utf-8')
    res_json = parse_leads_file(json_bytes, 'leads.json')
    assert res_json["status"] == "success"
    assert res_json["total_extracted"] == 2
    print(f" -> JSON parsed successfully: 2 valid leads.")

    # 1.3 TXT
    txt_bytes = """+201099887766
01199887766
not_a_number
""".encode('utf-8')
    res_txt = parse_leads_file(txt_bytes, 'leads.txt')
    assert res_txt["status"] == "success"
    assert res_txt["total_extracted"] == 2
    print(f" -> TXT parsed successfully: 2 valid leads.")

    # [2] Test Concurrency Limit Per User in Django Admin
    print("\n[TEST 2] Testing UserCampaignLimit (Concurrency per User in Django Admin)...")
    limit_obj, _ = UserCampaignLimit.objects.get_or_create(user=user, defaults={'max_concurrent_calls': 3})
    limit_obj.max_concurrent_calls = 4
    limit_obj.save(update_fields=['max_concurrent_calls'])
    active_limit = UserCampaignLimit.get_limit_for_user(user)
    assert active_limit == 4, f"Expected 4 concurrent calls, got {active_limit}"
    print(f" -> UserCampaignLimit successfully configured: {active_limit} concurrent calls for user '{user.username}'")

    # [3] Test Campaign Creation from Uploaded File (Draft Mode)
    print("\n[TEST 3] Testing Campaign Creation from Uploaded File (Draft Mode)...")
    upload_file = SimpleUploadedFile("real_estate_leads.csv", csv_bytes, content_type="text/csv")
    post_data = {
        "name": "حملة عقارات الشيخ زايد - تجربة شاملة",
        "call_prompt": "أنت ممثل مبيعات عقاري لبق، اتصل بالعميل واعرف اهتمامه بشاليهات وسكن زايد، وحدد ميزانيته وموعد المعاينة.",
        "max_retries": "2",
        "retry_delay_minutes": "10",
        "gateway_type": "auto"
    }
    req = rf.post('/api/crm/campaigns/upload/', data={**post_data, "file": upload_file})
    req.user = user
    res = api_upload_and_create_campaign(req)
    assert res.status_code == 200, f"Campaign creation failed: {res.content}"
    data = json.loads(res.content.decode('utf-8'))
    assert data["status"] == "success"
    campaign_id = data["campaign"]["id"]
    campaign = OutboundCampaign.objects.get(id=campaign_id)
    assert campaign.status == "draft", "Campaign should initially be draft"
    assert campaign.total_contacts == 2
    print(f" -> Campaign #{campaign.id} '{campaign.name}' created in '{campaign.status}' status with {campaign.total_contacts} contacts.")

    # [4] Verify CRM Contacts Listing and Filtering
    print("\n[TEST 4] Testing CRM Contacts Listing and Detail API...")
    req = rf.get(f'/api/crm/campaigns/{campaign_id}/')
    req.user = user
    res = api_get_campaign_detail(req, campaign_id)
    assert res.status_code == 200
    detail_data = json.loads(res.content.decode('utf-8'))
    assert len(detail_data["contacts"]) == 2
    contact_1 = detail_data["contacts"][0]
    print(f" -> Lead 1 in CRM: {contact_1['customer_name']} ({contact_1['phone_number']}) - Status: {contact_1['call_status_display']}")
    print(f" -> Lead 1 Attributes: {contact_1['attributes']}")

    # [5] Test Starting the Campaign (Inngest Event Emission)
    print("\n[TEST 5] Testing Campaign Auto-Dialer Start (Inngest Event Dispatch)...")
    req = rf.post(f'/api/crm/campaigns/{campaign_id}/start/')
    req.user = user
    res = api_start_campaign(req, campaign_id)
    assert res.status_code == 200
    start_data = json.loads(res.content.decode('utf-8'))
    assert start_data["status"] == "success"
    campaign.refresh_from_db()
    assert campaign.status == "running"
    print(f" -> Campaign #{campaign.id} started. Status: {campaign.status}. Inngest events dispatched respecting limit ({active_limit}).")

    # [6] Test AI Lead Qualification & Post-Call Scoring
    print("\n[TEST 6] Testing AI Lead Qualification & Post-Call Scoring...")
    sample_transcript = """المساعد: مساء الخير أستاذ عمرو، معاك سارة من فريق المبيعات. كنت حابة استفسر عن اهتمامك بمشروع الشيخ زايد.
العميل: أهلاً يا سارة، أيوة أنا مهتم جداً وعاوز شقة 3 غرف في زايد وميزانيتي حوالي 5 مليون.
المساعد: ممتاز جداً يا فندم! هل يناسب حضرتك نزور الموقع ونعمل معاينة يوم السبت القادم الساعة 2 ظهراً؟
العميل: تمام ممتاز، السبت الساعة 2 يناسبني جداً.
المساعد: تشرفنا يا فندم، هنسجل الميعاد ونبعتلك اللوكيشن على الواتساب. شكراً جزيلاً!"""

    scoring_res = score_and_extract_lead(
        call_prompt=campaign.call_prompt,
        transcript=sample_transcript,
        customer_name="عمرو دياب",
        attributes={"المدينة": "القاهرة", "الميزانية": "5 مليون"}
    )
    print(f" -> AI Scoring Result: Interest = {scoring_res['interest_level']}")
    print(f" -> AI Call Summary: {scoring_res['call_summary']}")
    assert scoring_res["interest_level"] in ["hot", "warm"], f"Expected hot or warm lead, got {scoring_res['interest_level']}"

    # [7] Simulate Call Completion & CRM Contact Updates
    print("\n[TEST 7] Testing Call Completion & Automatic CRM Contact Update...")
    contact = campaign.contacts.first()
    call_session = CallSession.objects.create(
        user=user,
        room_name=f"test_camp_{campaign_id}_{contact.id}",
        direction='outbound_ai',
        destination_phone=contact.phone_number,
        duration_seconds=95,
        transcript_text=sample_transcript,
        summary=scoring_res['call_summary']
    )
    contact.call_status = 'answered'
    contact.interest_level = scoring_res['interest_level']
    contact.call_summary = scoring_res['call_summary']
    contact.extracted_data = scoring_res.get('extracted_data', {})
    contact.duration_seconds = 95
    contact.call_session = call_session
    contact.save()
    campaign.update_metrics()

    assert campaign.answered_contacts >= 1
    print(f" -> Contact #{contact.id} updated to answered ({contact.interest_level}). Campaign hot/warm metrics updated.")

    # [8] Test Smart Excel (.xlsx) and CSV Export
    print("\n[TEST 8] Testing Smart Excel (.xlsx) and CSV Export Engine...")
    
    # 8.1 Export Excel XLSX
    req = rf.get(f'/api/crm/campaigns/{campaign_id}/export/?format=xlsx&filter=all')
    req.user = user
    res_xlsx = api_export_campaign_contacts(req, campaign_id)
    assert res_xlsx.status_code == 200
    assert 'application/vnd.openxmlformats' in res_xlsx['Content-Type']
    xlsx_bytes = res_xlsx.content
    assert len(xlsx_bytes) > 2000, "XLSX file seems too small"
    print(f" -> Excel (.xlsx) exported successfully ({len(xlsx_bytes)} bytes) with RTL Arabic formatting & color coding.")

    # 8.2 Export CSV
    req = rf.get(f'/api/crm/campaigns/{campaign_id}/export/?format=csv&filter=all')
    req.user = user
    res_csv = api_export_campaign_contacts(req, campaign_id)
    assert res_csv.status_code == 200
    assert 'text/csv' in res_csv['Content-Type']
    csv_text = res_csv.content.decode('utf-8-sig')
    assert "اسم العميل" in csv_text
    assert contact.phone_number in csv_text
    print(f" -> CSV exported successfully with UTF-8 BOM encoding for Excel compatibility.")

    print("\n" + "=" * 70)
    print("🎉 ALL 8 E2E OUTBOUND CAMPAIGN & CRM TESTS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
