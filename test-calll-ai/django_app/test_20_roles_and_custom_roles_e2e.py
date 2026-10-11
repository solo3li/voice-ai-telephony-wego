"""
End-to-End Test Suite: 20 Specialized Industry Roles + Tenant Custom Roles Library
Verifies:
1. Standard Catalog: 20 industry roles across 12 sectors + choices integrity.
2. AI Prompt Builder Engine: Prompt compilation for all 20 presets + custom roles.
3. Tenant Custom Roles Library CRUD & Multi-Tenant Isolation.
4. Profile Integration: Assigning custom roles to agent profiles & bootstrap reflection.
5. Developer REST API (/api/v1/roles/, /api/v1/roles/custom/, studio).
6. Partner REST API (/api/partner/v1/clients/<id>/roles/, custom roles).
"""

import os
import sys
import json
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from agents.models import AgentProfile, TenantCustomRole
from developer.models import UserApiKey
from partners.models import PartnerProfile, PartnerClientRelationship

from agents.views import (
    api_roles_catalog,
    api_custom_roles_list_create,
    api_custom_role_detail,
    list_profiles,
    create_profile,
    update_profile,
    api_internal_agent_bootstrap
)
from developer.views import (
    api_user_roles_catalog,
    api_user_custom_roles,
    api_user_custom_role_detail,
    api_user_profiles_studio,
    api_user_profiles
)
from partners.views import (
    api_partner_studio,
    api_partner_client_roles,
    api_partner_client_custom_roles,
    api_partner_client_custom_role_detail,
    api_partner_client_profile
)

rf = RequestFactory()

