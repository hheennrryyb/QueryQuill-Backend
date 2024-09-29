from django.contrib import admin
from .models import Document, VectorDatabase

class DocumentAdmin(admin.ModelAdmin):
    list_display = ('document_id', 'user', 'file', 'uploaded_at', 'processed')
    list_filter = ('processed', 'uploaded_at')
    search_fields = ('document_id', 'user__username', 'file')

class VectorDatabaseAdmin(admin.ModelAdmin):
    list_display = ('project_id', 'user', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('project_id', 'user__username', 'name')

admin.site.register(Document, DocumentAdmin)
admin.site.register(VectorDatabase, VectorDatabaseAdmin)