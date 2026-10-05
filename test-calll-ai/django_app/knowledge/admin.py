from django.contrib import admin
from .models import Document, DocumentChunk

class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    fields = ('chunk_index', 'content_preview', 'created_at')
    readonly_fields = ('chunk_index', 'content_preview', 'created_at')
    can_delete = True

    def content_preview(self, obj):
        return (obj.content[:120] + "...") if obj.content and len(obj.content) > 120 else obj.content
    content_preview.short_description = "محتوى المقطع"

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'file_type', 'file_size_display', 'chunks_count', 'created_at')
    list_filter = ('file_type', 'created_at', 'user')
    search_fields = ('title', 'user__username')
    readonly_fields = ('created_at',)
    inlines = [DocumentChunkInline]

    def file_size_display(self, obj):
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        return f"{obj.file_size / (1024 * 1024):.2f} MB"
    file_size_display.short_description = "حجم الملف"

    def chunks_count(self, obj):
        return obj.chunks.count()
    chunks_count.short_description = "عدد المقاطع"

@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'user', 'chunk_index', 'content_preview', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('content', 'document__title', 'user__username')
    readonly_fields = ('created_at',)

    def content_preview(self, obj):
        return (obj.content[:100] + "...") if obj.content and len(obj.content) > 100 else obj.content
    content_preview.short_description = "محتوى المقطع"
