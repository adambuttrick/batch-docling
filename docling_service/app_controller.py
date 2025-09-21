import os
import uuid
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

from .batch_manager import get_batch_manager, BatchStates
from .tasks import process_pdf, audit_batch_status
from .celery_app import celery_app
from .config import get_config


class AppController:
    def __init__(self):
        self.config = get_config()
        self.batch_manager = get_batch_manager()

    def process_batch(self, input_dir: str, output_dir: str, batch_id: Optional[str] = None) -> Dict[str, Any]:
        if not os.path.isdir(input_dir):
            raise FileNotFoundError(f"Input directory '{input_dir}' does not exist")

        pdf_files = [
            Path(input_dir) / f for f in os.listdir(input_dir)
            if f.lower().endswith('.pdf')
        ]

        if not pdf_files:
            raise ValueError(f"No PDF files found in '{input_dir}'")

        os.makedirs(output_dir, exist_ok=True)
        if not os.access(output_dir, os.W_OK):
            raise PermissionError(f"Output directory '{output_dir}' is not writable")

        if not batch_id:
            batch_id = str(uuid.uuid4())

        batch_info = self.batch_manager.create_batch(batch_id, pdf_files)

        try:
            self.dispatch_batch_tasks(batch_id, pdf_files, output_dir)
            self.batch_manager.update_batch_status(
                batch_id, BatchStates.RUNNING)

            audit_delay = self.config.get("celery", "audit_delay_seconds", 36)
            self.schedule_batch_audit(batch_id, audit_delay)

            return {
                "batch_id": batch_id,
                "total_files": len(pdf_files),
                "status": BatchStates.RUNNING,
                "output_dir": output_dir
            }

        except Exception as e:
            self.batch_manager.update_batch_status(
                batch_id, BatchStates.CANCELLED)
            raise e

    def dispatch_batch_tasks(self, batch_id: str, pdf_files: List[Path], output_dir: str) -> List[str]:
        task_ids = []

        for pdf_path in pdf_files:
            task = process_pdf.delay(
                str(pdf_path), output_dir=output_dir, batch_id=batch_id)
            task_ids.append(task.id)
            self.batch_manager.add_task_to_batch(batch_id, task.id)

        return task_ids

    def monitor_batch(self, batch_id: str, watch: bool = False) -> Dict[str, Any]:
        if not self.batch_manager.batch_exists(batch_id):
            raise ValueError(f"Batch {batch_id} not found")

        if watch:
            return self._watch_batch_status(batch_id)
        else:
            return self.get_batch_status(batch_id)

    def _watch_batch_status(self, batch_id: str) -> Dict[str, Any]:
        while True:
            try:
                status = self.get_batch_status(batch_id)

                completed = status.get("completed", 0)
                total = status.get("total", 0)
                batch_status = status.get("status", "UNKNOWN")

                print(f"Progress: {completed}/{total} tasks completed", end='\r')

                if batch_status in [BatchStates.COMPLETED, BatchStates.CANCELLED]:
                    print(f"\nBatch {batch_status.lower()}! Final status: {completed}/{total} tasks completed.")
                    break

                time.sleep(self.config.get(
                    "monitoring", "status_check_interval", 2))

            except KeyboardInterrupt:
                print("\nStatus monitoring interrupted.")
                break
            except Exception as e:
                print(f"\nError checking status: {e}")
                break

        return self.get_batch_status(batch_id)

    def cancel_batch(self, batch_id: str) -> Dict[str, Any]:
        if not self.batch_manager.batch_exists(batch_id):
            raise ValueError(f"Batch {batch_id} not found")

        task_ids = self.batch_manager.get_batch_tasks(batch_id)

        if task_ids:
            celery_app.control.revoke(
                task_ids, terminate=True, signal='SIGKILL')

        self.batch_manager.cancel_batch(batch_id)

        return {
            "batch_id": batch_id,
            "status": BatchStates.CANCELLED,
            "cancelled_tasks": len(task_ids)
        }

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        batch_info = self.batch_manager.get_batch_info(batch_id)

        if not batch_info:
            return {"error": f"Batch {batch_id} not found"}

        progress = self.batch_manager.get_batch_progress(batch_id)

        return {
            "batch_id": batch_id,
            "status": batch_info["status"],
            "total": batch_info["total_files"],
            "completed": batch_info["completed_count"],
            "success": batch_info["success_count"],
            "failures": batch_info["failure_count"],
            "progress_percent": progress["progress_percent"],
            "elapsed_time": progress.get("elapsed_time"),
            "notes": batch_info.get("notes")
        }

    def schedule_batch_audit(self, batch_id: str, delay_seconds: int) -> str:
        task = audit_batch_status.apply_async(
            args=[batch_id], countdown=delay_seconds)
        return task.id

    def get_batch_timing_report(self, batch_id: str) -> Dict[str, Any]:
        batch_info = self.batch_manager.get_batch_info(batch_id)

        if not batch_info:
            return {"error": f"Batch {batch_id} not found"}

        status = batch_info["status"]

        if status not in [BatchStates.COMPLETED, BatchStates.CANCELLED]:
            return {
                "batch_id": batch_id,
                "status": status,
                "message": "Batch has not completed yet",
                "notes": batch_info.get("notes")
            }

        start_time = batch_info.get("start_time", 0)
        end_time = batch_info.get("end_time", time.time())
        duration = end_time - start_time if start_time else 0

        summary_text = (
            f"Batch summary complete. "
            f"Success: {batch_info.get('success_count', 'N/A')}, "
            f"Failures: {batch_info.get('failure_count', 'N/A')}"
        )

        return {
            "batch_id": batch_id,
            "status": status,
            "total_tasks": batch_info.get("total_files", "N/A"),
            "success": batch_info.get("success_count", "N/A"),
            "failures": batch_info.get("failure_count", "N/A"),
            "summary": summary_text,
            "notes": batch_info.get("notes"),
            "duration": duration
        }


_controller_instance: Optional[AppController] = None


def get_app_controller() -> AppController:
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = AppController()
    return _controller_instance


def process_batch(input_dir: str, output_dir: str, batch_id: Optional[str] = None) -> Dict[str, Any]:
    return get_app_controller().process_batch(input_dir, output_dir, batch_id)


def dispatch_batch_tasks(batch_id: str, pdf_files: List[Path], output_dir: str) -> List[str]:
    return get_app_controller().dispatch_batch_tasks(batch_id, pdf_files, output_dir)


def monitor_batch(batch_id: str, watch: bool = False) -> Dict[str, Any]:
    return get_app_controller().monitor_batch(batch_id, watch)


def cancel_batch(batch_id: str) -> Dict[str, Any]:
    return get_app_controller().cancel_batch(batch_id)


def get_batch_status(batch_id: str) -> Dict[str, Any]:
    return get_app_controller().get_batch_status(batch_id)


def schedule_batch_audit(batch_id: str, delay_seconds: int) -> str:
    return get_app_controller().schedule_batch_audit(batch_id, delay_seconds)


def get_batch_timing_report(batch_id: str) -> Dict[str, Any]:
    return get_app_controller().get_batch_timing_report(batch_id)