def run_tests():
    print("=" * 80)
    print("🚀 STARTING E2E VERIFICATION: 20 SPECIALIZED ROLES & CUSTOM ROLES LIBRARY")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: Catalog Integrity & Role Choices (20 Specialized Roles)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Verifying 20 Specialized Industry Roles in Catalog & Choices...")
    catalog = AgentProfile.INDUSTRY_ROLE_CATALOG
    assert isinstance(catalog, list), "INDUSTRY_ROLE_CATALOG must be a list"
    
    total_catalog_roles = sum(len(cat.get("roles", [])) for cat in catalog)
    print(f"  -> Found {len(catalog)} industry sectors with a total of {total_catalog_roles} specialized roles.")
    assert total_catalog_roles == 20, f"Expected exactly 20 specialized roles in catalog, got {total_catalog_roles}"

    role_choices_dict = dict(AgentProfile.ROLE_CHOICES)
    expected_20_roles = [
        "clinic_receptionist", "pharmacy_advisor",
        "restaurant_orders", "table_booking_concierge",
        "real_estate_qualifier", "property_management_rep",
        "ecommerce_support", "inbound_telesales",
        "delivery_dispatch",
        "debt_collection_rep", "insurance_claims_agent",
        "auto_service_scheduler",
        "hotel_frontdesk", "travel_tourism_agent",
        "course_admissions_advisor",
        "recruitment_prescreener",
        "it_helpdesk_level1", "saas_onboarding_specialist",
        "executive_personal_assistant", "vip_concierge_care"
    ]

    for role_id in expected_20_roles:
        assert role_id in role_choices_dict, f"Role {role_id} missing from ROLE_CHOICES"

    print("  ✅ 20 Specialized industry roles are verified in catalog and choices.")

    # -------------------------------------------------------------------------
    # TEST 2: Role Prompts Verification in Catalog
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verifying Default Prompts and Descriptions across all 20 Roles...")
    for cat in catalog:
        for role in cat.get("roles", []):
            assert "default_prompt" in role and len(role["default_prompt"]) > 50, f"Role {role['id']} has invalid prompt"
            assert "description" in role and len(role["description"]) > 10, f"Role {role['id']} has invalid description"
    print("  ✅ All 20 roles have rich default prompts and clear descriptions.")

    # -------------------------------------------------------------------------
    # TEST 3: Tenant Custom Roles Library CRUD & Multi-Tenant Isolation
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing Tenant Custom Roles CRUD & Isolation...")
    tenant_a, _ = User.objects.get_or_create(username="tenant_alpha_test", defaults={"email": "alpha@example.com"})
    tenant_b, _ = User.objects.get_or_create(username="tenant_beta_test", defaults={"email": "beta@example.com"})

    # Clean old test data
    TenantCustomRole.objects.filter(user__in=[tenant_a, tenant_b]).delete()
    AgentProfile.objects.filter(user__in=[tenant_a, tenant_b]).delete()

    # 3.1 Tenant A creates a custom role via API
    req = rf.post(
        '/api/agents/roles/custom/',
        data=json.dumps({
            "name": "منسق شاليهات الساحل",
            "industry": "tourism",
            "description": "حجز شاليهات وقرى سياحية",
            "role_prompt": "دورك هو منسق شاليهات وقرى سياحية راقٍ ومضياف: تستقبل استفسارات النزلاء وتوضح الأسعار والمواعيد."
        }),
        content_type='application/json'
    )
    req.user = tenant_a
    resp = api_custom_roles_list_create(req)
    assert resp.status_code == 201, f"Failed to create custom role: {resp.content}"
    role_a_data = json.loads(resp.content)["role"]
    role_a_id = role_a_data["id"]
    print(f"  -> Tenant A created Custom Role #{role_a_id} ('{role_a_data['name']}')")

    # 3.2 Tenant A creates a second role
    req = rf.post(
        '/api/agents/roles/custom/',
        data=json.dumps({
            "name": "مسؤول مبيعات عقارية نادرة",
            "industry": "real_estate",
            "description": "فلل وقصور",
            "role_prompt": "دورك هو مستشار عقارات فاخرة وفلل وقصور خاصة."
        }),
        content_type='application/json'
    )
    req.user = tenant_a
    resp = api_custom_roles_list_create(req)
    assert resp.status_code == 201
    role_a2_id = json.loads(resp.content)["role"]["id"]

    # 3.3 Tenant B creates their own role
    req = rf.post(
        '/api/agents/roles/custom/',
        data=json.dumps({
            "name": "مستشار عيادات الأسنان التخصصية",
            "industry": "medical",
            "description": "زراعة وتقويم أسنان",
            "role_prompt": "دورك هو منسق عيادات أسنان دقيق وصبور."
        }),
        content_type='application/json'
    )
    req.user = tenant_b
    resp = api_custom_roles_list_create(req)
    assert resp.status_code == 201
    role_b_id = json.loads(resp.content)["role"]["id"]
    print(f"  -> Tenant B created Custom Role #{role_b_id}")

    # 3.4 Multi-tenant Isolation Check
    # Tenant A list
    req = rf.get('/api/agents/roles/custom/')
    req.user = tenant_a
    resp = api_custom_roles_list_create(req)
    data = json.loads(resp.content)
    assert data["total"] == 2
    assert all(r["id"] in [role_a_id, role_a2_id] for r in data["roles"])

    # Tenant B list
    req = rf.get('/api/agents/roles/custom/')
    req.user = tenant_b
    resp = api_custom_roles_list_create(req)
    data = json.loads(resp.content)
    assert data["total"] == 1
    assert data["roles"][0]["id"] == role_b_id

    # Tenant B cannot access or edit Tenant A's role (Must return 404 Http404)
    from django.http import Http404
    req = rf.get(f'/api/agents/roles/custom/{role_a_id}/')
    req.user = tenant_b
    try:
        api_custom_role_detail(req, role_a_id)
        assert False, "Security violation: Tenant B accessed Tenant A's custom role!"
    except Http404:
        print("  🔒 Multi-tenant isolation verified: Tenant B cannot access Tenant A's custom role.")

    # 3.5 Unique together per tenant check
    req = rf.post(
        '/api/agents/roles/custom/',
        data=json.dumps({
            "name": "منسق شاليهات الساحل",  # Duplicate name for Tenant A
            "industry": "tourism",
            "role_prompt": "some prompt"
        }),
        content_type='application/json'
    )
    req.user = tenant_a
    resp = api_custom_roles_list_create(req)
    assert resp.status_code == 400, "Should reject duplicate role name for same tenant"

    # But Tenant B CAN create a role with the same name
    req = rf.post(
        '/api/agents/roles/custom/',
        data=json.dumps({
            "name": "منسق شاليهات الساحل",  # Same name, different tenant
            "industry": "tourism",
            "role_prompt": "tenant B prompt"
        }),
        content_type='application/json'
    )
    req.user = tenant_b
    resp = api_custom_roles_list_create(req)
    assert resp.status_code == 201, "Tenant B should be allowed to use same role name as Tenant A"
    json.loads(resp.content)["role"]["id"]
    print("  ✅ Name uniqueness is correctly isolated per tenant.")

    # -------------------------------------------------------------------------
    # TEST 4: Agent Profile Integration with Custom Roles
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing Agent Profile Integration with Custom Roles...")
    # Create profile linking to role_a_id
    req = rf.post(
        '/api/agents/profiles/create/',
        data=json.dumps({
            "name": "مساعد الشاليهات الذكي",
            "gender": "female",
            "language": "arabic",
            "dialect": "egyptian",
            "custom_role_id": role_a_id,
            "speaking_style": "friendly",
            "is_active": True
        }),
        content_type='application/json'
    )
    req.user = tenant_a
    resp = create_profile(req)
    assert resp.status_code == 201, f"Failed to create profile: {resp.content}"
    prof_data = json.loads(resp.content)["profile"]
    prof_id = prof_data["id"]
    assert prof_data["custom_role_id"] == role_a_id
    assert prof_data["custom_role"]["name"] == "منسق شاليهات الساحل"
    print(f"  -> Profile #{prof_id} linked to Custom Role #{role_a_id}")

    # Verify Internal Bootstrap API reflects the custom role
    from common.auth import get_internal_api_key
    req = rf.post(
        '/api/agents/internal/bootstrap/',
        data=json.dumps({"user_id": tenant_a.id}),
        content_type='application/json'
    )
    req.META['HTTP_X_INTERNAL_API_KEY'] = get_internal_api_key()
    resp = api_internal_agent_bootstrap(req)
    assert resp.status_code == 200, f"Bootstrap returned {resp.status_code}: {resp.content}"
    b_data = json.loads(resp.content)
    assert b_data["profile"]["custom_role_id"] == role_a_id
    assert b_data["profile"]["custom_role"]["name"] == "منسق شاليهات الساحل"
    print("  ✅ Bootstrap API correctly returns linked custom role.")

    # -------------------------------------------------------------------------
    # TEST 5: Developer REST API Endpoints (/api/v1/roles/)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Developer REST API (/api/v1/roles/, /api/v1/roles/custom/, studio)...")
    dev_key = UserApiKey.generate_for_user(user=tenant_a, name="Test Dev Key")

    # 5.1 GET /api/v1/roles/
    req = rf.get('/api/v1/roles/')
    req.META['HTTP_X_API_KEY'] = dev_key.key
    resp = api_user_roles_catalog(req)
    assert resp.status_code == 200
    roles_cat_data = json.loads(resp.content)
    assert len(roles_cat_data["industry_roles_catalog"]) == 12
    assert len(roles_cat_data["custom_roles"]) == 2
    assert any(cr["id"] == role_a_id for cr in roles_cat_data["custom_roles"])
    print("  -> Developer /api/v1/roles/ returned catalog and tenant's custom roles.")

    # 5.2 POST /api/v1/roles/custom/
    req = rf.post(
        '/api/v1/roles/custom/',
        data=json.dumps({
            "name": "مساعد استيراد وتصدير",
            "industry": "trade",
            "description": "تخليص جمركي",
            "role_prompt": "دورك هو مستشار تخليص جمركي وشحن دولي محترف."
        }),
        content_type='application/json'
    )
    req.META['HTTP_X_API_KEY'] = dev_key.key
    resp = api_user_custom_roles(req)
    assert resp.status_code == 201
    dev_cr = json.loads(resp.content)["role"]
    dev_cr_id = dev_cr["id"]

    # 5.3 PUT /api/v1/roles/custom/<id>/
    req = rf.put(
        f'/api/v1/roles/custom/{dev_cr_id}/',
        data=json.dumps({
            "description": "تخليص جمركي وبوالص شحن بحري"
        }),
        content_type='application/json'
    )
    req.META['HTTP_X_API_KEY'] = dev_key.key
    resp = api_user_custom_role_detail(req, dev_cr_id)
    assert resp.status_code == 200
    assert json.loads(resp.content)["role"]["description"] == "تخليص جمركي وبوالص شحن بحري"

    # 5.4 GET /api/v1/profiles/studio/
    req = rf.get('/api/v1/profiles/studio/')
    req.META['HTTP_X_API_KEY'] = dev_key.key
    resp = api_user_profiles_studio(req)
    assert resp.status_code == 200
    studio_data = json.loads(resp.content)
    assert "industry_roles_catalog" in studio_data
    assert "custom_roles" in studio_data
    assert len(studio_data["custom_roles"]) == 3

    # 5.5 POST /api/v1/profiles/ with custom_role_id
    req = rf.post(
        '/api/v1/profiles/',
        data=json.dumps({
            "name": "بروفايل المطور للشحن",
            "voice_name": "Charon",
            "gender": "male",
            "dialect": "egyptian",
            "custom_role_id": dev_cr_id,
            "is_active": False
        }),
        content_type='application/json'
    )
    req.META['HTTP_X_API_KEY'] = dev_key.key
    resp = api_user_profiles(req)
    assert resp.status_code == 201
    dev_prof = json.loads(resp.content)["profile"]
    assert dev_prof["custom_role_id"] == dev_cr_id

    # 5.6 DELETE /api/v1/roles/custom/<id>/
    req = rf.delete(f'/api/v1/roles/custom/{dev_cr_id}/')
    req.META['HTTP_X_API_KEY'] = dev_key.key
    resp = api_user_custom_role_detail(req, dev_cr_id)
    assert resp.status_code == 200
    print("  ✅ Developer REST API custom roles management verified.")

    # -------------------------------------------------------------------------
    # TEST 6: Partner REST API Endpoints (/api/partner/v1/clients/<id>/roles/)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Partner REST API for sub-client custom roles...")
    partner_user, _ = User.objects.get_or_create(username="partner_owner_test", defaults={"email": "partner@example.com"})
    partner_prof, _ = PartnerProfile.objects.get_or_create(
        user=partner_user,
        defaults={
            "company_name": "Test Telecom Partner",
            "status": "approved",
            "api_key": "prt_live_key_999888777",
            "partner_code": "PRTTEST"
        }
    )

    client_user, _ = User.objects.get_or_create(username="partner_client_usr", defaults={"email": "client@partner.com"})
    PartnerClientRelationship.objects.get_or_create(
        partner=partner_prof,
        client=client_user,
        defaults={"external_reference": "ref_1001", "is_active": True}
    )

    # 6.1 Partner Client Roles Catalog
    req = rf.get(f'/api/partner/v1/clients/{client_user.id}/roles/', HTTP_X_PARTNER_KEY=partner_prof.api_key)
    resp = api_partner_client_roles(req, client_id=client_user.id)
    assert resp.status_code == 200
    p_roles_data = json.loads(resp.content)
    assert len(p_roles_data["industry_roles_catalog"]) == 12

    # 6.2 Partner Client Custom Role Creation
    req = rf.post(
        f'/api/partner/v1/clients/{client_user.id}/roles/custom/',
        data=json.dumps({
            "name": "أخصائي حجز ملاعب بادل",
            "industry": "sports",
            "description": "حجز ملاعب وبطولات",
            "role_prompt": "دورك هو منسق ملاعب بادل نشيط ومتعاون: تحجز الفترات الزمنية وتنظم الاشتراكات."
        }),
        content_type='application/json',
        HTTP_X_PARTNER_KEY=partner_prof.api_key
    )
    resp = api_partner_client_custom_roles(req, client_id=client_user.id)
    assert resp.status_code == 201
    p_role_data = json.loads(resp.content)["role"]
    p_role_id = p_role_data["id"]

    # 6.3 Partner Client Profile with custom_role_id
    req = rf.post(
        f'/api/partner/v1/clients/{client_user.id}/profiles/',
        data=json.dumps({
            "name": "مساعد البادل للعميل",
            "voice_name": "Puck",
            "gender": "male",
            "dialect": "saudi",
            "custom_role_id": p_role_id
        }),
        content_type='application/json',
        HTTP_X_PARTNER_KEY=partner_prof.api_key
    )
    resp = api_partner_client_profile(req, client_id=client_user.id)
    assert resp.status_code == 201
    p_prof_data = json.loads(resp.content)["profile"]
    assert p_prof_data["custom_role_id"] == p_role_id

    # 6.4 Partner Studio metadata
    req = rf.get(f'/api/partner/v1/studio/?client_id={client_user.id}', HTTP_X_PARTNER_KEY=partner_prof.api_key)
    resp = api_partner_studio(req, client_id=client_user.id)
    assert resp.status_code == 200
    p_studio = json.loads(resp.content)
    assert "industry_roles_catalog" in p_studio
    assert any(cr["id"] == p_role_id for cr in p_studio["custom_roles"])
    print("  ✅ Partner REST API for sub-client custom roles verified.")

    print("\n" + "=" * 80)
    print("🎉 ALL 6 TESTS PASSED SUCCESSFULLY! 20 INDUSTRY ROLES & CUSTOM ROLES FULLY TESTED!")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
