from django.contrib import admin

# Register your models here.
from .models import Document, VectorDatabase

admin.site.register(Document)
admin.site.register(VectorDatabase)