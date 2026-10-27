# Dedicated Tier 2 WhatsApp Human Support Desk Design

**Date:** 2026-10-24
**Topic:** Dedicated WhatsApp Escalation Desk (`/desk/whatsapp/`)
**Target Directory:** `/root/voice-ai-telephony/test-calll-ai`

## 1. Intent & Purpose
Provide a clean, focused, distraction-free cockpit specifically tailored for human customer support agents handling conversations escalated from the WhatsApp AI bot. Replaces sequential round-robin routing with a real-time **Broadcast Ringing & Claim** model and enforces a **5-minute SLA first-response watchdog**.

## 2. Core Functional Requirements
- **R1. Shared Broadcast Ringing Pool:** Unclaimed escalations appear in a shared queue with audible chime on all active agents' browsers simultaneously.
- **R2. Atomic Chat Claim:** Clicking "استلام المحادثة" atomically claims the chat for the agent, removes it from other agents' screens, and stops their chimes.
- **R3. 3-Panel Dedicated Cockpit:**
  - Panel 1: Incoming Broadcast Ringing Queue.
  - Panel 2: Agent's Active Claimed Chats.
  - Panel 3: Live Chat Thread with AI Handoff Brief, 5-minute countdown, and Quick Composer.
- **R4. 5-Minute SLA Watchdog:** If an agent claims a chat but sends no message within 300 seconds (5 minutes), the chat is automatically unassigned and returned to the broadcast ringing pool with customer reassurance.
- **R5. Resolution & AI Handback:** One-click resolution closes the ticket, logs notes into `CustomerMemory`, and re-enables AI auto-reply.

## 3. Interfaces & Contracts

### Endpoints
1. `GET /desk/whatsapp/` -> Renders `whatsapp_desk.html` (login required).
2. `POST /api/crm/whatsapp/conversations/<path:phone_number>/claim/` ->
   - Atomically claims the conversation for `request.user`.
   - Returns `{"status": "success", "conversation_state": "ACTIVE_SUPPORT", "assigned_agent_id": user.id}`.
   - Publishes Centrifugo event `whatsapp_chat_claimed` to `tenant_{user_id}` and `user_{agent_id}`.
3. `POST /api/crm/whatsapp/conversations/<path:phone_number>/release/` ->
   - Releases chat back to pool (`assigned_agent_id = None`, `conversation_state = 'PENDING_AGENT_REPLY'`).
4. `POST /api/crm/whatsapp/conversations/<path:phone_number>/resolve/` ->
   - Existing endpoint resolving ticket and re-enabling AI.

## 4. UI Layout & Audio
- Uses Web Audio API for soft continuous chime ringing while items are present in the unclaimed queue.
- Modern Tailwind CSS styling matching the platform design tokens.
