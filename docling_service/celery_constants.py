CELERY_SERIALIZATION_SETTINGS = {
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"]
}

CELERY_RELIABILITY_SETTINGS = {
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "worker_max_tasks_per_child": 1
}

DEFAULT_TIMEOUTS = {
    "REDIS_PING": 5,
    "TASK_COMPLETION": 300,
    "STATUS_CHECK": 30
}

FILE_EXTENSIONS = {
    "PDF": ".pdf",
    "JSON": ".json",
    "YAML": ".yaml",
    "YML": ".yml"
}