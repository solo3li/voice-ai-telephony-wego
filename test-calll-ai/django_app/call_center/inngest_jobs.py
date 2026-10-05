import os
import json
import time
import uuid
import logging
import datetime
from django.conf import settings
from asgiref.sync import sync_to_async
from livekit import api
import redis
import requests
import inngest

logger = logging.getLogger(__name__)

from common.inngest_client import inngest_client
from common.centrifugo import publish_to_centrifugo

def _get_redis():
    return redis.Redis.from_url(settings.REDIS_URL)

async def delete_livekit_room(room_name: str):
    """Cleanly delete and close LiveKit room on server."""
    if not room_name:
        return
    try:
        lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        await lk.room.delete_room(api.DeleteRoomRequest(room=room_name))
        await lk.aclose()
        logger.info(f"LiveKit room {room_name} deleted successfully.")
    except Exception as e:
        logger.debug(f"LiveKit room deletion note for {room_name}: {e}")

def generate_livekit_token(room_name: str, identity: str, name: str, metadata: dict = None) -> str:
    """Generate secure LiveKit token for a room."""
    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(name)
    if metadata:
        token = token.with_metadata(json.dumps(metadata))
    token = token.with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
    return token.to_jwt()


def _get_employee_sync(emp_id: int):
    from call_center.models import EmployeeProfile
    return EmployeeProfile.objects.filter(id=emp_id, is_active=True).first()

def _update_employee_status_sync(emp_id: int, status: str):
    from call_center.models import EmployeeProfile
    emp = EmployeeProfile.objects.filter(id=emp_id).first()
    if emp:
        emp.status = status
        emp.save(update_fields=['status'])
        publish_to_centrifugo("employees:presence", {
            "event": "status_change",
            "employee": emp.to_dict()
        })
        return emp.to_dict()
    return None

def _create_call_log_sync(emp_id: int, other_party: str, extension: str, room_name: str, call_type: str):
    from call_center.models import EmployeeProfile, EmployeeCallLog
    emp = EmployeeProfile.objects.filter(id=emp_id).first()
    if emp:
        return EmployeeCallLog.objects.create(
            employee=emp,
            other_party=other_party,
            extension=extension,
            room_name=room_name,
            call_type=call_type
        )
    return None


