# gunicorn.conf.py
bind = "0.0.0.0:10000"
workers = 1
worker_class = "sync"
timeout = 300  # 5 minutes au lieu de 30 secondes
preload_app = True
max_requests = 1000
max_requests_jitter = 100