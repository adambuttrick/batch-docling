import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import redis
from .config import get_config


class BatchStates:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BatchManager:
    def __init__(self):
        self.config = get_config()
        self.redis_client = redis.from_url(self.config.get_redis_url(), decode_responses=True)
        self.key_prefix = "docling_batch:"
    
    def _get_batch_key(self, batch_id: str) -> str:
        return f"{self.key_prefix}{batch_id}"
    
    def _get_tasks_key(self, batch_id: str) -> str:
        return f"{self.key_prefix}{batch_id}:tasks"
    
    def create_batch(self, batch_id: str, pdf_files: List[Path]) -> Dict[str, Any]:
        batch_key = self._get_batch_key(batch_id)
        
        batch_metadata = {
            "batch_id": batch_id,
            "status": BatchStates.PENDING,
            "total_files": len(pdf_files),
            "completed_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "start_time": None,
            "end_time": None,
            "files": [str(f) for f in pdf_files],
            "notes": None,
            "fallback_pending": 0
        }

        self.redis_client.set(batch_key, json.dumps(batch_metadata))
        return batch_metadata
    
    def update_batch_status(self, batch_id: str, status: str) -> None:
        batch_key = self._get_batch_key(batch_id)
        batch_data = self.get_batch_info(batch_id)
        
        if not batch_data:
            raise ValueError(f"Batch {batch_id} not found")
        
        batch_data["status"] = status
        if status == BatchStates.RUNNING and not batch_data.get("start_time"):
            batch_data["start_time"] = time.time()
        
        self.redis_client.set(batch_key, json.dumps(batch_data))
    
    def increment_completed(self, batch_id: str, success: bool = True) -> Dict[str, Any]:
        batch_key = self._get_batch_key(batch_id)
        batch_data = self.get_batch_info(batch_id)
        
        if not batch_data:
            raise ValueError(f"Batch {batch_id} not found")
        
        batch_data["completed_count"] += 1
        if success:
            batch_data["success_count"] += 1
        else:
            batch_data["failure_count"] += 1
        
        self.redis_client.set(batch_key, json.dumps(batch_data))
        return batch_data

    def increment_fallback_pending(self, batch_id: str) -> Dict[str, Any]:
        batch_key = self._get_batch_key(batch_id)
        batch_data = self.get_batch_info(batch_id)

        if not batch_data:
            raise ValueError(f"Batch {batch_id} not found")

        batch_data["fallback_pending"] = batch_data.get("fallback_pending", 0) + 1
        self.redis_client.set(batch_key, json.dumps(batch_data))
        return batch_data

    def decrement_fallback_pending(self, batch_id: str) -> Dict[str, Any]:
        batch_key = self._get_batch_key(batch_id)
        batch_data = self.get_batch_info(batch_id)

        if not batch_data:
            raise ValueError(f"Batch {batch_id} not found")

        fallback_pending = max(batch_data.get("fallback_pending", 0) - 1, 0)
        batch_data["fallback_pending"] = fallback_pending
        self.redis_client.set(batch_key, json.dumps(batch_data))
        return batch_data

    def get_batch_info(self, batch_id: str) -> Optional[Dict[str, Any]]:
        batch_key = self._get_batch_key(batch_id)
        batch_json = self.redis_client.get(batch_key)

        if not batch_json:
            return None
        
        return json.loads(batch_json)
    
    def add_task_to_batch(self, batch_id: str, task_id: str) -> None:
        tasks_key = self._get_tasks_key(batch_id)
        self.redis_client.sadd(tasks_key, task_id)
    
    def get_batch_tasks(self, batch_id: str) -> List[str]:
        tasks_key = self._get_tasks_key(batch_id)
        return list(self.redis_client.smembers(tasks_key))
    
    def finalize_batch(self, batch_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        batch_key = self._get_batch_key(batch_id)
        batch_data = self.get_batch_info(batch_id)
        
        if not batch_data:
            raise ValueError(f"Batch {batch_id} not found")
        
        batch_data["status"] = BatchStates.COMPLETED
        batch_data["end_time"] = time.time()
        if notes:
            batch_data["notes"] = notes
        
        self.redis_client.set(batch_key, json.dumps(batch_data))
        return batch_data
    
    def get_batch_progress(self, batch_id: str) -> Dict[str, Any]:
        batch_data = self.get_batch_info(batch_id)
        
        if not batch_data:
            return {"error": f"Batch {batch_id} not found"}
        
        total = batch_data["total_files"]
        completed = batch_data["completed_count"]

        progress = {
            "batch_id": batch_id,
            "status": batch_data["status"],
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "completed": completed,
            "total": total,
            "success_count": batch_data["success_count"],
            "failure_count": batch_data["failure_count"],
            "fallback_pending": batch_data.get("fallback_pending", 0)
        }

        if batch_data.get("start_time"):
            progress["elapsed_time"] = time.time() - batch_data["start_time"]

        return progress
    
    def cancel_batch(self, batch_id: str) -> None:
        self.update_batch_status(batch_id, BatchStates.CANCELLED)
    
    def delete_batch(self, batch_id: str) -> bool:
        batch_key = self._get_batch_key(batch_id)
        tasks_key = self._get_tasks_key(batch_id)
        
        pipe = self.redis_client.pipeline()
        pipe.delete(batch_key)
        pipe.delete(tasks_key)
        results = pipe.execute()
        
        return any(results)
    
    def list_batches(self, pattern: str = "*") -> List[str]:
        search_pattern = f"{self.key_prefix}{pattern}"
        batch_ids = []
        for key in self.redis_client.scan_iter(match=search_pattern):
            if ":tasks" not in key:
                batch_ids.append(key.replace(self.key_prefix, ""))
        return batch_ids
    
    def batch_exists(self, batch_id: str) -> bool:
        batch_key = self._get_batch_key(batch_id)
        return bool(self.redis_client.exists(batch_key))


_batch_manager_instance: Optional[BatchManager] = None


def get_batch_manager() -> BatchManager:
    global _batch_manager_instance
    if _batch_manager_instance is None:
        _batch_manager_instance = BatchManager()
    return _batch_manager_instance
