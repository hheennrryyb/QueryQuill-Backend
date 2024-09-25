import os
from celery import Celery
import multiprocessing
import logging
# Set the start method to 'forkserver'
multiprocessing.set_start_method('forkserver', force=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vector_search_project.settings')

app = Celery('vector_search_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Set up logging
logger = logging.getLogger('celery')
handler = logging.FileHandler('/var/log/celery/celery.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)