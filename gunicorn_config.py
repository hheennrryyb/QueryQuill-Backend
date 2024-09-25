import multiprocessing
import os

# Bind to 0.0.0.0 to allow external connections
bind = "0.0.0.0:" + os.environ.get("PORT", "8000")

# Number of worker processes
# A good rule of thumb is (2 x number_of_cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class
worker_class = 'gevent'

# Maximum number of simultaneous clients
worker_connections = 1000

# Maximum number of requests a worker will process before restarting
max_requests = 1000
max_requests_jitter = 50

# Timeout for graceful workers restart
graceful_timeout = 30

# Timeout for worker processes
timeout = 30

# Log level
loglevel = 'info'

# Access log format
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Error log
errorlog = '-'

# Preload app code before forking worker processes
preload_app = True

# Daemonize the Gunicorn process (run in background)
daemon = False

# Enable debugging mode
debug = False

# Limit the allowed request line length
limit_request_line = 4094

# Limit the allowed size of request headers
limit_request_fields = 100
limit_request_field_size = 8190