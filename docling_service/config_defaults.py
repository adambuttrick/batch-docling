DEFAULT_CONFIG = {
    "redis": {
        "url": "redis://localhost:6379/0"
    },
    "celery": {
        "task_soft_time_limit": 30,
        "task_time_limit": 36,
        "worker_max_tasks_per_child": 1,
        "worker_prefetch_multiplier": 1,
        "task_acks_late": True,
        "audit_delay_seconds": 36
    },
    "directories": {
        "test_small": "tests/sample_pdfs",
        "test_medium": "test_medium",
        "test_large": "test_large",
        "benchmarks": "benchmarks",
        "default_output": "./markdown_results",
        "config_home": ".config/docling"
    },
    "files": {
        "baseline": "benchmarks/baseline.json",
        "job_id": "latest_job.id"
    },
    "benchmarks": {
        "memory_check_interval": 0.1,
        "metrics_to_check": ["execution_time", "pages_per_second", "memory_delta"]
    },
    "regression": {
        "threshold_percent": 10.0,
        "fail_on_regression": True
    },
    "monitoring": {
        "status_check_interval": 2,
        "progress_display_refresh": 0.1,
        "monitor_poll_seconds": 120,
        "task_timeout_profiles": {
            "standard": {
                "soft_seconds": 600,
                "hard_seconds": 1200,
                "max_retries": 1
            },
            "vlm": {
                "soft_seconds": 1800,
                "hard_seconds": 3600,
                "max_retries": 1
            }
        }
    },
    "accelerator": {
        "standard_device": "auto",
        "vlm_device": "auto",
        "prefer_mps": True,
        "prefer_cuda": True,
        "num_threads": 4
    },
    "vlm_fallback": {
        "enabled": False,
        "queue_name": "vlm_pdf",
        "model": "GRANITE_VISION_TRANSFORMERS",
        "primary_mode": "standard",
        "granite_mlx_repo": "ibm-granite/granite-vision-3.2-2b-mlx",
        "artifacts_path": None,
        "enable_remote_services": False,
        "force_backend_text": False,
        "images_scale": 2.0,
        "generate_page_images": True,
        "generate_picture_images": False,
        "worker_concurrency": 1
    },
    "daemon": {
        "watch_directory": "./data/input",
        "scan_interval": 10,
        "processed_dirs_file": ".processed_directories.json",
        "daemon_pid_file": "daemon.pid",
        "shutdown_timeout": 30,
        "output_base_dir": "./data/output"
    }
}
