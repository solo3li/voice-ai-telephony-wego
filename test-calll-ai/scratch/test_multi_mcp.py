import sys, requests, urllib3, json
sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings()

s = requests.Session()
s.verify = False

print('=' * 65)
print('STARTING MULTI-MCP ARCHITECTURE & CRUD TESTS')
print('=' * 65)

# 1. Login
login_page = s.get('https://localhost/login/')
csrftoken = s.cookies.get('csrftoken', '')
s.post('https://localhost/login/', data={'username': 'admin', 'password': 'admin123456', 'csrfmiddlewaretoken': csrftoken}, headers={'Referer': 'https://localhost/login/'})

# 2. Get initial MCP servers
res = s.get('https://localhost/api/agents/mcp/')
assert res.status_code == 200, f'Failed get_mcp: {res.status_code}'
data = res.json()
print('[PASS] Initial GET /api/agents/mcp/ returned 200 OK')
assert 'servers' in data, 'Missing servers list'
initial_count = len(data['servers'])
server_1 = data['servers'][0]
server_1_id = server_1['id']
print(f" -> Found {initial_count} initial server(s). Primary server ID: {server_1_id} ({server_1['name']})")

# 3. Add 2nd MCP server
new_server_payload = {
    'name': 'خادم الخدمات الإضافية التجريبي',
    'server_url': 'http://mock-store:8002/sse',
    'auth_token': '',
    'is_active': True
}
res_add = s.post('https://localhost/api/agents/mcp/save/', json=new_server_payload, headers={'X-CSRFToken': s.cookies.get('csrftoken')})
assert res_add.status_code == 200, f'Add server failed: {res_add.status_code} - {res_add.text}'
add_data = res_add.json()
server_2 = add_data['server']
server_2_id = server_2['id']
assert server_2_id != server_1_id, 'Server 2 should have unique ID'
print(f'[PASS] Successfully created Server 2 with ID: {server_2_id}')

# 4. Verify 2 servers exist
res_list = s.get('https://localhost/api/agents/mcp/')
data_list = res_list.json()
assert len(data_list['servers']) == initial_count + 1, 'Server count should have incremented'
print(f"[PASS] Listing confirms {len(data_list['servers'])} servers present in user account")

# 5. Test Toggle Server 2
res_toggle = s.post('https://localhost/api/agents/mcp/toggle/', json={'id': server_2_id}, headers={'X-CSRFToken': s.cookies.get('csrftoken')})
assert res_toggle.status_code == 200
assert res_toggle.json()['is_active'] == False, 'Server 2 should now be disabled'
print('[PASS] Toggled Server 2 to inactive. Server 1 remains untouched')

# Verify Server 1 is still active
res_chk = s.get('https://localhost/api/agents/mcp/')
for s_obj in res_chk.json()['servers']:
    if s_obj['id'] == server_1_id:
        assert s_obj['is_active'] == True, 'Server 1 must stay active'
    elif s_obj['id'] == server_2_id:
        assert s_obj['is_active'] == False, 'Server 2 must be inactive'
print('[PASS] Independent state verification passed (Server 1 Active, Server 2 Inactive)')

# Re-activate Server 2
s.post('https://localhost/api/agents/mcp/toggle/', json={'id': server_2_id}, headers={'X-CSRFToken': s.cookies.get('csrftoken')})

# 6. Test Internal Bootstrap API
bootstrap_res = s.post('https://localhost/api/agents/internal/bootstrap/', json={'user_id': 10}, headers={'X-Internal-API-Key': 'development-secret-key-123'})
assert bootstrap_res.status_code == 200, f'Bootstrap failed: {bootstrap_res.text}'
b_data = bootstrap_res.json()
assert 'mcp_servers' in b_data
b_server_ids = [s_item['id'] for s_item in b_data['mcp_servers']]
assert server_1_id in b_server_ids and server_2_id in b_server_ids, 'Both active servers must be passed to voice agent'
print(f"[PASS] Internal agent bootstrap received {len(b_data['mcp_servers'])} active MCP servers")

# 7. Edit Server 2
edit_payload = {
    'id': server_2_id,
    'name': 'خادم الأدوات والخدمات المحدث',
    'server_url': 'http://mock-store:8002/sse',
    'auth_token': 'secret123',
    'is_active': True
}
res_edit = s.post('https://localhost/api/agents/mcp/save/', json=edit_payload, headers={'X-CSRFToken': s.cookies.get('csrftoken')})
assert res_edit.status_code == 200
edited_server = res_edit.json()['server']
assert edited_server['name'] == 'خادم الأدوات والخدمات المحدث'
assert edited_server['auth_token'] == 'secret123'
print('[PASS] Successfully edited Server 2 properties')

# 8. Delete Server 2
res_del = s.post('https://localhost/api/agents/mcp/delete/', json={'id': server_2_id}, headers={'X-CSRFToken': s.cookies.get('csrftoken')})
assert res_del.status_code == 200
res_after_del = s.get('https://localhost/api/agents/mcp/')
remaining_ids = [s_item['id'] for s_item in res_after_del.json()['servers']]
assert server_2_id not in remaining_ids, 'Server 2 should be deleted'
assert server_1_id in remaining_ids, 'Server 1 should still exist'
print('[PASS] Specific server deletion verified (Server 2 deleted, Server 1 intact)')

# 9. Verify UI Elements
ui_html = s.get('https://localhost/').text
assert 'id="mcp-servers-grid"' in ui_html
assert 'id="btn-add-mcp-server"' in ui_html
assert 'modal-mcp-id' in ui_html
assert 'loadMcpServers' in ui_html
print('[PASS] Frontend UI elements for Multi-MCP grid, stats, and modal verified')

print('=' * 65)
print('ALL MULTI-MCP BACKEND, AGENT BOOTSTRAP, AND UI TESTS PASSED 100%!')
print('=' * 65)
