#!/usr/bin/env python
import os
import sys
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from agents.models import AgentProfile
from developer.models import UserApiKey
from partners.models import PartnerProfile, PartnerClientRelationship

def test_verbosity_end_to_end():
    print("=" * 70)
    print("🚀 STARTING E2E TEST: Verbosity Control (مختصر / متوازن / مفصل)")
    print("=" * 70)
    
    client = Client()

    # Setup User & Partner
    user, _ = User.objects.get_or_create(username="verbosity_test_user", defaults={"email": "verb@test.com"})
    user_key, _ = UserApiKey.objects.get_or_create(
        user=user,
        defaults={"name": "Verb Key", "key": "sk_live_usr_verb_" + "b" * 28, "is_active": True}
    )
    user_headers = {"HTTP_X_API_KEY": user_key.key}

    partner_owner, _ = User.objects.get_or_create(username="verbosity_partner_owner", defaults={"email": "partner_verb@test.com"})
    partner_profile, _ = PartnerProfile.objects.get_or_create(
        user=partner_owner,
        defaults={
            "company_name": "Verbosity Partner Co",
            "partner_code": "verb_part_001",
            "api_key": "sk_live_part_verb_" + "c" * 28,
            "status": "approved"
        }
    )
    partner_headers = {"HTTP_X_PARTNER_KEY": partner_profile.api_key}

    rel, _ = PartnerClientRelationship.objects.get_or_create(
        partner=partner_profile, client=user, defaults={"external_reference": "ext_verb_999"}
    )

    # 1. Developer Studio API returns verbosities
    print("\n[TEST 1] Testing Developer Studio API: GET /api/v1/profiles/studio/")
    res = client.get('/api/v1/profiles/studio/', **user_headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert "verbosities" in data, "Missing verbosities in studio response"
    v_ids = [v["id"] for v in data["verbosities"]]
    assert "concise" in v_ids and "balanced" in v_ids and "detailed" in v_ids, f"Invalid verbosities: {v_ids}"
    print(f"✅ Developer Studio returns {len(data['verbosities'])} verbosity options: {v_ids}")

    # 2. Partner Studio API returns verbosities
    print("\n[TEST 2] Testing Partner Studio API: GET /api/partner/v1/studio/")
    res = client.get('/api/partner/v1/studio/', **partner_headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    p_data = res.json()
    assert "verbosities" in p_data, "Missing verbosities in partner studio response"
    print(f"✅ Partner Studio returns {len(p_data['verbosities'])} verbosity options.")

    # 3. Create Profile via Developer API with concise verbosity
    print("\n[TEST 3] Testing Create Profile with verbosity='concise' via Developer API")
    create_payload = {
        "name": "المساعد السريع الفوري",
        "voice_name": "Aoede",
        "gender": "female",
        "language": "arabic",
        "dialect": "egyptian",
        "persona_role": "خدمة عملاء فائقة السرعة للرد على استفسارات الأسعار",
        "speaking_style": "مباشر وموجز",
        "verbosity": "concise"
    }
    res = client.post('/api/v1/profiles/', data=json.dumps(create_payload), content_type='application/json', **user_headers)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.content}"
    prof_data = res.json()["profile"]
    assert prof_data["verbosity"] == "concise", f"Expected verbosity='concise', got {prof_data['verbosity']}"
    prof_id = prof_data["id"]
    print(f"✅ Created profile ID={prof_id} with verbosity='concise'.")

    # 4. Update Profile via Developer API to detailed verbosity
    print("\n[TEST 4] Testing Update Profile with verbosity='detailed' via Developer API")
    update_payload = {"verbosity": "detailed"}
    res = client.patch(f'/api/v1/profiles/{prof_id}/', data=json.dumps(update_payload), content_type='application/json', **user_headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    updated_prof = res.json()["profile"]
    assert updated_prof["verbosity"] == "detailed", f"Expected verbosity='detailed', got {updated_prof['verbosity']}"
    print(f"✅ Successfully updated profile to verbosity='detailed'.")

    # 5. Partner Client Profile Create with verbosity='concise'
    print("\n[TEST 5] Testing Partner Client Profile with verbosity='concise'")
    partner_create_payload = {
        "name": "مساعد عميل الشريك المختصر",
        "voice_name": "Fenrir",
        "gender": "male",
        "language": "arabic",
        "dialect": "saudi",
        "persona_role": "مستشار عقاري",
        "speaking_style": "واثق وسريع",
        "verbosity": "concise"
    }
    res = client.post(f'/api/partner/v1/clients/{user.id}/profiles/', data=json.dumps(partner_create_payload), content_type='application/json', **partner_headers)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.content}"
    p_prof_data = res.json()["profile"]
    assert p_prof_data["verbosity"] == "concise", f"Expected concise, got {p_prof_data['verbosity']}"
    p_prof_id = p_prof_data["id"]
    print(f"✅ Partner profile created with verbosity='concise' ID={p_prof_id}.")

    # 6. Test Model to_dict serialization
    print("\n[TEST 6] Testing AgentProfile model to_dict serialization")
    db_profile = AgentProfile.objects.get(id=prof_id)
    d = db_profile.to_dict()
    assert "verbosity" in d and "verbosity_display" in d, f"Missing verbosity in to_dict: {d}"
    print(f"✅ Model to_dict correctly includes verbosity='{d['verbosity']}' and display='{d['verbosity_display']}'.")

    # Clean up test profiles
    AgentProfile.objects.filter(id__in=[prof_id, p_prof_id]).delete()

    print("\n" + "=" * 70)
    print("🎉 ALL VERBOSITY E2E TESTS PASSED 100% SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    test_verbosity_end_to_end()
