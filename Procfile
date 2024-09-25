web: gunicorn vector_search_project.wsgi:application --config gunicorn_config.py
worker: celery -A vector_search_project worker --loglevel=info --pool=solo