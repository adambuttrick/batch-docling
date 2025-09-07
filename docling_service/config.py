import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML is required for config file parsing. Install via: pip install pyyaml")


class Config:
    def __init__(self, config_file: str = "config.yaml"):
        self._config_file = config_file
        self._config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        from .config_defaults import DEFAULT_CONFIG
        default_config = DEFAULT_CONFIG
        
        config_path = Path(self._config_file)
        if not config_path.exists():
            return self._apply_env_overrides(default_config)
        
        try:
            with open(config_path, 'r') as f:
                file_config = yaml.safe_load(f) or {}
            merged_config = self._merge_configs(default_config, file_config)
            return self._apply_env_overrides(merged_config)
        except (yaml.YAMLError, IOError):
            return self._apply_env_overrides(default_config)
    
    def _merge_configs(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = default.copy()
        for key, value in override.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        env_mappings = {
            "REDIS_URL": ("redis", "url"),
            "CELERY_TASK_SOFT_TIME_LIMIT": ("celery", "task_soft_time_limit"),
            "CELERY_TASK_TIME_LIMIT": ("celery", "task_time_limit"),
            "WORKER_MAX_TASKS_PER_CHILD": ("celery", "worker_max_tasks_per_child"),
            "WORKER_PREFETCH_MULTIPLIER": ("celery", "worker_prefetch_multiplier"),
            "AUDIT_DELAY_SECONDS": ("celery", "audit_delay_seconds"),
            "TEST_SMALL_DIR": ("directories", "test_small"),
            "TEST_MEDIUM_DIR": ("directories", "test_medium"),
            "TEST_LARGE_DIR": ("directories", "test_large"),
            "BENCHMARKS_DIR": ("directories", "benchmarks"),
            "DEFAULT_OUTPUT_DIR": ("directories", "default_output"),
            "BASELINE_FILE": ("files", "baseline"),
            "REGRESSION_THRESHOLD": ("regression", "threshold_percent"),
            "STATUS_CHECK_INTERVAL": ("monitoring", "status_check_interval"),
            "WATCH_DIRECTORY": ("daemon", "watch_directory"),
            "SCAN_INTERVAL": ("daemon", "scan_interval"),
            "PROCESSED_DIRS_FILE": ("daemon", "processed_dirs_file"),
            "DAEMON_PID_FILE": ("daemon", "daemon_pid_file"),
            "SHUTDOWN_TIMEOUT": ("daemon", "shutdown_timeout")
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    if key in ["task_soft_time_limit", "task_time_limit", "worker_max_tasks_per_child", 
                              "worker_prefetch_multiplier", "audit_delay_seconds", "status_check_interval", "scan_interval", "shutdown_timeout"]:
                        config[section][key] = int(value)
                    elif key in ["threshold_percent"]:
                        config[section][key] = float(value)
                    elif key in ["task_acks_late", "fail_on_regression"]:
                        config[section][key] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        config[section][key] = value
                except (ValueError, TypeError):
                    logging.warning(
                        f"Could not parse environment variable {env_var} with value '{value}'. "
                        f"Using default or config file value instead."
                    )
        
        return config
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._config.get(section, {}).get(key, default)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        return self._config.get(section, {})
    
    def get_redis_url(self) -> str:
        return self.get("redis", "url")
    
    def get_baseline_path(self) -> Path:
        return Path(self.get("files", "baseline"))
    
    def get_test_dir(self, size: str = "small") -> Path:
        return Path(self.get("directories", f"test_{size}"))
    
    def get_benchmarks_dir(self) -> Path:
        return Path(self.get("directories", "benchmarks"))
    
    def get_default_output_dir(self) -> Path:
        return Path(self.get("directories", "default_output"))
    
    def get_config_home(self) -> Path:
        home_dir = Path.home()
        config_rel_path = self.get("directories", "config_home")
        return home_dir / config_rel_path
    
    def get_job_id_path(self) -> Path:
        config_dir = self.get_config_home()
        job_id_file = self.get("files", "job_id")
        return config_dir / job_id_file
    
    def get_regression_threshold(self) -> float:
        return self.get("regression", "threshold_percent")
    
    def get_celery_config(self) -> Dict[str, Any]:
        return self.get_section("celery")
    
    def _validate_config(self) -> None:
        threshold = self.get_regression_threshold()
        if threshold < 0:
            raise ValueError("Configuration error: regression.threshold_percent cannot be negative")
        
        soft_limit = self.get("celery", "task_soft_time_limit")
        hard_limit = self.get("celery", "task_time_limit")
        if soft_limit > 0 and hard_limit > 0 and soft_limit >= hard_limit:
            raise ValueError("Configuration error: celery.task_soft_time_limit must be less than task_time_limit")


_config_instance: Optional[Config] = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config(config_file: str = "config.yaml"):
    global _config_instance
    _config_instance = Config(config_file)