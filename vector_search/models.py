from django.db import models
from django.contrib.auth.models import User
import uuid

def short_uuid():
    return uuid.uuid4().hex[:8]

# Create your models here.
class Document(models.Model):
    document_id = models.CharField(max_length=8, primary_key=True, default=short_uuid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    vector_database = models.ForeignKey('VectorDatabase', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.file.name} : {self.uploaded_at}"

class VectorDatabase(models.Model):
    project_id = models.CharField(max_length=8, primary_key=True, default=short_uuid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default='Untitled')
    index_file = models.FileField(upload_to='vector_dbs/')
    chunks_file = models.FileField(upload_to='vector_dbs/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    documents = models.ManyToManyField(Document, related_name='vector_databases')

    def __str__(self):
        return f"{self.user.username} - {self.name} : {self.created_at}"