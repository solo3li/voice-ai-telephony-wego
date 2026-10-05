from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from pgvector.django import VectorExtension, VectorField, HnswIndex

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        VectorExtension(),
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('file', models.FileField(upload_to='documents/%Y/%m/%d/')),
                ('file_type', models.CharField(blank=True, max_length=50)),
                ('file_size', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DocumentChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk_index', models.IntegerField(default=0)),
                ('content', models.TextField()),
                ('embedding', VectorField(dimensions=768)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='voice_assistant.document')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_chunks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['chunk_index'],
                'indexes': [
                    HnswIndex(ef_construction=64, fields=['embedding'], m=16, name='docchunk_embedding_hnsw_idx', opclasses=['vector_cosine_ops']),
                ],
            },
        ),
    ]
