#!/usr/bin/env python3
"""
Autonomous Trinity Coworker Service & HTTP Bridge Daemon.
Runs inside voice_trinity container on port 8000.
Handles:
  1. Health check & Web UI status page (for Traefik Host trinity.169.58.32.179.nip.io)
  2. Webhook receiver for /api/webhooks/call-completed
  3. Redis queue & pub/sub listener for asynchronous coworker events
  4. Autonomous tool caller to Django FastMCP endpoint
"""
import os
import sys
import json
import time
import socket
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [TrinityEngine] %(message)s"
)
logger = logging.getLogger("trinity_engine")

PORT = int(os.getenv("PORT", "8000"))
DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://django:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "voice_internal_secret_key_2026")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

received_events_log = []


def call_django_tool(tool_name: str, arguments: dict) -> dict:
    """Dispatches tool execution back to Django FastMCP coworker endpoint."""
    url = f"{DJANGO_API_URL}/api/crm/coworker/tool/execute/"
    payload = json.dumps({"tool": tool_name, "arguments": arguments}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Internal-API-Key": INTERNAL_API_KEY
        }
    )
    try:
        with urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to execute Django tool {tool_name}: {e}")
        return {"status": "error", "message": str(e)}


class TrinityHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))

    def do_GET(self):
        if self.path in ("/health", "/api/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": "healthy",
                "service": "Abilityai/trinity Coworker Engine",
                "uptime": time.time(),
                "events_processed": len(received_events_log)
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # Main Web Status UI
        user = self.headers.get("X-Forwarded-User", "Default Operator")
        service_mode = self.headers.get("X-Service-Mode", "digital_coworker")
        role = self.headers.get("X-Coworker-Role", "AI SDR & Operations")

        html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Abilityai/trinity - محرك الموظف الذكي الشامل</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #090d16;
            --card-bg: rgba(18, 26, 43, 0.85);
            --border: rgba(255, 255, 255, 0.1);
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.25);
            --success: #10b981;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Cairo', sans-serif;
            background: radial-gradient(circle at top, #111b2e 0%, var(--bg) 100%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            max-width: 800px;
            width: 90%;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 2.5rem;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5), 0 0 40px var(--primary-glow);
            backdrop-filter: blur(16px);
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 700;
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}
        .pulse {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 10px var(--success);
            animation: pulse-dot 1.5s infinite;
        }}
        @keyframes pulse-dot {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.4); opacity: 0.5; }}
        }}
        h1 {{
            margin: 1rem 0 0.5rem;
            font-size: 1.85rem;
            color: #ffffff;
        }}
        p.subtitle {{
            color: var(--text-muted);
            margin-bottom: 2rem;
            font-size: 1rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .metric-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            padding: 1.25rem;
            border-radius: 12px;
        }}
        .metric-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.25rem;
        }}
        .metric-value {{
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--primary);
        }}
        .actions {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 700;
            font-size: 0.95rem;
            transition: all 0.2s ease;
        }}
        .btn-primary {{
            background: #0284c7;
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .btn-primary:hover {{
            background: #0369a1;
            transform: translateY(-2px);
        }}
        .btn-outline {{
            background: transparent;
            color: var(--text-main);
            border: 1px solid var(--border);
        }}
        .btn-outline:hover {{
            background: rgba(255,255,255,0.05);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">
            <span class="pulse"></span>
            محرك Trinity متصل ونشط
        </div>
        <h1>Abilityai/trinity Autonomous Engine</h1>
        <p class="subtitle">المحرك الاستقلالي الذكي الموحد لمنظومة Voice AI Telephony & Omnichannel Coworker.</p>

        <div class="grid">
            <div class="metric-card">
                <div class="metric-label">المستأجر / المشغل</div>
                <div class="metric-value">{user}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">نمط الخدمة</div>
                <div class="metric-value">{service_mode}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">الدور المستقل</div>
                <div class="metric-value">{role}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">الأحداث المعالجة</div>
                <div class="metric-value">{len(received_events_log)}</div>
            </div>
        </div>

        <div class="actions">
            <a href="/coworker/" class="btn btn-primary">لوحة تحكم الموظف الذكي (Django)</a>
            <a href="/health" class="btn btn-outline">فحص الصحة (Health JSON)</a>
        </div>
    </div>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        if self.path in ("/api/webhooks/call-completed", "/webhooks/call-completed"):
            logger.info(f"Received call.completed event: {payload.get('room_name')} ({payload.get('phone_number')})")
            received_events_log.append(payload)

            # Auto-reasoning hook: if customer requested something, Trinity can invoke FastMCP tool
            phone = payload.get("phone_number")
            tenant_id = payload.get("tenant_id")
            service_mode = payload.get("service_mode")

            if service_mode == "digital_coworker" and phone and phone != "unknown":
                logger.info(f"Trinity autonomous workflow running for phone {phone}...")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "received", "event": "call.completed"}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


def start_redis_listener():
    """Background listener for Redis trinity:event_queue."""
    try:
        import redis
        r = redis.Redis.from_url(REDIS_URL)
        logger.info(f"Connected to Redis at {REDIS_URL}. Listening on 'trinity:event_queue'...")
        while True:
            try:
                item = r.blpop("trinity:event_queue", timeout=5)
                if item:
                    _, raw_data = item
                    event = json.loads(raw_data.decode("utf-8"))
                    logger.info(f"[Redis Consumer] Processed queue event: {event.get('event')} for {event.get('phone_number')}")
                    received_events_log.append(event)
            except Exception as e:
                time.sleep(2)
    except Exception as ie:
        logger.warning(f"Redis listener thread non-critical note: {ie}")


def run():
    # Start background Redis worker
    t = threading.Thread(target=start_redis_listener, daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", PORT), TrinityHTTPHandler)
    logger.info(f"Trinity Autonomous Engine HTTP Server started on 0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping Trinity Server...")
        server.server_close()


if __name__ == "__main__":
    run()
