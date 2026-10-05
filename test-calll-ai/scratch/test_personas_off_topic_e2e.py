import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from agents.models import AgentProfile

User = get_user_model()
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
print(f"Testing with user: {user.username}")

client = Client()
client.force_login(user)

# 1. Test /personas/ page rendering
print("\n--- [TEST 1] Testing /personas/ page HTML rendering ---")
resp = client.get('/personas/')
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
content = resp.content.decode('utf-8')
assert 'id="field-off-topic"' in content, "Missing field-off-topic in /personas/ page!"
assert 'id="new-prof-off-topic"' in content, "Missing new-prof-off-topic in /personas/ page!"
print("[PASS] /personas/ HTML contains field-off-topic and new-prof-off-topic")

# 2. Test /static/js/personas.js content
print("\n--- [TEST 2] Testing static personas.js content ---")
resp_js = client.get('/static/js/personas.js')
assert resp_js.status_code == 200, f"Expected 200, got {resp_js.status_code}"
js_content = b''.join(resp_js.streaming_content).decode('utf-8')
assert 'fieldOffTopic' in js_content, "Missing fieldOffTopic in personas.js"
assert 'newProfOffTopic' in js_content, "Missing newProfOffTopic in personas.js"
assert 'off_topic_response' in js_content, "Missing off_topic_response in personas.js"
print("[PASS] personas.js contains off_topic_response bindings, cards preview, and payloads")

# 3. Test API: Create profile with off_topic_response
print("\n--- [TEST 3] Testing /api/agents/profiles/create/ with off_topic_response ---")
create_payload = {
    "name": "بروفايل تجريبي للاختبار",
    "voice_name": "Aoede",
    "gender": "female",
    "language": "arabic",
    "dialect": "egyptian",
    "persona_role": "مستشار مبيعات",
    "speaking_style": "ودود",
    "verbosity": "balanced",
    "welcome_message": "أهلاً بك",
    "is_welcome_message_enabled": True,
    "off_topic_response": "أنا متخصص في المتجر فقط، تفضل بسؤالك عن منتجاتنا.",
    "is_active": False
}
resp_create = client.post(
    '/api/agents/profiles/create/',
    data=json.dumps(create_payload),
    content_type='application/json'
)
assert resp_create.status_code == 201, f"Expected 201, got {resp_create.status_code}: {resp_create.content}"
create_data = resp_create.json()
profile_id = create_data['profile']['id']
assert create_data['profile']['off_topic_response'] == create_payload['off_topic_response'], "off_topic_response not in create response!"

# Verify from database
db_profile = AgentProfile.objects.get(id=profile_id)
assert db_profile.off_topic_response == create_payload['off_topic_response'], "off_topic_response not persisted in DB on create!"
print(f"[PASS] Successfully created profile {profile_id} with off_topic_response: '{db_profile.off_topic_response}'")

# 4. Test API: Update profile with off_topic_response
print("\n--- [TEST 4] Testing /api/agents/profiles/<id>/update/ with off_topic_response ---")
update_payload = {
    "off_topic_response": "رسالة محدثة: تخصصي محدد بالدعم الفني والمبيعات فقط."
}
resp_update = client.post(
    f'/api/agents/profiles/{profile_id}/update/',
    data=json.dumps(update_payload),
    content_type='application/json'
)
assert resp_update.status_code == 200, f"Expected 200, got {resp_update.status_code}: {resp_update.content}"
update_data = resp_update.json()
assert update_data['profile']['off_topic_response'] == update_payload['off_topic_response'], "off_topic_response not in update response!"

# Verify from database
db_profile.refresh_from_db()
assert db_profile.off_topic_response == update_payload['off_topic_response'], "off_topic_response not updated in DB!"
print(f"[PASS] Successfully updated profile {profile_id} with new off_topic_response: '{db_profile.off_topic_response}'")

# 5. Test API: List profiles returns off_topic_response
print("\n--- [TEST 5] Testing /api/agents/profiles/ listing ---")
resp_list = client.get('/api/agents/profiles/')
assert resp_list.status_code == 200
list_data = resp_list.json()
found = any(p['id'] == profile_id and p['off_topic_response'] == update_payload['off_topic_response'] for p in list_data['profiles'])
assert found, "Created profile not found with correct off_topic_response in list_profiles!"
print("[PASS] Profile list includes profile with off_topic_response")

# Clean up
db_profile.delete()
print("\n[ALL TESTS PASSED SUCCESSFULLY!]")
