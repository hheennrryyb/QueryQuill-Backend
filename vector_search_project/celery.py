import os
from celery import Celery

# Add these lines
import multiprocessing
multiprocessing.set_start_method('spawn')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vector_search_project.settings')

app = Celery('vector_search_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()