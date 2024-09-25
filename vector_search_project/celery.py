import os
from celery import Celery
import multiprocessing

# Set the start method to 'forkserver'
multiprocessing.set_start_method('forkserver', force=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vector_search_project.settings')

app = Celery('vector_search_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()