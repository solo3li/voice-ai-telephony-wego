#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite for Newly Implemented Telephony Features:
1. RTP 1000+ Ports Range & Docker Host Network Mode (Zero proxy overhead)
2. WhatsApp Autonomous Follow-up migration to Inngest Jobs
3. Do Not Call (DNC) List with Model, Tenant/Global isolation, and Auto-Bypass
4. Prometheus & Grafana Monitoring Architecture with Live Metrics
"""

import sys
import os
import subprocess
import yaml
import json
import requests
import urllib3

sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

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

print("=" * 80)
print("  E2E TEST SUITE: TELEPHONY SCALING, INNGEST, DNC LIST & MONITORING")
print("=" * 80)

# ==============================================================================
# TEST 1: RTP 1000+ Ports & Host Networking Configuration
# ==============================================================================
print("\n>>> TEST 1: RTP 1000+ Port Range & Host Mode Architecture")

livekit_yaml_path = os.path.join(CURRENT_DIR, "livekit", "livekit.yaml")
with open(livekit_yaml_path, "r", encoding="utf-8") as f:
    lk_cfg = yaml.safe_load(f)

rtc_start = lk_cfg.get("rtc", {}).get("port_range_start")
rtc_end = lk_cfg.get("rtc", {}).get("port_range_end")
rtc_span = (rtc_end - rtc_start + 1) if (rtc_start and rtc_end) else 0

check("LiveKit WebRTC ports start at 50000", rtc_start == 50000, f"start={rtc_start}")
check("LiveKit WebRTC ports end at 51000 (1000+ ports)", rtc_end == 51000 and rtc_span >= 1000, f"ports count={rtc_span}")
check("LiveKit Prometheus metrics port enabled", lk_cfg.get("prometheus_port") == 6789, f"port={lk_cfg.get('prometheus_port')}")

sip_yaml_path = os.path.join(CURRENT_DIR, "livekit", "sip.yaml")
with open(sip_yaml_path, "r", encoding="utf-8") as f:
    sip_cfg = yaml.safe_load(f)

rtp_port_str = sip_cfg.get("rtp_port", "")
check("SIP RTP port range is 10000-11000 (1000+ ports)", rtp_port_str == "10000-11000", f"rtp_port={rtp_port_str}")

compose_path = os.path.join(CURRENT_DIR, "docker-compose.yml")
with open(compose_path, "r", encoding="utf-8") as f:
    compose_cfg = yaml.safe_load(f)

services = compose_cfg.get("services", {})
lk_service = services.get("livekit", {})
sip_service = services.get("sip", {})
redis_service = services.get("redis", {})

check("LiveKit container uses network_mode: host (Zero-proxy)", lk_service.get("network_mode") == "host")
check("SIP container uses network_mode: host (Zero-proxy)", sip_service.get("network_mode") == "host")
check("Redis exposes localhost port 6379 for host containers", "127.0.0.1:6379:6379" in redis_service.get("ports", []))

# ==============================================================================
# TEST 2: WhatsApp to Inngest Jobs Architecture
# ==============================================================================
print("\n>>> TEST 2: WhatsApp to Inngest Jobs Architecture (Code Verification)")

views_py_path = os.path.join(CURRENT_DIR, "django_app", "crm", "views.py")
with open(views_py_path, "r", encoding="utf-8") as f:
    views_code = f.read()

check("crm/views.py webhook uses dispatch_whatsapp_followup_job", "dispatch_whatsapp_followup_job" in views_code)
check("crm/views.py webhook eliminated threading.Thread for follow-ups", "threading.Thread(target=run_autonomous_followup" not in views_code)

inngest_py_path = os.path.join(CURRENT_DIR, "django_app", "crm", "inngest_jobs.py")
with open(inngest_py_path, "r", encoding="utf-8") as f:
    inngest_code = f.read()

check("crm/inngest_jobs.py registers fn_process_whatsapp_followup", "fn_process_whatsapp_followup" in inngest_code)
check("crm/inngest_jobs.py exports all_inngest_functions", "all_inngest_functions" in inngest_code)

# ==============================================================================
# TEST 3: Do Not Call (DNC) Database & Inngest Job Execution inside Container
# ==============================================================================
print("\n>>> TEST 3: Do Not Call (DNC) & Inngest Execution inside voice_django")

cmd = ["docker", "exec", "voice_django", "python", "manage.py", "shell", "-c", "exec(open('/app/test_dnc_and_inngest_e2e.py').read())"]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
sub_out = res.stdout

for line in sub_out.splitlines():
    if "[PASS]" in line or "[FAIL]" in line:
        print(" " + line)

check("Django DNC & Inngest internal execution exited with status 0", res.returncode == 0, f"exit={res.returncode}")

# ==============================================================================
# TEST 4: Prometheus & Grafana Monitoring Architecture
# ==============================================================================
print("\n>>> TEST 4: Prometheus & Grafana Monitoring Architecture")

# 4.1 Live Prometheus Metrics scraping from Django
try:
    m_resp = requests.get("http://127.0.0.1:8000/api/telephony/metrics/", timeout=5)
    check("Django /api/telephony/metrics/ returns HTTP 200", m_resp.status_code == 200)
    m_text = m_resp.text
    check("Metrics include telephony_active_calls", "telephony_active_calls" in m_text)
    check("Metrics include telephony_calls_total", "telephony_calls_total" in m_text)
    check("Metrics include telephony_duration_seconds_total", "telephony_duration_seconds_total" in m_text)
    check("Metrics include telephony_dnc_entries_total", "telephony_dnc_entries_total" in m_text)
    check("Metrics include telephony_campaigns_total", "telephony_campaigns_total" in m_text)
    check("Metrics include telephony_omnichannel_messages_total", "telephony_omnichannel_messages_total" in m_text)
except Exception as e:
    check("Django metrics endpoint accessible", False, str(e))

# 4.2 Prometheus Health and Target Scrapes
try:
    p_health = requests.get("http://127.0.0.1:9090/-/healthy", timeout=5)
    check("Prometheus server is healthy on port 9090", p_health.status_code == 200)

    p_targets = requests.get("http://127.0.0.1:9090/api/v1/targets", timeout=5).json()
    active_targets = p_targets.get("data", {}).get("activeTargets", [])
    up_targets = [t for t in active_targets if t.get("health") == "up"]
    check("Prometheus actively scrapes targets with status UP", len(up_targets) >= 2, f"active up targets: {len(up_targets)}")
except Exception as e:
    check("Prometheus server accessible", False, str(e))

# 4.3 Grafana Health and Provisioned Telephony Dashboard
try:
    g_health = requests.get("http://127.0.0.1:3000/api/health", timeout=5).json()
    check("Grafana server is healthy on port 3000", g_health.get("database") == "ok")

    dash_resp = requests.get("http://127.0.0.1:3000/api/dashboards/uid/telephony-voice-ai-main", auth=("admin", "admin"), timeout=5)
    check("Grafana dashboard 'Telephony & Voice AI' is provisioned and loaded", dash_resp.status_code == 200)
    dash_json = dash_resp.json()
    panels = dash_json.get("dashboard", {}).get("panels", [])
    check("Grafana dashboard contains all monitoring panels", len(panels) >= 5, f"total panels: {len(panels)}")
except Exception as e:
    check("Grafana server accessible", False, str(e))

# 4.4 Provisioning Files Validation
prom_yml = os.path.join(CURRENT_DIR, "prometheus", "prometheus.yml")
check("prometheus.yml config exists", os.path.exists(prom_yml))

grafana_ds = os.path.join(CURRENT_DIR, "grafana", "provisioning", "datasources", "datasource.yml")
check("grafana datasource.yml exists", os.path.exists(grafana_ds))

grafana_dash_json = os.path.join(CURRENT_DIR, "grafana", "dashboards", "telephony_dashboard.json")
check("grafana telephony_dashboard.json exists", os.path.exists(grafana_dash_json))

print("\n" + "=" * 80)
print(f"  ALL TESTS SUMMARY: {passed} PASSED, {failed} FAILED (TOTAL: {passed + failed})")
print("=" * 80)

if failed > 0:
    sys.exit(1)
sys.exit(0)
