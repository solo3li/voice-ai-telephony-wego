import os
import re
import json
import logging
import inngest
from datetime import datetime, timezone, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

from common.inngest_client import inngest_client
from common.centrifugo import publish_to_centrifugo

def broadcast_campaign_update(campaign_id: int, event_type: str, data: dict):
    """Broadcast real-time campaign update via Centrifugo if configured."""
    try:
        publish_to_centrifugo(
            f"campaign:{campaign_id}",
            {
                "type": event_type,
                "campaign_id": campaign_id,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        logger.debug(f"Centrifugo broadcast skipped or failed: {e}")


def _initiate_contact_call_sync(contact_id: int) -> dict:
    """Synchronous Django ORM and LiveKit execution for a single contact call."""
    from crm.models import CampaignContact
    from telephony.services import initiate_outbound_call

    try:
        contact = CampaignContact.objects.select_related('campaign', 'campaign__user').get(id=contact_id)
        campaign = contact.campaign

        if campaign.status in ['paused', 'completed']:
            logger.info(f"Campaign {campaign.id} is {campaign.status}. Skipping contact {contact.id}")
            return {"status": "skipped", "reason": f"Campaign is {campaign.status}"}

        # Check DNC (Do Not Call) list
        from crm.models import DoNotCallEntry
        if DoNotCallEntry.is_blacklisted(campaign.user_id, contact.phone_number):
            logger.info(f"[DNC] Contact {contact.id} ({contact.phone_number}) is in DNC list. Skipping call.")
            contact.call_status = 'skipped_dnc'
            contact.interest_level = 'cold'
            contact.call_summary = 'تم تخطي المكالمة لأن الرقم مسجل في قائمة عدم الاتصال (DNC).'
            contact.save(update_fields=['call_status', 'interest_level', 'call_summary', 'updated_at'])
            campaign.update_metrics()
            broadcast_campaign_update(campaign.id, "contact_skipped_dnc", {
                "contact_id": contact.id,
                "phone": contact.phone_number,
                "name": contact.customer_name,
                "reason": "DNC"
            })
            return {"status": "skipped_dnc", "reason": "Phone number is in DNC list"}

        contact.call_status = 'in_progress'
        contact.last_attempt_at = datetime.now(timezone.utc)
        contact.save(update_fields=['call_status', 'last_attempt_at', 'updated_at'])

        # Build tailored call prompt with contact attributes
        custom_attrs_str = ""
        if contact.attributes:
            items = [f"- {k}: {v}" for k, v in contact.attributes.items()]
            custom_attrs_str = "\nبيانات إضافية عن العميل:\n" + "\n".join(items)

        full_prompt = (
            f"{campaign.call_prompt or 'أنت ممثل خدمة عملاء ومبيعات لبق واحترافي.'}\n\n"
            f"بيانات العميل المستهدف بالمكالمة:\n"
            f"- الاسم: {contact.customer_name}\n"
            f"- الهاتف: {contact.phone_number}"
            f"{custom_attrs_str}\n\n"
            f"تعليمات هامة: رحّب بالعميل باسمه وخاطبه باحترام، وتحدث معه بعفوية باللهجة المناسبة، وحقق هدف المكالمة بسلاسة."
        )

        # Trigger outbound dial
        dial_res = initiate_outbound_call(
            user=campaign.user,
            phone_number=contact.phone_number,
            call_goal=full_prompt,
            profile_id=campaign.agent_profile_id,
            gateway_type=campaign.gateway_type,
            gateway_id=campaign.gateway_id
        )

        if dial_res.get("status") == "success":
            room_name = dial_res.get("room_name")
            sess_id = dial_res.get("session_id")
            if sess_id:
                contact.call_session_id = sess_id
                contact.save(update_fields=['call_session', 'updated_at'])
            broadcast_campaign_update(campaign.id, "contact_calling", {
                "contact_id": contact.id,
                "phone": contact.phone_number,
                "name": contact.customer_name,
                "room_name": room_name
            })
            return {"status": "success", "room_name": room_name, "session_id": sess_id, "dial_data": dial_res}
        else:
            if dial_res.get("code") == "no_outbound_gateway":
                # DO NOT mark as failed or waste retries when there is no gateway!
                contact.call_status = 'pending'
                contact.interest_level = 'uncontacted'
                contact.call_summary = ''
                contact.save(update_fields=['call_status', 'interest_level', 'call_summary', 'updated_at'])
                campaign.status = 'paused'
                campaign.save(update_fields=['status', 'updated_at'])
                campaign.update_metrics()
                broadcast_campaign_update(campaign.id, "campaign_paused_no_gateway", {
                    "message": "تم إيقاف الحملة مؤقتاً لعدم وجود مسار اتصال صادر مفعل."
                })
                return {"status": "aborted", "code": "no_outbound_gateway", "message": dial_res.get("message")}
            else:
                contact.call_status = 'failed'
                contact.interest_level = 'unreached'
                contact.call_summary = dial_res.get("message") or "فشل الاتصال بالمزود الخارجي"
                contact.save(update_fields=['call_status', 'interest_level', 'call_summary', 'updated_at'])
                schedule_contact_retry(contact.id)
                if campaign.channel == 'hybrid' and contact.whatsapp_status in ['pending', 'failed']:
                    from crm.services.campaign_whatsapp import send_campaign_contact_whatsapp
                    try:
                        send_campaign_contact_whatsapp(contact.id)
                    except Exception as hw_err:
                        logger.warning(f"Error dispatching hybrid WhatsApp on dial failure: {hw_err}")
                return {"status": "error", "message": dial_res.get("message")}
    except Exception as err:
        logger.exception(f"Error in _initiate_contact_call_sync for contact {contact_id}")
        return {"status": "error", "message": str(err)}


def schedule_contact_retry(contact_id: int) -> bool:
    """
    Checks if a contact qualifies for durable retry and dispatches 'campaign/contact.retry'.
    Called when a call is unanswered, busy, or failed.
    """
    from crm.models import CampaignContact
    try:
        contact = CampaignContact.objects.select_related('campaign').filter(id=contact_id).first()
        if not contact:
            return False
        campaign = contact.campaign

        if campaign.status not in ['running', 'draft']:
            logger.info(f"Campaign #{campaign.id} status is '{campaign.status}'. Skipping retry for contact #{contact.id}.")
            return False

        if contact.call_status == 'answered':
            logger.info(f"Contact #{contact.id} is answered. Skipping retry.")
            return False

        if contact.retries_count >= campaign.max_retries:
            logger.info(f"Contact #{contact.id} exhausted maximum retries ({contact.retries_count}/{campaign.max_retries}).")
            campaign.update_metrics()
            return False

        contact.retries_count += 1
        delay_mins = max(1, campaign.retry_delay_minutes)
        contact.call_summary = (
            f"لم يرد العميل (المحاولة {contact.retries_count}/{campaign.max_retries}). "
            f"مجدول لإعادة الاتصال تلقائياً بعد {delay_mins} دقيقة."
        )
        contact.save(update_fields=['retries_count', 'call_summary', 'updated_at'])
        campaign.update_metrics()

        from asgiref.sync import async_to_sync
        async_to_sync(inngest_client.send)([
            inngest.Event(
                name="campaign/contact.retry",
                data={
                    "contact_id": contact.id,
                    "campaign_id": campaign.id,
                    "user_id": campaign.user_id,
                    "delay_mins": delay_mins,
                    "attempt": contact.retries_count
                }
            )
        ])

        broadcast_campaign_update(campaign.id, "contact_retry_scheduled", {
            **contact.to_dict(),
            "retry_in_minutes": delay_mins,
            "next_attempt": contact.retries_count
        })
        logger.info(f"Scheduled retry for contact #{contact.id} ({contact.phone_number}) in {delay_mins} minutes (Attempt {contact.retries_count}/{campaign.max_retries}).")
        return True
    except Exception as e:
        logger.exception(f"Error in schedule_contact_retry for contact {contact_id}: {e}")
        return False


def _check_and_mark_retry_sync(contact_id: int) -> dict:
    """Synchronous check to determine if a contact call qualifies for durable retry."""
    return {"should_retry": schedule_contact_retry(contact_id)}


def _queue_contacts_sync(campaign_id: int) -> dict:
    """Synchronous query to gather pending contacts and user limit for a campaign."""
    from crm.models import OutboundCampaign, UserCampaignLimit
    campaign = OutboundCampaign.objects.get(id=campaign_id)
    campaign.status = 'running'
    campaign.save(update_fields=['status', 'updated_at'])

    limit = UserCampaignLimit.get_limit_for_user(campaign.user)

    if campaign.channel == 'whatsapp':
        pending_contacts = list(campaign.contacts.filter(whatsapp_status='pending').values_list('id', flat=True))
        event_name = "campaign/contact.whatsapp"
    else:
        pending_contacts = list(campaign.contacts.filter(call_status='pending').values_list('id', flat=True))
        event_name = "campaign/contact.dial"

    logger.info(f"Queuing {len(pending_contacts)} contacts for {campaign.channel} campaign {campaign.id} (user concurrency limit: {limit})")

    events_data = [
        {
            "event_name": event_name,
            "data": {
                "campaign_id": campaign.id,
                "contact_id": cid,
                "user_id": campaign.user_id,
                "concurrency_limit": limit
            }
        }
        for cid in pending_contacts
    ]
    return {
        "events_data": events_data,
        "concurrency_limit": limit,
        "queued_count": len(pending_contacts),
        "campaign_id": campaign.id,
        "channel": campaign.channel
    }


@inngest_client.create_function(
    fn_id="dial-campaign-contact",
    trigger=inngest.TriggerEvent(event="campaign/contact.dial"),
    concurrency=[inngest.Concurrency(limit=10, key="event.data.user_id")],
)
async def fn_dial_campaign_contact(ctx: inngest.Context) -> dict:
    """
    Inngest background job to execute an outbound call for a campaign contact.
    Handles concurrency throttling, LiveKit call dispatch, and lead scoring.
    """
    event_data = ctx.event.data
    contact_id = event_data.get("contact_id")

    async def step_initiate_call():
        return await sync_to_async(_initiate_contact_call_sync, thread_sensitive=True)(contact_id)

    call_result = await ctx.step.run("initiate-call", step_initiate_call)

    # If call was aborted due to missing outbound gateway, exit immediately without retries
    if call_result.get("code") == "no_outbound_gateway" or call_result.get("status") == "aborted":
        return {"status": "aborted", "reason": "no_outbound_gateway", "contact_id": contact_id}

    return {"status": "dispatched", "contact_id": contact_id, "call_result": call_result}


@inngest_client.create_function(
    fn_id="send-campaign-whatsapp",
    trigger=inngest.TriggerEvent(event="campaign/contact.whatsapp"),
    concurrency=[inngest.Concurrency(limit=5, key="event.data.user_id")],
)
async def fn_send_campaign_whatsapp(ctx: inngest.Context) -> dict:
    """
    Inngest background job to formulate and send a personalized WhatsApp message
    for a campaign contact via Evolution API and Gemini.
    """
    event_data = ctx.event.data
    contact_id = event_data.get("contact_id")

    # Anti-ban / Rate-limit pacing delay (1.2 seconds)
    await ctx.step.sleep("pacing-delay", timedelta(seconds=1.2))

    async def step_send_whatsapp():
        from crm.services.campaign_whatsapp import send_campaign_contact_whatsapp
        return await sync_to_async(send_campaign_contact_whatsapp, thread_sensitive=True)(contact_id)

    res = await ctx.step.run("send-whatsapp", step_send_whatsapp)
    return {"status": "completed", "contact_id": contact_id, "result": res}


@inngest_client.create_function(
    fn_id="retry-campaign-contact",
    trigger=inngest.TriggerEvent(event="campaign/contact.retry"),
)
async def fn_retry_campaign_contact(ctx: inngest.Context) -> dict:
    """
    Durable retry handler: sleeps for the configured retry_delay_minutes,
    re-verifies contact status, and dispatches a new dial event if eligible.
    """
    event_data = ctx.event.data
    contact_id = event_data.get("contact_id")
    delay_mins = int(event_data.get("delay_mins", 1))

    logger.info(f"[RETRY] Durable sleep initiated for contact #{contact_id}: {delay_mins} minutes.")
    await ctx.step.sleep("retry-delay", timedelta(minutes=delay_mins))

    def _prepare_retry_sync():
        from crm.models import CampaignContact, UserCampaignLimit
        contact = CampaignContact.objects.select_related('campaign').filter(id=contact_id).first()
        if not contact:
            return {"eligible": False, "reason": "contact_not_found"}
        campaign = contact.campaign
        if campaign.status not in ['running', 'draft']:
            logger.info(f"[RETRY] Campaign #{campaign.id} status is '{campaign.status}'. Skipping retry for contact #{contact.id}.")
            return {"eligible": False, "reason": f"campaign_{campaign.status}"}
        if contact.call_status == 'answered':
            logger.info(f"[RETRY] Contact #{contact.id} already answered. Skipping retry.")
            return {"eligible": False, "reason": "already_answered"}

        contact.call_status = 'pending'
        contact.save(update_fields=['call_status', 'updated_at'])
        limit = UserCampaignLimit.get_limit_for_user(campaign.user)
        return {
            "eligible": True,
            "campaign_id": campaign.id,
            "contact_id": contact.id,
            "user_id": campaign.user_id,
            "concurrency_limit": limit
        }

    prep_res = await ctx.step.run("check-and-prepare", sync_to_async(_prepare_retry_sync, thread_sensitive=True))
    if not prep_res.get("eligible"):
        return {"status": "skipped", "reason": prep_res.get("reason"), "contact_id": contact_id}

    # Emit dial event for this contact
    await inngest_client.send([
        inngest.Event(
            name="campaign/contact.dial",
            data={
                "campaign_id": prep_res.get("campaign_id"),
                "contact_id": prep_res.get("contact_id"),
                "user_id": prep_res.get("user_id"),
                "concurrency_limit": prep_res.get("concurrency_limit")
            }
        )
    ])
    logger.info(f"[RETRY] Successfully re-queued contact #{contact_id} for dialing after delay.")
    return {"status": "retry_dispatched", "contact_id": contact_id}


@inngest_client.create_function(
    fn_id="start-campaign",
    trigger=inngest.TriggerEvent(event="campaign/started"),
)
async def fn_start_campaign(ctx: inngest.Context) -> dict:
    """
    Orchestrator function to kick off an outbound campaign by emitting
    individual contact events (dial or whatsapp) respecting user limits.
    """
    event_data = ctx.event.data
    campaign_id = event_data.get("campaign_id")

    async def step_queue_contacts():
        res = await sync_to_async(_queue_contacts_sync, thread_sensitive=True)(campaign_id)
        events_to_send = [
            inngest.Event(
                name=d["event_name"],
                data=d["data"]
            )
            for d in res.get("events_data", [])
        ]

        if events_to_send:
            await inngest_client.send(events_to_send)

        broadcast_campaign_update(res.get("campaign_id"), "campaign_started", {
            "total_queued": res.get("queued_count"),
            "concurrency_limit": res.get("concurrency_limit"),
            "channel": res.get("channel")
        })

        return {"queued_count": res.get("queued_count"), "concurrency_limit": res.get("concurrency_limit")}

    return await ctx.step.run("queue-contacts", step_queue_contacts)


@inngest_client.create_function(
    fn_id="crm-process-whatsapp-followup",
    name="CRM: Process Autonomous WhatsApp Followup & Chat",
    trigger=inngest.TriggerEvent(event="crm/whatsapp.followup_requested"),
    retries=2,
)
async def fn_process_whatsapp_followup(ctx: inngest.Context):
    """Executes LangGraph autonomous omnichannel followup or chat reply via Inngest."""
    event_data = ctx.event.data
    user_id = event_data.get("user_id")
    phone_number = event_data.get("phone_number")
    trigger_type = event_data.get("trigger_type", "inbound_whatsapp")
    inbound_message = event_data.get("inbound_message", "")
    customer_name = event_data.get("customer_name", "")
    call_transcript = event_data.get("call_transcript", "")
    call_summary = event_data.get("call_summary", "")

    # Prevent processing non-deliverable identifiers such as web_dashboard
    raw_phone = str(phone_number or "").strip()
    digits = re.sub(r"\D", "", raw_phone)
    if not digits or raw_phone.lower() in ("web_dashboard", "none", "unknown", "anonymous") or len(digits) < 7:
        logger.info(f"[Inngest Followup] Skipped non-deliverable destination: '{phone_number}'")
        return {"status": "skipped", "reason": "invalid_or_web_phone"}

    async def step_run_langgraph():
        from crm.services.langgraph_worker import run_autonomous_followup
        try:
            return await sync_to_async(run_autonomous_followup, thread_sensitive=True)(
                user_id=user_id,
                phone_number=phone_number,
                trigger_type=trigger_type,
                call_transcript=call_transcript,
                call_summary=call_summary,
                inbound_message=inbound_message,
                customer_name=customer_name,
            )
        except Exception as e:
            logger.error(f"[Inngest LangGraph Error] Failed for {phone_number}: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "is_sent": False}

    return await ctx.step.run("execute-langgraph", step_run_langgraph)


def dispatch_whatsapp_followup_job(
    user_id: int,
    phone_number: str,
    trigger_type: str = "inbound_whatsapp",
    inbound_message: str = "",
    customer_name: str = "",
    call_transcript: str = "",
    call_summary: str = ""
):
    """Dispatches a durable Inngest background job for LangGraph followup with robust fallback."""
    raw_phone = str(phone_number or "").strip()
    digits = re.sub(r"\D", "", raw_phone)
    if not digits or raw_phone.lower() in ("web_dashboard", "none", "unknown", "anonymous") or len(digits) < 7:
        logger.info(f"Skipping WhatsApp followup dispatch: '{phone_number}' is not a valid deliverable phone number.")
        return {"status": "skipped", "reason": "invalid_or_web_phone"}

    from asgiref.sync import async_to_sync
    evt = inngest.Event(
        name="crm/whatsapp.followup_requested",
        data={
            "user_id": user_id,
            "phone_number": phone_number,
            "trigger_type": trigger_type,
            "inbound_message": inbound_message,
            "customer_name": customer_name,
            "call_transcript": call_transcript,
            "call_summary": call_summary,
        }
    )
    try:
        async_to_sync(inngest_client.send)([evt])
        logger.info(f"Successfully dispatched Inngest job for WhatsApp followup ({phone_number})")
        return {"status": "inngest_dispatched"}
    except Exception as e:
        logger.warning(f"Inngest dispatch failed ({e}), executing thread fallback: {e}")
        from crm.services.langgraph_worker import run_autonomous_followup
        import threading
        threading.Thread(
            target=run_autonomous_followup,
            kwargs={
                "user_id": user_id,
                "phone_number": phone_number,
                "trigger_type": trigger_type,
                "inbound_message": inbound_message,
                "customer_name": customer_name,
                "call_transcript": call_transcript,
                "call_summary": call_summary,
            },
            daemon=True
        ).start()
        return {"status": "thread_fallback"}


# ==================== Call Finish Redis Stream Consumer ====================
import redis

CALL_FINISH_STREAM_KEY = "call_finish_stream"
CALL_FINISH_GROUP_NAME = "call_finish_group"


def get_redis_connection():
    try:
        return redis.Redis.from_url(settings.REDIS_URL)
    except Exception as e:
        logger.warning(f"[Inngest Stream] Redis connection error: {e}")
        return None


def ensure_call_finish_stream_group(r: redis.Redis) -> bool:
    """Ensure consumer group exists on call_finish_stream."""
    try:
        r.xgroup_create(CALL_FINISH_STREAM_KEY, CALL_FINISH_GROUP_NAME, id="0", mkstream=True)
        return True
    except Exception as e:
        if "BUSYGROUP" in str(e):
            return True
        logger.warning(f"[Inngest Stream] xgroup_create error: {e}")
        return False


def ack_call_finish_stream_message(r: redis.Redis, stream_id: str) -> bool:
    """Acknowledge message in call_finish_stream."""
    if not stream_id:
        return False
    try:
        ensure_call_finish_stream_group(r)
        r.xack(CALL_FINISH_STREAM_KEY, CALL_FINISH_GROUP_NAME, stream_id)
        logger.info(f"[Inngest Stream XACK] Acknowledged stream message '{stream_id}'")
        return True
    except Exception as e:
        logger.warning(f"[Inngest Stream XACK Error] Failed to ack message '{stream_id}': {e}")
        return False


def parse_stream_entry_fields(raw_fields: dict) -> dict:
    """Decode raw Redis stream fields into typed Python dictionary."""
    data = {}
    for k, v in raw_fields.items():
        key_str = k.decode('utf-8') if isinstance(k, bytes) else str(k)
        val_str = v.decode('utf-8') if isinstance(v, bytes) else str(v)
        # Attempt json parse if looks like json object/array
        if (val_str.startswith('{') and val_str.endswith('}')) or (val_str.startswith('[') and val_str.endswith(']')):
            try:
                data[key_str] = json.loads(val_str)
                continue
            except Exception:
                pass
        # Numerical conversion for expected int/float fields
        if key_str in ('user_id', 'duration_seconds', 'session_id'):
            try:
                data[key_str] = int(val_str)
                continue
            except (ValueError, TypeError):
                pass
        elif key_str == 'started_at':
            try:
                data[key_str] = float(val_str)
                continue
            except (ValueError, TypeError):
                pass
        data[key_str] = val_str
    return data


@inngest_client.create_function(
    fn_id="process-call-finish-stream",
    name="Process Call Finish Stream Event",
    trigger=inngest.TriggerEvent(event="call/session.finish_stream"),
    retries=3,
)
async def fn_process_call_finish_stream(ctx: inngest.Context) -> dict:
    """
    Inngest consumer for individual call finish stream events.
    Asynchronously persists CallSession and CustomerMemory with automatic retries,
    then acknowledges the event in Redis Stream (XACK).
    """
    event_data = ctx.event.data or {}
    stream_id = event_data.get("stream_id")
    room_name = event_data.get("room_name")

    logger.info(f"[Inngest Stream] Processing call finish stream event for room '{room_name}' (stream_id: {stream_id})")

    # Step 1: Persist CallSession & CustomerMemory in PostgreSQL
    async def step_persist():
        from crm.services.session_persistence import persist_call_session_and_memory
        payload = dict(event_data)
        if stream_id and not payload.get("transcript_text") and not payload.get("summary"):
            r = get_redis_connection()
            if r:
                try:
                    entries = r.xrange(CALL_FINISH_STREAM_KEY, min=stream_id, max=stream_id)
                    if entries:
                        _, raw_fields = entries[0]
                        full_fields = parse_stream_entry_fields(raw_fields)
                        full_fields.update(payload)
                        payload = full_fields
                except Exception as r_err:
                    logger.debug(f"[Inngest Stream] xrange fetch note: {r_err}")
        return await sync_to_async(persist_call_session_and_memory, thread_sensitive=True)(payload)

    persist_res = await ctx.step.run("persist-call-session", step_persist)

    # Step 2: Acknowledge message in Redis Stream
    async def step_ack():
        if not stream_id:
            return {"acked": False, "reason": "no_stream_id"}
        r = get_redis_connection()
        if r:
            acked = ack_call_finish_stream_message(r, stream_id)
            return {"acked": acked, "stream_id": stream_id}
        return {"acked": False, "reason": "redis_unavailable"}

    ack_res = await ctx.step.run("ack-redis-stream", step_ack)

    return {
        "status": "completed",
        "room_name": room_name,
        "stream_id": stream_id,
        "persist_result": persist_res,
        "ack_result": ack_res,
    }


@inngest_client.create_function(
    fn_id="sweep-call-finish-stream",
    name="Sweep Call Finish Redis Stream",
    trigger=inngest.TriggerCron(cron="* * * * *"),
)
async def fn_sweep_call_finish_stream(ctx: inngest.Context) -> dict:
    """
    Periodic Inngest cron worker that sweeps call_finish_stream for any
    unprocessed or unacknowledged messages, guaranteeing zero data loss.
    """
    async def step_sweep():
        r = get_redis_connection()
        if not r:
            return {"status": "skipped", "reason": "redis_unavailable"}

        ensure_call_finish_stream_group(r)
        processed_count = 0

        try:
            from crm.services.session_persistence import persist_call_session_and_memory
            messages = r.xreadgroup(
                CALL_FINISH_GROUP_NAME,
                "inngest_sweeper",
                {CALL_FINISH_STREAM_KEY: ">"},
                count=10,
                block=500
            )
            for stream, entries in messages or []:
                for msg_id, raw_fields in entries:
                    stream_id = msg_id.decode('utf-8') if isinstance(msg_id, bytes) else str(msg_id)
                    data = parse_stream_entry_fields(raw_fields)
                    data["stream_id"] = stream_id
                    persist_call_session_and_memory(data)
                    ack_call_finish_stream_message(r, stream_id)
                    processed_count += 1
        except Exception as sweep_err:
            logger.warning(f"[Inngest Stream Sweeper] Error during stream sweep: {sweep_err}")

        return {"status": "swept", "processed_count": processed_count}

    sweep_res = await ctx.step.run("sweep-stream", step_sweep)
    return sweep_res


# Expose functions list for Django Inngest serve handler
all_inngest_functions = [
    fn_dial_campaign_contact,
    fn_send_campaign_whatsapp,
    fn_start_campaign,
    fn_retry_campaign_contact,
    fn_process_whatsapp_followup,
    fn_process_call_finish_stream,
    fn_sweep_call_finish_stream,
]

