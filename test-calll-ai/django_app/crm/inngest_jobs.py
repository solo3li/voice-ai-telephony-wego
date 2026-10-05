import os
import json
import logging
import inngest
from datetime import datetime, timezone
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
            broadcast_campaign_update(campaign.id, "contact_calling", {
                "contact_id": contact.id,
                "phone": contact.phone_number,
                "name": contact.customer_name,
                "room_name": room_name
            })
            return {"status": "success", "room_name": room_name, "dial_data": dial_res}
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
                campaign.update_metrics()
                return {"status": "error", "message": dial_res.get("message")}
    except Exception as err:
        logger.exception(f"Error in _initiate_contact_call_sync for contact {contact_id}")
        return {"status": "error", "message": str(err)}


def _check_and_mark_retry_sync(contact_id: int) -> dict:
    """Synchronous check to determine if a contact call qualifies for durable retry."""
    from crm.models import CampaignContact
    try:
        contact = CampaignContact.objects.select_related('campaign').get(id=contact_id)
        campaign = contact.campaign
        if contact.retries_count < campaign.max_retries and campaign.status == 'running':
            contact.retries_count += 1
            contact.call_status = 'pending'
            contact.save(update_fields=['retries_count', 'call_status', 'updated_at'])
            delay_mins = max(1, campaign.retry_delay_minutes)
            return {"should_retry": True, "delay_mins": delay_mins}
        return {"should_retry": False}
    except Exception as e:
        logger.exception(f"Error in _check_and_mark_retry_sync: {e}")
        return {"should_retry": False}


def _queue_contacts_sync(campaign_id: int) -> dict:
    """Synchronous query to gather pending contacts and user limit for a campaign."""
    from crm.models import OutboundCampaign, UserCampaignLimit
    campaign = OutboundCampaign.objects.get(id=campaign_id)
    campaign.status = 'running'
    campaign.save(update_fields=['status', 'updated_at'])

    limit = UserCampaignLimit.get_limit_for_user(campaign.user)
    pending_contacts = list(campaign.contacts.filter(call_status='pending').values_list('id', flat=True))
    logger.info(f"Queuing {len(pending_contacts)} contacts for campaign {campaign.id} (user concurrency limit: {limit})")

    events_data = [
        {
            "campaign_id": campaign.id,
            "contact_id": cid,
            "user_id": campaign.user_id,
            "concurrency_limit": limit
        }
        for cid in pending_contacts
    ]
    return {
        "events_data": events_data,
        "concurrency_limit": limit,
        "queued_count": len(pending_contacts),
        "campaign_id": campaign.id
    }


@inngest_client.create_function(
    fn_id="dial-campaign-contact",
    trigger=inngest.TriggerEvent(event="campaign/contact.dial"),
    concurrency=[inngest.Concurrency(limit=10, key="event.data.user_id")],
)
async def fn_dial_campaign_contact(ctx: inngest.Context) -> dict:
    """
    Inngest background job to execute an outbound call for a campaign contact.
    Handles concurrency throttling, LiveKit call dispatch, durable retry sleep, and lead scoring.
    """
    event_data = ctx.event.data
    contact_id = event_data.get("contact_id")

    async def step_initiate_call():
        return await sync_to_async(_initiate_contact_call_sync, thread_sensitive=True)(contact_id)

    call_result = await ctx.step.run("initiate-call", step_initiate_call)

    # If call was aborted due to missing outbound gateway, exit immediately without retries
    if call_result.get("code") == "no_outbound_gateway" or call_result.get("status") == "aborted":
        return {"status": "aborted", "reason": "no_outbound_gateway", "contact_id": contact_id}

    if call_result.get("status") != "success":
        retry_info = await sync_to_async(_check_and_mark_retry_sync, thread_sensitive=True)(contact_id)
        if retry_info.get("should_retry"):
            delay_mins = retry_info.get("delay_mins", 15)
            # Durable sleep via Inngest step before retry!
            await ctx.step.sleep("retry-delay", f"{delay_mins}m")
            return await ctx.step.run("retry-call", step_initiate_call)

    return {"status": "completed", "contact_id": contact_id, "call_result": call_result}


@inngest_client.create_function(
    fn_id="start-campaign",
    trigger=inngest.TriggerEvent(event="campaign/started"),
)
async def fn_start_campaign(ctx: inngest.Context) -> dict:
    """
    Orchestrator function to kick off an outbound campaign by emitting
    individual contact dial events respecting user limits.
    """
    event_data = ctx.event.data
    campaign_id = event_data.get("campaign_id")

    async def step_queue_contacts():
        res = await sync_to_async(_queue_contacts_sync, thread_sensitive=True)(campaign_id)
        events_to_send = [
            inngest.Event(
                name="campaign/contact.dial",
                data=d
            )
            for d in res.get("events_data", [])
        ]

        if events_to_send:
            await inngest_client.send(events_to_send)

        broadcast_campaign_update(res.get("campaign_id"), "campaign_started", {
            "total_queued": res.get("queued_count"),
            "concurrency_limit": res.get("concurrency_limit")
        })

        return {"queued_count": res.get("queued_count"), "concurrency_limit": res.get("concurrency_limit")}

    return await ctx.step.run("queue-contacts", step_queue_contacts)


# Expose functions list for Django Inngest serve handler
all_inngest_functions = [
    fn_dial_campaign_contact,
    fn_start_campaign,
]
