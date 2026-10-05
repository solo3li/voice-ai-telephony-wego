from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField, HnswIndex

class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    file_type = models.CharField(max_length=50, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default='ready', choices=[('pending', 'قيد الفهرسة'), ('ready', 'جاهز'), ('failed', 'فشل')])
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voice_assistant_document'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_chunks')
    chunk_index = models.IntegerField(default=0)
    content = models.TextField()
    embedding = VectorField(dimensions=768)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voice_assistant_documentchunk'
        ordering = ['chunk_index']
        indexes = [
            HnswIndex(
                name='docchunk_embedding_hnsw_idx',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            )
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
