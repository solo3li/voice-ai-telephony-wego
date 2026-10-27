# WhatsApp Dedicated Support Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated Tier 2 WhatsApp Human Support Desk (`/desk/whatsapp/`) with shared broadcast ringing, atomic chat claiming, 5-minute SLA watchdog, and one-click AI handback.

**Architecture:** Standalone Django template route with a 3-panel layout (Incoming Broadcast Queue, Claimed Chats, Live Cockpit) integrated with Centrifugo WebSocket for real-time ring alerts and atomic claim/release endpoints.

**Tech Stack:** Python 3.11, Django 5, PostgreSQL, Centrifugo, Web Audio API, Tailwind CSS.

**Spec:** `docs/superpowers/specs/2026-10-24-whatsapp-support-desk-design.md`

## Global Constraints
- Single tenant / multi-tenant isolation: strictly scope all operations to `request.user`.
- No round-robin: broadcast ringing for all available agents; first to claim takes the chat.
- SLA watchdog: 300 seconds (5 minutes) maximum first response time before auto-return to pool.

---

### Task 1: Backend Claim & Release Endpoints and Dispatcher Update
**Files:**
- Modify: `django_app/crm/services/whatsapp_dispatcher.py`
- Modify: `django_app/crm/views.py`
- Modify: `django_app/crm/urls.py`
- Create: `django_app/test_whatsapp_support_desk_claim_e2e.py`

- [x] **Step 1: Write E2E test for claim, release, and 300s SLA watchdog**
- [x] **Step 2: Run test to verify it fails before implementation**
- [x] **Step 3: Implement `api_whatsapp_conversation_claim` and `api_whatsapp_conversation_release` in `crm/views.py`**
- [x] **Step 4: Update `whatsapp_dispatcher.py` default SLA to 300 seconds (5 minutes)**
- [x] **Step 5: Run tests to verify they pass**

### Task 2: Dedicated Support Desk View and 3-Panel HTML Template
**Files:**
- Create: `django_app/voice_assistant/templates/voice_assistant/pages/whatsapp_desk.html`
- Modify: `django_app/voice_assistant/views.py`
- Modify: `django_app/voice_assistant/urls.py` (or root `config/urls.py`)

- [x] **Step 1: Create `support_whatsapp_desk` view with login check in `voice_assistant/views.py`**
- [x] **Step 2: Mount URL `path('desk/whatsapp/', views.support_whatsapp_desk, name='support_whatsapp_desk')`**
- [x] **Step 3: Implement `whatsapp_desk.html` 3-panel cockpit with Web Audio chime, broadcast queue, claimed chats, and AI brief**
- [x] **Step 4: Verify template renders with HTTP 200 via test**

### Task 3: Full End-to-End Suite Run & Hardening
- [x] **Step 1: Run comprehensive tests in `voice_django`**
- [x] **Step 2: Verify all assertions pass cleanly**
