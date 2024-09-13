from django.db import models

# Create your models here.
from django.contrib.auth.models import User

class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

class VectorDatabase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    index_file = models.FileField(upload_to='vector_dbs/')
    chunks_file = models.FileField(upload_to='vector_dbs/')
    created_at = models.DateTimeField(auto_now_add=True)