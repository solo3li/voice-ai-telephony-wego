import os
import sys

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}" + (f" -> {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" -> {detail}" if detail else ""))

print("\n>>> SUB-TEST: Django ORM, Inngest Job & DNC Execution inside voice_django")

from django.contrib.auth.models import User
from crm.models import DoNotCallEntry, CampaignContact, OutboundCampaign
from crm.inngest_jobs import all_inngest_functions, dispatch_whatsapp_followup_job, fn_process_whatsapp_followup, _initiate_contact_call_sync
from crm.services.campaign_whatsapp import send_campaign_contact_whatsapp

# 1. Inngest function registration
func_ids = [getattr(fn, "id", None) or getattr(fn, "fn_id", None) for fn in all_inngest_functions]
check("Inngest functions list includes WhatsApp followup job",
      "crm-process-whatsapp-followup" in func_ids or any("whatsapp" in str(x).lower() for x in func_ids))

# 2. Dispatch WhatsApp followup
user = User.objects.first()
if not user:
    user = User.objects.create_user(username="test_inngest_user", password="password123")

disp_res = dispatch_whatsapp_followup_job(
    user_id=user.id,
    phone_number="+201009998877",
    trigger_type="inbound_whatsapp",
    inbound_message="مرحبا، أريد استفسار عن الخدمات",
    customer_name="عميل تجريبي"
)
check("dispatch_whatsapp_followup_job returns success/inngest_dispatched or fallback",
      disp_res.get("status") in ["inngest_dispatched", "thread_fallback"], str(disp_res))

# 3. DNC Model & Normalization
test_phone = "+201012345678"
raw_phone = "01012345678"

DoNotCallEntry.objects.filter(phone_number__in=[test_phone, raw_phone]).delete()

dnc_entry = DoNotCallEntry.objects.create(
    user=user,
    phone_number=test_phone,
    customer_name="أحمد للتجربة",
    reason="طلب العميل صراحة عدم الاتصال",
    is_global=False
)
check("DNC Entry created in database", dnc_entry.id is not None)
check("is_blacklisted recognizes normalized +2010... format", DoNotCallEntry.is_blacklisted(user.id, test_phone))
check("is_blacklisted recognizes local 010... format", DoNotCallEntry.is_blacklisted(user.id, raw_phone))

other_user, _ = User.objects.get_or_create(username="other_test_tenant")
check("Tenant isolation: other user not blacklisted by private DNC", not DoNotCallEntry.is_blacklisted(other_user.id, test_phone))

dnc_entry.is_global = True
dnc_entry.save(update_fields=['is_global'])
check("Global DNC blocks number across all tenants", DoNotCallEntry.is_blacklisted(other_user.id, test_phone))

# 4. Campaign Voice Call bypass
camp = OutboundCampaign.objects.create(
    user=user,
    name="حملة اختبار DNC",
    status="running"
)
contact = CampaignContact.objects.create(
    campaign=camp,
    customer_name="أحمد للتجربة",
    phone_number=test_phone,
    call_status="pending"
)

call_res = _initiate_contact_call_sync(contact.id)
contact.refresh_from_db()
check("Voice Campaign automatically skips DNC blacklisted number", call_res.get("status") == "skipped_dnc")
check("Contact call_status set to skipped_dnc", contact.call_status == "skipped_dnc")

# 5. Campaign WhatsApp bypass
camp.status = 'running'
camp.save(update_fields=['status'])
contact.whatsapp_status = 'pending'
contact.save(update_fields=['whatsapp_status'])

wa_res = send_campaign_contact_whatsapp(contact.id)
contact.refresh_from_db()
check("WhatsApp Campaign automatically skips DNC blacklisted number", wa_res.get("status") == "skipped_dnc")
check("Contact whatsapp_status set to skipped_dnc", contact.whatsapp_status == "skipped_dnc")

# Cleanup
contact.delete()
camp.delete()
dnc_entry.delete()

print(f"\nDjango Sub-test result: {passed} PASSED, {failed} FAILED")
if failed > 0:
    sys.exit(1)
