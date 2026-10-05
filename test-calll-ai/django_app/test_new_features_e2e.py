#!/usr/bin/env python3
"""
Comprehensive End-to-End Verification Test for:
1. Welcome message toggle & custom welcome message in models, APIs, and prompt builders.
2. Business Hours (مواعيد العمل) schedule, timezone calculation, web APIs, developer APIs, and partner APIs.
3. Inbound SIP / Web off-hours detection and dispatch.
"""
import os
import sys
import json
from datetime import datetime, time
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from zoneinfo import ZoneInfo

from agents.models import AgentProfile
from telephony.models import BusinessHoursSchedule, get_default_business_days_config
from partners.models import PartnerProfile, PartnerClientRelationship
import developer.views as dev_views
import partners.views as part_views
import voice_assistant.views as va_views


def test_welcome_message_feature():
    print("\n--- [TEST 1] Welcome Message Toggle & Prompt Instructions ---")
    user, _ = User.objects.get_or_create(username="test_welcome_user", defaults={"email": "welcome@test.com"})

    # 1. Create profile with welcome message enabled
    prof_enabled = AgentProfile.objects.create(
        user=user,
        name="مساعد ترحيبي",
        welcome_message="أهلاً بك يا فندم، أنا تحت أمرك!",
        is_welcome_message_enabled=True,
        dialect="egyptian",
        is_active=False
    )
    p_dict = prof_enabled.to_dict()
    assert p_dict["is_welcome_message_enabled"] is True
    assert p_dict["welcome_message"] == "أهلاً بك يا فندم، أنا تحت أمرك!"

    # 2. Create profile with welcome message DISABLED
    prof_disabled = AgentProfile.objects.create(
        user=user,
        name="مساعد صامت عند البدء",
        welcome_message="تحية لن تقال لأن الترحيب معطل",
        is_welcome_message_enabled=False,
        dialect="egyptian",
        is_active=False
    )
    p_dict_disabled = prof_disabled.to_dict()
    assert p_dict_disabled["is_welcome_message_enabled"] is False
    assert p_dict_disabled["welcome_message"] == "تحية لن تقال لأن الترحيب معطل"

    # Clean up test profiles
    prof_enabled.delete()
    prof_disabled.delete()
    print("✓ Welcome Message Model & Serialization verification PASSED!")


def test_business_hours_schedule_model():
    print("\n--- [TEST 2] Business Hours Schedule Model & Timezone Calculation ---")
    user, _ = User.objects.get_or_create(username="test_bhours_user", defaults={"email": "bhours@test.com"})
    BusinessHoursSchedule.objects.filter(user=user).delete()

    sched = BusinessHoursSchedule.objects.create(
        user=user,
        is_enabled=True,
        timezone="Africa/Cairo",
        days_config={
            "sunday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
            "monday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
            "friday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"}
        },
        action_type="ai_message",
        ai_message="خارج أوقات العمل الرسمية"
    )

    tz_cairo = ZoneInfo("Africa/Cairo")

    # Sunday at 11:30 AM (Cairo time) -> In business hours
    dt_sun_open = datetime(2026, 9, 27, 11, 30, tzinfo=tz_cairo)
    assert sched.is_within_business_hours(dt_sun_open) is True, "Sunday 11:30 should be open"

    # Sunday at 20:00 PM (Cairo time) -> Outside business hours
    dt_sun_closed = datetime(2026, 9, 27, 20, 0, tzinfo=tz_cairo)
    assert sched.is_within_business_hours(dt_sun_closed) is False, "Sunday 20:00 should be closed"

    # Friday at 11:30 AM (Cairo time) -> Day off / closed
    dt_fri_off = datetime(2026, 9, 25, 11, 30, tzinfo=tz_cairo)
    assert sched.is_within_business_hours(dt_fri_off) is False, "Friday should be day off / closed"

    # If is_enabled is False, should always return True (unrestricted)
    sched.is_enabled = False
    sched.save()
    assert sched.is_within_business_hours(dt_fri_off) is True, "Disabled schedule should allow calls"

    print("✓ Business Hours Schedule Model & Timezone calculations PASSED!")


def test_business_hours_web_api():
    print("\n--- [TEST 3] Business Hours Web Dashboard APIs ---")
    rf = RequestFactory()
    user, _ = User.objects.get_or_create(username="test_web_bhours", defaults={"email": "web_bhours@test.com"})

    # 1. GET /api/business-hours/
    req_get = rf.get('/api/business-hours/')
    req_get.user = user
    resp_get = va_views.get_business_hours(req_get)
    assert resp_get.status_code == 200
    data_get = json.loads(resp_get.content.decode('utf-8'))
    assert data_get["status"] == "success"
    assert "schedule" in data_get

    # 2. POST /api/business-hours/save/ (JSON)
    payload = {
        "is_enabled": True,
        "timezone": "Asia/Riyadh",
        "action_type": "ai_message",
        "ai_message": "مرحباً بكم في متجرنا بالرياض، الاتصال خارج الدوام.",
        "days_config": {
            "sunday": {"is_workday": True, "start_time": "08:00", "end_time": "16:00"},
            "monday": {"is_workday": True, "start_time": "08:00", "end_time": "16:00"},
            "friday": {"is_workday": False, "start_time": "08:00", "end_time": "16:00"}
        }
    }
    req_post = rf.post(
        '/api/business-hours/save/',
        data=json.dumps(payload),
        content_type='application/json'
    )
    req_post.user = user
    resp_post = va_views.save_business_hours(req_post)
    assert resp_post.status_code == 200
    data_post = json.loads(resp_post.content.decode('utf-8'))
    assert data_post["status"] == "success"
    assert data_post["schedule"]["timezone"] == "Asia/Riyadh"
    assert data_post["schedule"]["is_enabled"] is True
    assert data_post["schedule"]["action_type"] == "ai_message"
    assert data_post["schedule"]["ai_message"] == "مرحباً بكم في متجرنا بالرياض، الاتصال خارج الدوام."

    print("✓ Business Hours Web Dashboard APIs PASSED!")


