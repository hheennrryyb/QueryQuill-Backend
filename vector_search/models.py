from django.db import models
from django.contrib.auth.models import User
import uuid
import os
from django.db.models.signals import post_delete
from django.dispatch import receiver

def short_uuid():
    return uuid.uuid4().hex[:8]

def user_directory_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/documents/user_<id>/project_<id>/<filename>
    return f'documents/user_{instance.user.id}/project_{instance.vector_database.project_id}/{filename}'

# Create your models here.
class Document(models.Model):
    document_id = models.CharField(max_length=8, primary_key=True, default=short_uuid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to=user_directory_path, max_length=255)  # Increase max_length 
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    vector_database = models.ForeignKey('VectorDatabase', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.file.name} : {self.uploaded_at}"

    def delete(self, *args, **kwargs):
        self.delete_file()
        super(Document, self).delete(*args, **kwargs)

    def delete_file(self):
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)

@receiver(post_delete, sender=Document)
def delete_document_file(sender, instance, **kwargs):
    instance.delete_file()

class VectorDatabase(models.Model):
    project_id = models.CharField(max_length=8, primary_key=True, default=short_uuid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default='Untitled')
    description = models.TextField(default='')
    approvedDomains = models.TextField(default='')
    introPrompt = models.TextField(default='I\'m a helpful assistant. How can I help you today?')
    index_file = models.FileField(upload_to='vector_dbs/')
    chunks_file = models.FileField(upload_to='vector_dbs/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    documents = models.ManyToManyField(Document, related_name='vector_databases')

    def __str__(self):
        return f"{self.user.username} - {self.name} : {self.created_at}"

    def delete(self, *args, **kwargs):
        self.delete_files()
        super(VectorDatabase, self).delete(*args, **kwargs)

    def delete_files(self):
        for field in [self.index_file, self.chunks_file]:
            if field:
                if os.path.isfile(field.path):
                    os.remove(field.path)

@receiver(post_delete, sender=VectorDatabase)
def delete_vector_database_files(sender, instance, **kwargs):
    instance.delete_files()

@receiver(post_delete, sender=User)
def delete_user_files(sender, instance, **kwargs):
    # Delete Document files
    for document in Document.objects.filter(user=instance):
        document.delete_file()
    
    # Delete VectorDatabase files
    for vector_db in VectorDatabase.objects.filter(user=instance):
        vector_db.delete_files()