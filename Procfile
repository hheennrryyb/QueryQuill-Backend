web: gunicorn vector_search_project.wsgi:application --config gunicorn_config.py
worker: celery -A vector_search_project worker --loglevel=info --max-memory-per-child=500000 --max-tasks-per-child=10