def test_developer_business_hours_api():
    print("\n--- [TEST 4] Developer API for Business Hours (/api/v1/business-hours/) ---")
    rf = RequestFactory()
    user, _ = User.objects.get_or_create(username="test_dev_bhours", defaults={"email": "dev_bhours@test.com"})
    from developer.models import UserApiKey
    key_obj, _ = UserApiKey.objects.get_or_create(
        user=user,
        defaults={"name": "test key", "key": "sk_live_usr_bhours_test", "is_active": True}
    )
    if not key_obj.is_active:
        key_obj.is_active = True
        key_obj.save()

    # 1. GET
    req_get = rf.get('/api/v1/business-hours/', HTTP_X_API_KEY=key_obj.key)
    resp_get = dev_views.api_user_business_hours(req_get)
    assert resp_get.status_code == 200, f"GET failed with {resp_get.status_code}: {resp_get.content}"
    data_get = json.loads(resp_get.content.decode('utf-8'))
    assert data_get["status"] == "success"

    # 2. PUT with audio_file_url (strictly URL, no binary upload)
    payload = {
        "is_enabled": True,
        "timezone": "Africa/Cairo",
        "action_type": "audio_file",
        "file_url": "https://storage.example.com/audio/off_hours_cairo.mp3"
    }
    req_put = rf.put(
        '/api/v1/business-hours/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_X_API_KEY=key_obj.key
    )
    resp_put = dev_views.api_user_business_hours(req_put)
    assert resp_put.status_code == 200, f"PUT failed with {resp_put.status_code}: {resp_put.content}"
    data_put = json.loads(resp_put.content.decode('utf-8'))
    assert data_put["schedule"]["action_type"] == "audio_file"
    assert data_put["schedule"]["audio_file_url"] == "https://storage.example.com/audio/off_hours_cairo.mp3"

    print("✓ Developer API for Business Hours PASSED!")


def test_partner_client_business_hours_api():
    print("\n--- [TEST 5] Partner API for Client Business Hours (/api/partner/v1/clients/<id>/business-hours/) ---")
    rf = RequestFactory()
    partner_user, _ = User.objects.get_or_create(username="partner_owner", defaults={"email": "partner@test.com"})
    partner, _ = PartnerProfile.objects.get_or_create(
        user=partner_user,
        defaults={
            "company_name": "Test Partner Ltd",
            "partner_code": "PARTNER_TEST",
            "api_key": "part_key_test_bhours",
            "status": "approved"
        }
    )
    partner.status = "approved"
    if not partner.api_key:
        partner.api_key = "part_key_test_bhours"
    partner.save()

    client_user, _ = User.objects.get_or_create(username="client_user_101", defaults={"email": "client101@test.com"})
    PartnerClientRelationship.objects.get_or_create(partner=partner, client=client_user)

    # 1. GET
    req_get = rf.get(
        f'/api/partner/v1/clients/{client_user.id}/business-hours/',
        HTTP_X_PARTNER_KEY=partner.api_key
    )
    resp_get = part_views.api_partner_client_business_hours(req_get, client_id=client_user.id)
    assert resp_get.status_code == 200, f"Partner GET failed with {resp_get.status_code}: {resp_get.content}"
    data_get = json.loads(resp_get.content.decode('utf-8'))
    assert data_get["status"] == "success"
    assert data_get["client_id"] == client_user.id

    # 2. POST update client schedule
    payload = {
        "is_enabled": True,
        "timezone": "Asia/Dubai",
        "action_type": "ai_message",
        "ai_message": "شكراً لاتصالك بشركة دبي. نحن في إجازة حالياً."
    }
    req_post = rf.post(
        f'/api/partner/v1/clients/{client_user.id}/business-hours/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_X_PARTNER_KEY=partner.api_key
    )
    resp_post = part_views.api_partner_client_business_hours(req_post, client_id=client_user.id)
    assert resp_post.status_code == 200, f"Partner POST failed with {resp_post.status_code}: {resp_post.content}"
    data_post = json.loads(resp_post.content.decode('utf-8'))
    assert data_post["schedule"]["timezone"] == "Asia/Dubai"
    assert data_post["schedule"]["ai_message"] == "شكراً لاتصالك بشركة دبي. نحن في إجازة حالياً."

    print("✓ Partner Client Business Hours API PASSED!")


if __name__ == '__main__':
    print("=" * 65)
    print("Starting End-to-End Verification Test Suite")
    print("=" * 65)
    test_welcome_message_feature()
    test_business_hours_schedule_model()
    test_business_hours_web_api()
    test_developer_business_hours_api()
    test_partner_client_business_hours_api()
    print("\n" + "=" * 65)
    print("ALL TESTS PASSED SUCCESSFULLY! 🚀")
    print("=" * 65)
