import os, sys, psycopg2
from pypdf import PdfReader
from google import genai

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from knowledge.models import Document, DocumentChunk
from knowledge.rag_utils import get_embeddings_batch
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(username='shosho')

pdf_path = '/tmp/qisas.pdf'
reader = PdfReader(pdf_path)
full_text = ""
for page in reader.pages:
    txt = page.extract_text() or ""
    if txt.strip():
        full_text += txt + "\n\n"

file_size = os.path.getsize(pdf_path)
print(f"Extracted {len(full_text)} characters from {len(reader.pages)} pages. File size: {file_size} bytes.")

title = "قصص وحكايات_60024_Foulabook.com_"
doc, created = Document.objects.get_or_create(
    user=user,
    title=title,
    defaults={
        "file_type": "PDF",
        "file_size": file_size,
        "status": "ready"
    }
)
if not created:
    doc.chunks.all().delete()
    doc.file_type = "PDF"
    doc.file_size = file_size
    doc.status = "ready"
    doc.save()

chunk_size = 500
overlap = 50
chunks = []
start = 0
while start < len(full_text):
    end = start + chunk_size
    chunk_str = full_text[start:end].strip()
    if chunk_str:
        chunks.append(chunk_str)
    start += (chunk_size - overlap)
    if len(chunks) >= 30:  # 30 representative chunks
        break

# Generate embeddings
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
print(f"Generating 768-dim embeddings for {len(chunks)} chunks...")
embeddings = get_embeddings_batch(client, chunks)
print(f"Generated {len(embeddings)} embeddings successfully.")

chunk_objects = []
for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
    chunk_objects.append(DocumentChunk(
        document=doc,
        user=user,
        chunk_index=idx,
        content=chunk_text,
        embedding=emb,
    ))

DocumentChunk.objects.bulk_create(chunk_objects)
print(f"Created Django Document #{doc.id} with {len(chunk_objects)} chunks for user {user.username}!")

# Update Chatwoot captain_documents (id 1)
conn = psycopg2.connect(
    dbname="chatwoot_production",
    user="postgres",
    password="ChatwootDbPassword2026",
    host="omni_postgres",
    port=5432
)
cur = conn.cursor()

cur.execute("""
    UPDATE captain_documents
    SET content = %s, status = 1, sync_status = 1, updated_at = NOW(),
        metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{django_doc_id}', %s::jsonb, true)
    WHERE id = 1
""", (full_text[:50000], str(doc.id)))

cur.execute("DELETE FROM captain_assistant_responses WHERE documentable_id = 1 AND documentable_type = 'Captain::Document'")

qas = [
    ("ما هو محتوى كتاب قصص وحكايات؟", full_text[:1500]),
]
for idx, chunk in enumerate(chunks[:15]):
    qas.append((f"قصص وحكايات - جزء {idx+1}:", chunk))

for q, a in qas:
    cur.execute("""
        INSERT INTO captain_assistant_responses (
            assistant_id, account_id, question, answer, status,
            documentable_type, documentable_id, edited, created_at, updated_at
        ) VALUES (
            1, 2, %s, %s, 1,
            'Captain::Document', 1, false, NOW(), NOW()
        )
    """, (q, a))

conn.commit()
print(f"Updated Chatwoot Document #1 and added {len(qas)} responses!")

cur.execute("SELECT id, name, status, sync_status FROM captain_documents ORDER BY id")
for row in cur.fetchall():
    print("Chatwoot Doc in DB:", row)

conn.close()
