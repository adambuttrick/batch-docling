import os
from pathlib import Path
from celery import Celery

if Path("config.local.yaml").exists():
    from .config import reload_config
    reload_config("config.local.yaml")
elif Path("config.yaml").exists():
    from .config import reload_config
    reload_config("config.yaml")

from .config import get_config

config = get_config()
REDIS_URL = config.get_redis_url()
celery_config = config.get_celery_config()

celery_app = Celery(
    'docling_tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['docling_service.tasks']
)

celery_app.conf.update(
    worker_max_tasks_per_child=celery_config.get('worker_max_tasks_per_child', 1),

    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    task_soft_time_limit=celery_config.get('task_soft_time_limit', 30),
    task_time_limit=celery_config.get('task_time_limit', 36),

    task_acks_late=celery_config.get('task_acks_late', True),
    
    worker_prefetch_multiplier=celery_config.get('worker_prefetch_multiplier', 1),
)