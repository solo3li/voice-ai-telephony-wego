"""Management command to process completed call finish events from Redis Stream.

Runs continuously or with --once flag.
Reads from 'call_finish_stream' using consumer group 'call_finish_group',
asynchronously persists CallSession & updates CustomerMemory in PostgreSQL,
and sends XACK acknowledgment.
"""
import time
import signal
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
import redis

from crm.inngest_jobs import (
    CALL_FINISH_STREAM_KEY,
    CALL_FINISH_GROUP_NAME,
    ensure_call_finish_stream_group,
    ack_call_finish_stream_message,
    parse_stream_entry_fields
)
from crm.services.session_persistence import persist_call_session_and_memory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume and process finished call records from Redis Stream 'call_finish_stream'."

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run a single pass over existing stream entries and exit.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of messages to read per batch (default: 10).',
        )
        parser.add_argument(
            '--block-ms',
            type=int,
            default=2000,
            help='Milliseconds to block waiting for new messages (default: 2000ms).',
        )

    def handle(self, *args, **options):
        once = options['once']
        batch_size = options['batch_size']
        block_ms = options['block_ms']

        self.stdout.write(self.style.SUCCESS(
            f"[*] Starting Redis Stream consumer on '{CALL_FINISH_STREAM_KEY}' (Group: '{CALL_FINISH_GROUP_NAME}')..."
        ))

        r = redis.Redis.from_url(settings.REDIS_URL)
        ensure_call_finish_stream_group(r)

        running = True

        def sig_handler(sig, frame):
            nonlocal running
            self.stdout.write("Received shutdown signal. Stopping consumer gracefully...")
            running = False

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        consumer_name = f"django_worker_{int(time.time())}"
        processed_total = 0

        while running:
            try:
                # Read new entries from stream
                messages = r.xreadgroup(
                    CALL_FINISH_GROUP_NAME,
                    consumer_name,
                    {CALL_FINISH_STREAM_KEY: ">"},
                    count=batch_size,
                    block=block_ms
                )

                if not messages:
                    if once:
                        self.stdout.write(f"No more messages in stream. Total processed: {processed_total}")
                        break
                    continue

                for stream, entries in messages:
                    for msg_id, raw_fields in entries:
                        stream_id = msg_id.decode('utf-8') if isinstance(msg_id, bytes) else str(msg_id)
                        data = parse_stream_entry_fields(raw_fields)
                        data['stream_id'] = stream_id

                        res = persist_call_session_and_memory(data)
                        ack_call_finish_stream_message(r, stream_id)
                        processed_total += 1

                        room = data.get('room_name', 'unknown')
                        self.stdout.write(self.style.SUCCESS(
                            f"[OK] Persisted room '{room}' (Stream ID: {stream_id}, Session #{res.get('session_id')}) -> XACK sent."
                        ))

                if once:
                    break

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error processing stream entries: {e}"))
                if once:
                    break
                time.sleep(1.0)

        self.stdout.write(self.style.SUCCESS(f"Stream consumer finished. Total processed: {processed_total}"))
