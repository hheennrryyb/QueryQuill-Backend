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
app.conf.worker_pool = 'gevent'
app.conf.worker_concurrency = 4  # Adjust based on your system's capabilities

# Add this line to address the deprecation warning
app.conf.broker_connection_retry_on_startup = True

# Create a logs directory in your project
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)

# Set up logging
logger = logging.getLogger('celery')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(os.path.join(log_dir, 'celery.log'))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
