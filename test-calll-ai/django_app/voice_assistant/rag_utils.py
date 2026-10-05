"""
Re-export RAG utilities from knowledge.rag_utils for backward compatibility.
"""
from knowledge.rag_utils import (
    extract_text_from_file,
    chunk_text,
    get_embeddings_batch,
)

__all__ = [
    "extract_text_from_file",
    "chunk_text",
    "get_embeddings_batch",
]
