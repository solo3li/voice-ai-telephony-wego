import logging
from django.core.management.base import BaseCommand
from voice_assistant.chatwoot_service import get_chatwoot_db_conn, register_chatwoot_billing_webhook

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Registers or updates the message billing webhook for all existing Chatwoot accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            default=None,
            help="Custom webhook URL (defaults to CHATWOOT_BILLING_WEBHOOK_URL setting or http://voice_django:8000/api/billing/chatwoot/webhook/)",
        )

    def handle(self, *args, **options):
        custom_url = options.get('url')
        self.stdout.write("Fetching accounts from Chatwoot database...")

        account_ids = []
        try:
            with get_chatwoot_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, name FROM accounts ORDER BY id ASC;")
                    rows = cur.fetchall()
                    account_ids = [(row[0], row[1]) for row in rows]
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to query Chatwoot accounts: {e}"))
            return

        if not account_ids:
            self.stdout.write(self.style.WARNING("No accounts found in Chatwoot database."))
            return

        self.stdout.write(f"Found {len(account_ids)} accounts. Registering billing webhooks...")
        success_count = 0
        error_count = 0

        for acc_id, acc_name in account_ids:
            ok = register_chatwoot_billing_webhook(acc_id, webhook_url=custom_url)
            if ok:
                success_count += 1
                self.stdout.write(f" [OK] Account #{acc_id} ({acc_name})")
            else:
                error_count += 1
                self.stderr.write(self.style.ERROR(f" [ERR] Account #{acc_id} ({acc_name})"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully registered billing webhooks for {success_count}/{len(account_ids)} accounts. (Errors: {error_count})"
            )
        )
