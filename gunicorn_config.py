from os import environ as env

workers = env.get("GC_WORKERS") or 1
timeout = env.get("GC_WORKER_TIMEOUT") or 600
bind = '0.0.0.0:5000'
loglevel = str.lower(env.get("LOG_LEVEL") or 'debug')
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
errorlog = '-'
