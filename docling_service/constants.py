from enum import Enum


class JobStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class TaskStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


JOB_FIELDS = [
    "total_tasks",
    "completed_count", 
    "success_count",
    "failure_count",
    "start_time",
    "status",
    "notes"
]

REDIS_KEY_PATTERNS = {
    "JOB": "docling_job:{job_id}",
    "TASK_IDS": "docling_job:{job_id}:task_ids",
    "TASK_RESULT": "task:{task_id}:result"
}

SIGNAL_TYPES = {
    "SIGKILL": "SIGKILL",
    "SIGTERM": "SIGTERM"
}

COMPONENT_NAMES = [
    "sanitize_pdf",
    "process_pdf"
]