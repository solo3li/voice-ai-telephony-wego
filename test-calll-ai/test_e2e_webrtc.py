import json
import sys
import requests
import urllib3
sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://app.169.58.32.179.nip.io"
session = requests.Session()
session.verify = True

API_KEY = "voice-internal-secret-token-key-12345"
internal_headers = {
    "X-Internal-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def run_tests():
    print("=" * 65)
    print("RUNNING END-TO-END VERIFICATION: MODULAR APPS & DECOUPLED AGENT")
    print("=" * 65)

    # 1. Login Ahmed (101) via Call Center App
    print("\n[1] Testing Employee Login (/api/call-center/auth/login/ - Ahmed 101)...")
    res = session.post(f"{BASE_URL}/api/call-center/auth/login/", json={
        "identifier": "101",
        "password": "password123"
    })
    assert res.status_code == 200, f"Login failed: {res.status_code} {res.text}"
    data = res.json()
    assert data["status"] == "success"
    token = data["token"]
    emp = data["employee"]
    centrifugo = data["centrifugo"]
    print(f" -> Logged in successfully as: {emp['display_name']} (Ext: {emp['extension']})")
    print(f" -> Centrifugo Token: {centrifugo['token'][:25]}...")
    print(f" -> Centrifugo WS URL: {centrifugo['ws_url']}")
    print(f" -> Employee Centrifugo Channel: {centrifugo['channel']}")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Employee Me
    print("\n[2] Testing /api/call-center/auth/me/...")
    res = session.get(f"{BASE_URL}/api/call-center/auth/me/", headers=headers)
    assert res.status_code == 200
    me_data = res.json()
    assert me_data["employee"]["extension"] == "101"
    print(f" -> Verified session for: {me_data['employee']['display_name']}")

    # 3. Update Status
    print("\n[3] Testing Status Update (/api/call-center/employees/status/)...")
    res = session.post(f"{BASE_URL}/api/call-center/employees/status/", json={"status": "break"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["employee"]["status"] == "break"
    print(" -> Status updated to 'break'")

    res = session.post(f"{BASE_URL}/api/call-center/employees/status/", json={"status": "ready"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["employee"]["status"] == "ready"
    print(" -> Status updated to 'ready'")

    # 4. List Directory
    print("\n[4] Testing Directory Listing (/api/call-center/employees/)...")
    res = session.get(f"{BASE_URL}/api/call-center/employees/", headers=headers)
    assert res.status_code == 200
    dir_data = res.json()
    employees = dir_data["employees"]
    queues = dir_data["queues"]
    print(f" -> Found {len(employees)} other employees in directory:")
    for e in employees:
        print(f"    - [{e['extension']}] {e['display_name']} ({e['department']}) - {e['status']}")
    print(f" -> Found {len(queues)} call queues:")
    for q in queues:
        print(f"    - [Queue {q['code']}] {q['name']} ({len(q['members'])} members)")

    # 5. Internal Dialing (101 -> 103 Mohamed)
    print("\n[5] Testing Internal WebRTC Dialing (/api/call-center/calls/dial/ - 101 -> 103 Mohamed)...")
    res = session.post(f"{BASE_URL}/api/call-center/calls/dial/", json={"target": "103"}, headers=headers)
    assert res.status_code == 200, f"Dial failed: {res.status_code} {res.text}"
    dial_data = res.json()
    assert dial_data["status"] == "success"
    assert dial_data["call_type"] == "direct_internal"
    assert "livekit_token" in dial_data
    room_name = dial_data["room_name"]
    print(f" -> Room created: {room_name}")
    print(f" -> LiveKit URL: {dial_data['livekit_url']}")
    print(f" -> Callee target: {dial_data['target_name']} (Ext: {dial_data['target_number']})")
    print(f" -> Caller LiveKit JWT generated successfully ({len(dial_data['livekit_token'])} chars)")

    # 6. Callee Joining (103 Mohamed gets token)
    print("\n[6] Testing Callee Answering (/api/call-center/calls/token/)...")
    mohamed_res = session.post(f"{BASE_URL}/api/call-center/auth/login/", json={
        "identifier": "mohamed",
        "password": "password123"
    })
    mohamed_token = mohamed_res.json()["token"]
    mohamed_headers = {"Authorization": f"Bearer {mohamed_token}"}

    res = session.post(f"{BASE_URL}/api/call-center/calls/token/", json={"room_name": room_name}, headers=mohamed_headers)
    assert res.status_code == 200
    callee_data = res.json()
    assert "livekit_token" in callee_data
    print(f" -> Mohamed successfully acquired WebRTC join token for room '{room_name}'")

    # 7. Hangup Call
    print("\n[7] Testing Call Hangup (/api/call-center/calls/hangup/)...")
    res = session.post(f"{BASE_URL}/api/call-center/calls/hangup/", json={
        "room_name": room_name,
        "target_employee_id": 3
    }, headers=headers)
    assert res.status_code == 200
    print(" -> Call hangup signaled cleanly to room and Centrifugo")

    # 8. Queue Dialing (101 -> 200 Sales Queue)
    print("\n[8] Testing Queue WebRTC Dialing (/api/call-center/calls/dial/ - 101 -> 200 Sales Queue)...")
    res = session.post(f"{BASE_URL}/api/call-center/calls/dial/", json={"target": "200"}, headers=headers)
    assert res.status_code == 200
    q_dial = res.json()
    assert q_dial["call_type"] == "queue"
    print(f" -> Queue call successfully initiated for: {q_dial['target_name']}")

    # 9. Internal Agent Bootstrap API
    print("\n[9] Testing Internal Agent Bootstrap API (/api/agents/internal/bootstrap/)...")
    b_res = session.post(f"{BASE_URL}/api/agents/internal/bootstrap/", json={"user_id": 8}, headers=internal_headers)
    assert b_res.status_code == 200
    b_data = b_res.json()
    assert b_data["status"] == "success"
    assert "profile" in b_data
    assert "mcp_servers" in b_data
    assert "customer_memory" in b_data
    print(f" -> Agent Bootstrap succeeded: loaded profile '{b_data['profile']['name']}', MCP servers, and memory")

    # 10. Internal Knowledge RAG API
    print("\n[10] Testing Internal Knowledge RAG API (/api/knowledge/internal/rag/)...")
    rag_res = session.post(f"{BASE_URL}/api/knowledge/internal/rag/", json={
        "user_id": 8,
        "query": "ما هي المنتجات والخدمات؟",
        "top_k": 3
    }, headers=internal_headers)
    assert rag_res.status_code == 200
    rag_data = rag_res.json()
    assert rag_data["status"] == "success"
    print(f" -> Knowledge RAG API succeeded (text len: {len(rag_data['text'])})")

    # 11. Internal CRM Complete Call API
    print("\n[11] Testing Internal CRM Complete Call API (/api/crm/internal/complete-call/)...")
    crm_res = session.post(f"{BASE_URL}/api/crm/internal/complete-call/", json={
        "user_id": 8,
        "room_name": "e2e_verification_room_final",
        "started_at": 1700000000.0,
        "duration_seconds": 60,
        "direction": "inbound",
        "destination_phone": "+201012345678",
        "call_goal": "اختبار التحقق النهائي",
        "transcript_text": "العميل: هل كل شيء يعمل؟\nالمساعد: نعم، النظام يعمل بأعلى كفاءة ومعمارية مستقلة.",
        "summary": "مكالمة ناجحة للتحقق من تكامل جميع التطبيقات والخدمات.",
        "permanent_profile": {"customer_name": "محمد", "phone": "+201012345678"}
    }, headers=internal_headers)
    assert crm_res.status_code == 200
    crm_data = crm_res.json()
    assert crm_data["status"] == "success"
    print(f" -> CRM Complete Call succeeded: Session #{crm_data['session_id']}, Total calls: {crm_data['total_calls_count']}")

    print("\n" + "=" * 65)
    print("ALL 11 END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
