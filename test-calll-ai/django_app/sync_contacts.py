import os, psycopg2
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from crm.models import CampaignContact, CustomerMemory

conn = psycopg2.connect(
    dbname="chatwoot_production",
    user="postgres",
    password="ChatwootDbPassword2026",
    host="omni_postgres",
    port=5432
)
cur = conn.cursor()

# 1. Sync from CustomerMemory
memories = CustomerMemory.objects.all()
synced_count = 0
for m in memories:
    phone = (m.phone_number or "").strip()
    if not phone:
        continue
    name = (m.customer_name or "").strip() or f"عميل {phone[-4:]}"
    cur.execute("SELECT id FROM contacts WHERE account_id = 2 AND phone_number = %s", (phone,))
    existing = cur.fetchone()
    if existing:
        cur.execute("""
            UPDATE contacts
            SET name = %s, updated_at = NOW(),
                custom_attributes = jsonb_set(COALESCE(custom_attributes, '{}'::jsonb), '{total_calls}', %s::jsonb, true)
            WHERE id = %s
        """, (name, f'"{m.total_calls_count}"', existing[0]))
    else:
        cur.execute("""
            INSERT INTO contacts (
                account_id, name, phone_number, created_at, updated_at,
                custom_attributes
            ) VALUES (
                2, %s, %s, NOW(), NOW(),
                %s::jsonb
            )
        """, (name, phone, f'{{"source": "voice_ai_memory", "total_calls": "{m.total_calls_count}"}}'))
    synced_count += 1

# 2. Sync from CampaignContact
contacts = CampaignContact.objects.all()
for c in contacts:
    phone = (c.phone_number or "").strip()
    if not phone:
        continue
    name = (c.customer_name or "").strip() or f"عميل {phone[-4:]}"
    cur.execute("SELECT id FROM contacts WHERE account_id = 2 AND phone_number = %s", (phone,))
    existing = cur.fetchone()
    if not existing:
        cur.execute("""
            INSERT INTO contacts (
                account_id, name, phone_number, created_at, updated_at,
                custom_attributes
            ) VALUES (
                2, %s, %s, NOW(), NOW(),
                '{"source": "voice_campaign"}'::jsonb
            )
        """, (name, phone))
        synced_count += 1

conn.commit()
print(f"Synced {synced_count} contacts into Chatwoot contacts table!")

cur.execute("SELECT COUNT(*) FROM contacts WHERE account_id = 2")
total_chatwoot_contacts = cur.fetchone()[0]
print(f"Total contacts now in Chatwoot for Account 2: {total_chatwoot_contacts}")

conn.close()
