import os
import io
import logging
from google.genai import types

logger = logging.getLogger(__name__)

def extract_text_from_file(file_obj, filename: str) -> str:
    """Extract raw text from PDF, DOCX, and plain text files."""
    ext = os.path.splitext(filename)[1].lower()
    text = ""
    
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    
    if ext == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(file_obj)
        pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t.strip())
        text = "\n\n".join(pages)
        
    elif ext in ('.docx', '.doc'):
        import docx
        doc = docx.Document(file_obj)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        
    elif ext in ('.txt', '.md', '.csv', '.json'):
        content = file_obj.read()
        if isinstance(content, bytes):
            text = content.decode('utf-8', errors='ignore')
        else:
            text = content
    else:
        raise ValueError(f"صيغة الملف '{ext}' غير مدعومة. الصيغ المدعومة هي: PDF, DOCX, TXT, MD")

    return text.strip()

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks of chunk_size characters with overlap."""
    chunks = []
    text = text.strip()
    if not text:
        return chunks

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

def get_embeddings_batch(genai_client, texts: list[str], batch_size: int = 50) -> list[list[float]]:
    """Generate embeddings for texts using Gemini embedding model in batches with 768 dimensions."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        res = genai_client.models.embed_content(
            model="gemini-embedding-001",
            contents=batch,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        for emb in res.embeddings:
            all_embeddings.append(emb.values)
    return all_embeddings
