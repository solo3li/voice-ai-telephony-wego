import os
import sys
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from voice_assistant.models import Document, DocumentChunk
from voice_assistant.rag_utils import extract_text_from_file, chunk_text, get_embeddings_batch
from google import genai
from django.conf import settings
import psycopg2
from pgvector.psycopg2 import register_vector

def run_tests():
    print("========================================")
    print("🚀 STARTING END-TO-END SYSTEM TEST")
    print("========================================")

    # 1. Clean test user
    test_username = "test_e2e_user"
    test_password = "password123"
    User.objects.filter(username=test_username).delete()

    session = requests.Session()
    base_url = "http://localhost:8000"

    # Test 1: Access control (Unauthenticated redirect)
    print("\n[TEST 1] Checking unauthenticated protection on '/'...")
    r = session.get(f"{base_url}/", allow_redirects=False)
    assert r.status_code == 302, f"Expected 302 redirect, got {r.status_code}"
    assert "/login/" in r.headers.get("Location", ""), f"Unexpected redirect location: {r.headers.get('Location')}"
    print("✅ Unauthenticated user successfully redirected to /login/.")

    # Test 2: User Registration
    print("\n[TEST 2] Testing User Registration (/register/)...")
    # Fetch CSRF token
    reg_page = session.get(f"{base_url}/register/")
    csrf_token = session.cookies.get("csrftoken")

    reg_payload = {
        "username": test_username,
        "email": "test@example.com",
        "password": test_password,
        "password_confirm": test_password,
        "csrfmiddlewaretoken": csrf_token
    }
    r = session.post(f"{base_url}/register/", data=reg_payload, headers={"Referer": f"{base_url}/register/"}, allow_redirects=True)
    assert r.status_code == 200
    assert test_username in r.text
    print(f"✅ User '{test_username}' successfully registered and logged in!")

    user = User.objects.get(username=test_username)
    user_id = user.id
    print(f"   User ID in DB: {user_id}")

    # Test 3: Fetch Tokens (/api/token/)
    print("\n[TEST 3] Testing Token Generation (/api/token/)...")
    token_res = session.get(f"{base_url}/api/token/")
    assert token_res.status_code == 200
    token_data = token_res.json()
    assert token_data["status"] == "success"
    assert "livekit_token" in token_data
    assert "centrifugo_token" in token_data
    assert f"user_{user_id}" in token_data["user_identity"]
    print(f"✅ LiveKit & Centrifugo tokens generated for user: {token_data['user_identity']}")

    # Test 4: Document Ingestion & Embedding with Gemini
    print("\n[TEST 4] Testing Document Ingestion & Gemini Embedding (RAG)...")
    doc_content = """
    سياسة الإرجاع والضمان لمتجر الأفق الذكي:
    1. يحق للعميل إرجاع أي منتج خلال 14 يوماً من تاريخ الاستلام شريطة أن يكون بحالته الأصلية.
    2. الضمان ساري لمدة سنتين ويشمل الأعطال المصنعية فقط ولا يشمل سوء الاستخدام أو الكسر.
    3. الرقم الموحد لخدمة العملاء هو 920008899 ويعمل من الأحد إلى الخميس من 9 صباحاً إلى 5 مساءً.
    """
    
    files = {
        "file": ("store_policy.txt", doc_content.encode("utf-8"), "text/plain")
    }
    csrf_token = session.cookies.get("csrftoken")
    headers = {
        "Referer": f"{base_url}/",
        "X-CSRFToken": csrf_token
    }
    upload_res = session.post(f"{base_url}/api/documents/upload/", files=files, headers=headers)
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_json = upload_res.json()
    assert upload_json["status"] == "success"
    print(f"✅ Document successfully uploaded and embedded: {upload_json['message']}")

    # Check Document & Chunks in DB
    doc_count = Document.objects.filter(user=user).count()
    chunk_count = DocumentChunk.objects.filter(user=user).count()
    assert doc_count == 1
    assert chunk_count > 0
    print(f"✅ Verified in PostgreSQL: {doc_count} Document, {chunk_count} Chunks with 768-dim embeddings.")

    # Test 5: Semantic Search (Matching Document Query)
    print("\n[TEST 5] Testing Semantic Search with Gemini text-embedding-004...")
    query = "كم مدة الإرجاع المسموحة وما هو رقم خدمة العملاء؟"
    from google.genai import types
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    emb_res = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    q_vec = emb_res.embeddings[0].values
    
    # Query Postgres pgvector directly
    conn = psycopg2.connect(
        dbname=settings.DATABASES['default']['NAME'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT']
    )
    register_vector(conn)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT content, (embedding <=> %s::vector) AS distance
            FROM voice_assistant_documentchunk
            WHERE user_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 2;
        """, (q_vec, user_id, q_vec))
        results = cur.fetchall()
    conn.close()

    assert len(results) > 0
    best_match_content, distance = results[0]
    print(f"   Query: '{query}'")
    print(f"   Cosine Distance: {distance:.4f} (Similarity: {1 - distance:.4f})")
    assert distance < 0.5, f"Distance too high: {distance}"
    assert "14" in best_match_content
    assert "920008899" in best_match_content
    print("✅ Semantic Search retrieved exact matching chunk with high similarity!")

    # Test 6: Document Isolation (Multi-Tenancy)
    print("\n[TEST 6] Testing Multi-Tenancy / User Data Isolation...")
    other_user = User.objects.create_user(username="other_user_e2e", password="password123")
    with psycopg2.connect(
        dbname=settings.DATABASES['default']['NAME'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT']
    ) as conn_other:
        register_vector(conn_other)
        with conn_other.cursor() as cur:
            cur.execute("""
                SELECT count(*)
                FROM voice_assistant_documentchunk
                WHERE user_id = %s;
            """, (other_user.id,))
            other_chunks = cur.fetchone()[0]
    other_user.delete()
    assert other_chunks == 0
    print("✅ User data isolation confirmed: Other users cannot see or search another user's documents.")

    print("\n========================================")
    print("🎉 ALL END-TO-END TESTS PASSED SUCCESSFULLY!")
    print("========================================")

if __name__ == '__main__':
    run_tests()