@inngest_client.create_function(
    fn_id="transfer-call-queue",
    trigger=inngest.TriggerEvent(event="call_center/transfer.requested"),
)
async def fn_transfer_call_queue(ctx: inngest.Context) -> dict:
    """
    Durable, clean call transfer workflow.
    - Closes old room immediately.
    - Puts Caller on hold locally with hold tone.
    - Rings queue candidates one by one in priority order.
    - If answered: creates new room, connects both, and notifies transferrer.
    - If rejected/timeout: moves to next online candidate.
    - If cancelled: restores connection between Caller and Transferrer.
    - If expired: ends hold and notifies parties.
    """
    event_data = ctx.event.data
    transfer_id = event_data.get("transfer_id")
    old_room_name = event_data.get("old_room_name")
    from_emp_id = event_data.get("from_employee_id")
    from_emp_name = event_data.get("from_employee_name", "الزميل")
    from_emp_ext = event_data.get("from_employee_extension", "")
    caller_id = event_data.get("caller_id")
    caller_name = event_data.get("caller_name", "المتصل")
    caller_ext = event_data.get("caller_extension", "")
    candidate_ids = event_data.get("candidate_ids", [])
    ring_timeout_seconds = int(event_data.get("ring_timeout_seconds", 15))
    total_timeout_seconds = int(event_data.get("total_timeout_seconds", 300))

    logger.info(f"[Inngest Transfer {transfer_id}] Starting transfer for caller {caller_name} ({caller_ext}) -> candidates {candidate_ids} (total timeout: {total_timeout_seconds}s)")

    # Step 1: Ensure old LiveKit room is cleanly deleted if internal employee transfer
    async def step_close_old_room():
        if caller_id and old_room_name:
            await delete_livekit_room(old_room_name)
        return {"status": "room_closed", "room": old_room_name}

    await ctx.step.run("close-old-room", step_close_old_room)

    # Step 2: Initialize transfer state in Redis inside a step so replays don't overwrite it
    async def step_init_transfer_state():
        r_init = _get_redis()
        current_state = r_init.get(f"transfer:{transfer_id}:state")
        if not current_state:
            r_init.set(f"transfer:{transfer_id}:state", "ringing", ex=total_timeout_seconds + 60)
        return {"status": "initialized"}

    await ctx.step.run("init-transfer-state", step_init_transfer_state)

    r = _get_redis()
    # Check if transfer already finished in previous step executions
    current_state = r.get(f"transfer:{transfer_id}:state")
    if current_state in [b"completed", b"cancelled"]:
        logger.info(f"[Inngest Transfer {transfer_id}] Pre-loop check: state is already {current_state}")
        return {"status": current_state.decode()}

    # Step 3: Iterate through candidate employees in order with queue waiting period (up to total_timeout_seconds)
    transferred_success = False
    answered_emp_id = None

    start_loop_time = time.time()
    pass_num = 0
    max_passes = max(int(total_timeout_seconds // 5), 1)

    while (time.time() - start_loop_time) < total_timeout_seconds and pass_num < max_passes:
        pass_num += 1

        # Check current Redis state before running pass
        current_state = r.get(f"transfer:{transfer_id}:state")
        if current_state in [b"completed", b"cancelled"]:
            logger.info(f"[Inngest Transfer {transfer_id}] Stopped in loop (pass {pass_num}): state is already {current_state}")
            return {"status": current_state.decode()}

        any_candidate_rung = False

        for idx, cand_id in enumerate(candidate_ids):
            # Check current Redis state before attempting next candidate
            current_state = r.get(f"transfer:{transfer_id}:state")
            if current_state in [b"completed", b"cancelled"]:
                logger.info(f"[Inngest Transfer {transfer_id}] Stopped in loop: state is already {current_state}")
                return {"status": current_state.decode()}

            # Verify candidate is still available in DB
            cand = await sync_to_async(_get_employee_sync, thread_sensitive=True)(cand_id)
            if not cand:
                continue

            # If candidate was already set as current candidate or transfer completed, don't skip them
            current_cand_id = r.get(f"transfer:{transfer_id}:current_candidate")
            is_current_candidate = (current_cand_id == str(cand_id).encode())
            if not is_current_candidate and cand.status not in ['ready', 'available']:
                logger.info(f"[Inngest Transfer {transfer_id}] Candidate {cand_id} not available (status={getattr(cand, 'status', None)}), skipping in pass {pass_num}.")
                continue

            any_candidate_rung = True
            step_tag = f"p{pass_num}-c{cand_id}"

            # Ring candidate
            async def step_ring_candidate():
                r.set(f"transfer:{transfer_id}:current_candidate", cand_id, ex=ring_timeout_seconds + 5)
                call_payload = {
                    "event": "incoming_call",
                    "call_type": "transfer",
                    "transfer_id": transfer_id,
                    "room_name": old_room_name if (not caller_id and old_room_name) else f"transfer_{transfer_id}",
                    "caller_name": caller_name,
                    "caller_extension": caller_ext,
                    "transferred_by": from_emp_name,
                    "ring_timeout_seconds": ring_timeout_seconds,
                }
                r.set(f"call_center:ringing:employee:{cand_id}", json.dumps(call_payload), ex=ring_timeout_seconds + 5)
                publish_to_centrifugo(f"employee:{cand_id}", call_payload)
                if getattr(cand, 'push_token', None):
                    try:
                        from .views import send_expo_push_notification
                        send_expo_push_notification(
                            cand.push_token,
                            "مكالمة محولة واردة",
                            f"مكالمة واردة ومحولة من {from_emp_name} لـ {caller_name}",
                            call_payload
                        )
                    except Exception as pe:
                        logger.warning(f"Error sending push on transfer: {pe}")
                return {"status": "ringing", "candidate_id": cand_id}

            await ctx.step.run(f"ring-{step_tag}", step_ring_candidate)

            # Wait for action event from candidate (answer/reject) or from transferrer (cancel)
            action_event = await ctx.step.wait_for_event(
                f"wait-action-{step_tag}",
                event="call_center/transfer.action",
                if_exp=f"async.data.transfer_id == '{transfer_id}'",
                timeout=datetime.timedelta(seconds=ring_timeout_seconds)
            )

            if action_event is None:
                # Check if state was changed in the meantime
                if r.get(f"transfer:{transfer_id}:state") in [b"completed", b"cancelled"]:
                    return {"status": r.get(f"transfer:{transfer_id}:state").decode()}

                # Timeout on this candidate
                logger.info(f"[Inngest Transfer {transfer_id}] Candidate {cand_id} timed out after {ring_timeout_seconds}s in pass {pass_num}.")
                async def step_timeout_candidate():
                    r.delete(f"call_center:ringing:employee:{cand_id}")
                    publish_to_centrifugo(f"employee:{cand_id}", {
                        "event": "call_ended",
                        "transfer_id": transfer_id,
                        "reason": "timeout"
                    })
                    return {"status": "candidate_timed_out", "candidate_id": cand_id}
                await ctx.step.run(f"timeout-{step_tag}", step_timeout_candidate)
                continue

            action_data = action_event.data
            action = action_data.get("action")
            action_emp_id = action_data.get("employee_id")

            # 3.1: Candidate Answered
            if action == "answer" and int(action_emp_id) == int(cand_id):
                logger.info(f"[Inngest Transfer {transfer_id}] Candidate {cand_id} answered call in pass {pass_num}!")
                answered_emp_id = cand_id

                async def step_complete_transfer():
                    if not caller_id and old_room_name:
                        new_room = old_room_name
                    else:
                        new_room = f"call_ext_{caller_ext}_{cand.extension}_tr_{uuid.uuid4().hex[:6]}"
                    
                    r.delete(f"call_center:ringing:employee:{cand_id}")
                    # Tokens
                    cand_token = generate_livekit_token(
                        new_room,
                        f"employee_{cand.id}_{cand.extension}",
                        cand.display_name,
                        {"role": "callee", "employee_id": cand.id}
                    )

                    # Set candidate busy
                    await sync_to_async(_update_employee_status_sync, thread_sensitive=True)(cand.id, "busy")
                    
                    # Create call log for candidate
                    await sync_to_async(_create_call_log_sync, thread_sensitive=True)(
                        cand.id, caller_name, caller_ext, new_room, "inbound"
                    )

                    # Send new room token to Caller on hold if employee
                    if caller_id:
                        caller_token = generate_livekit_token(
                            new_room,
                            f"employee_{caller_id}_{caller_ext}",
                            caller_name,
                            {"role": "caller", "employee_id": caller_id}
                        )
                        publish_to_centrifugo(f"employee:{caller_id}", {
                            "event": "transfer_room_ready",
                            "transfer_id": transfer_id,
                            "room_name": new_room,
                            "livekit_url": settings.LIVEKIT_URL,
                            "livekit_token": caller_token,
                            "partner_name": cand.display_name,
                            "partner_extension": cand.extension
                        })

                    # Broadcast to room channel for web widgets
                    if old_room_name:
                        publish_to_centrifugo(f"rooms:{old_room_name}", {
                            "event": "transfer_room_ready",
                            "transfer_id": transfer_id,
                            "room_name": new_room,
                            "partner_name": cand.display_name,
                            "partner_extension": cand.extension
                        })

                    # Send new room token to Answered Candidate
                    publish_to_centrifugo(f"employee:{cand.id}", {
                        "event": "transfer_room_ready",
                        "transfer_id": transfer_id,
                        "room_name": new_room,
                        "livekit_url": settings.LIVEKIT_URL,
                        "livekit_token": cand_token,
                        "partner_name": caller_name,
                        "partner_extension": caller_ext
                    })

                    # Notify Transferrer of success if human employee
                    if from_emp_id:
                        publish_to_centrifugo(f"employee:{from_emp_id}", {
                            "event": "transfer_success",
                            "transfer_id": transfer_id,
                            "transferred_to": cand.display_name,
                            "target_extension": cand.extension
                        })
                        await sync_to_async(_update_employee_status_sync, thread_sensitive=True)(from_emp_id, "ready")

                    r.set(f"transfer:{transfer_id}:state", "completed", ex=300)
                    r.set(f"transfer:{transfer_id}:answered_by", cand.id, ex=300)
                    if old_room_name:
                        r.delete(f"room:{old_room_name}:is_transferring")
                        r.delete(f"room:{old_room_name}:transfer_id")
                    if new_room:
                        r.delete(f"room:{new_room}:is_transferring")
                        r.delete(f"room:{new_room}:transfer_id")
                    return {"status": "completed", "room": new_room, "answered_by": cand.id}

                res = await ctx.step.run(f"complete-{step_tag}", step_complete_transfer)
                transferred_success = True
                return res

            # 3.2: Transferrer Cancelled
            elif action == "cancel":
                logger.info(f"[Inngest Transfer {transfer_id}] Transfer cancelled by transferrer {from_emp_id} in pass {pass_num}.")
                async def step_cancel_transfer():
                    # Dismiss ringing on candidate
                    publish_to_centrifugo(f"employee:{cand_id}", {
                        "event": "call_ended",
                        "transfer_id": transfer_id,
                        "reason": "cancelled"
                    })

                    # Reconnect Caller and Transferrer only if both are employees
                    restored_room = None
                    if caller_id and from_emp_id:
                        restored_room = f"call_ext_{caller_ext}_{from_emp_ext}_rst_{uuid.uuid4().hex[:6]}"
                        caller_token = generate_livekit_token(
                            restored_room,
                            f"employee_{caller_id}_{caller_ext}",
                            caller_name,
                            {"role": "caller", "employee_id": caller_id}
                        )
                        from_token = generate_livekit_token(
                            restored_room,
                            f"employee_{from_emp_id}_{from_emp_ext}",
                            from_emp_name,
                            {"role": "transferrer", "employee_id": from_emp_id}
                        )

                        publish_to_centrifugo(f"employee:{caller_id}", {
                            "event": "transfer_cancelled",
                            "transfer_id": transfer_id,
                            "room_name": restored_room,
                            "livekit_url": settings.LIVEKIT_URL,
                            "livekit_token": caller_token,
                            "partner_name": from_emp_name
                        })
                        publish_to_centrifugo(f"employee:{from_emp_id}", {
                            "event": "transfer_cancelled",
                            "transfer_id": transfer_id,
                            "room_name": restored_room,
                            "livekit_url": settings.LIVEKIT_URL,
                            "livekit_token": from_token,
                            "partner_name": caller_name
                        })

                    if old_room_name:
                        r.delete(f"room:{old_room_name}:is_transferring")
                        r.delete(f"room:{old_room_name}:transfer_id")

                    r.set(f"transfer:{transfer_id}:state", "cancelled", ex=300)
                    return {"status": "cancelled", "restored_room": restored_room}

                res = await ctx.step.run(f"cancel-{step_tag}", step_cancel_transfer)
                return res

            # 3.3: Candidate Rejected
            elif action == "reject":
                logger.info(f"[Inngest Transfer {transfer_id}] Candidate {cand_id} rejected call in pass {pass_num}.")
                async def step_reject_candidate():
                    publish_to_centrifugo(f"employee:{cand_id}", {
                        "event": "call_ended",
                        "transfer_id": transfer_id,
                        "reason": "rejected"
                    })
                    return {"status": "rejected", "candidate_id": cand_id}
                await ctx.step.run(f"reject-{step_tag}", step_reject_candidate)
                continue

        if transferred_success or r.get(f"transfer:{transfer_id}:state") in [b"completed", b"cancelled"]:
            break

        # If no candidates were available to ring in this pass, wait 5 seconds before next cycle
        if not any_candidate_rung:
            logger.info(f"[Inngest Transfer {transfer_id}] No candidate available in pass {pass_num}. Customer waiting in queue...")
            await ctx.step.sleep(f"wait-queue-pass-{pass_num}", datetime.timedelta(seconds=5))

    # Step 4: If nobody answered or all rejected / timed out
    # Pre-check Redis: if state is completed or cancelled, DO NOT send transfer_failed!
    final_state = r.get(f"transfer:{transfer_id}:state")
    if final_state in [b"completed", b"cancelled"]:
        logger.info(f"[Inngest Transfer {transfer_id}] Skipping failure step: state is {final_state}")
        return {"status": final_state.decode()}

    if not transferred_success:
        logger.info(f"[Inngest Transfer {transfer_id}] All candidates exhausted. Transfer failed.")
        async def step_finalize_failed():
            # Check inside step as well
            r_check = _get_redis()
            if r_check.get(f"transfer:{transfer_id}:state") in [b"completed", b"cancelled"]:
                logger.info(f"[Inngest Transfer {transfer_id}] In-step check: transfer already resolved. Skipping failure.")
                return {"status": "already_resolved"}

            if caller_id:
                publish_to_centrifugo(f"employee:{caller_id}", {
                    "event": "transfer_failed",
                    "transfer_id": transfer_id,
                    "message": "عذراً، لم يتسنَّ للموظفين الرد على المكالمة حالياً وتم إنهاء المكالمة."
                })
                await sync_to_async(_update_employee_status_sync, thread_sensitive=True)(caller_id, "ready")

            if old_room_name:
                publish_to_centrifugo(f"rooms:{old_room_name}", {
                    "event": "transfer_failed",
                    "transfer_id": transfer_id,
                    "message": "عذراً، لم يتسنَّ للموظفين الرد على المكالمة حالياً وتم إنهاء المكالمة."
                })
                r_check.delete(f"room:{old_room_name}:is_transferring")
                r_check.delete(f"room:{old_room_name}:transfer_id")
            r_check.set(f"transfer:{transfer_id}:state", "failed", ex=300)
            return {"status": "failed", "reason": "all_candidates_exhausted"}

        res = await ctx.step.run("finalize-failed-transfer", step_finalize_failed)
        return res

    return {"status": "done"}

all_call_center_inngest_functions = [
    fn_transfer_call_queue,
]
