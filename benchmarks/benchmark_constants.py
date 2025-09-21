from enum import Enum
from typing import Dict


class BenchmarkStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"


class RegressionDirection(Enum):
    HIGHER_IS_WORSE = "higher_worse"
    LOWER_IS_WORSE = "lower_worse"


BENCHMARK_METRICS = [
    "execution_time",
    "pages_per_second", 
    "time_per_page",
    "memory_delta",
    "total_pages",
    "kept_pages",
    "skipped_pages"
]

REGRESSION_METRICS = [
    "execution_time",
    "pages_per_second",
    "memory_delta"
]

PERFORMANCE_METRIC_DIRECTIONS: Dict[str, RegressionDirection] = {
    "execution_time": RegressionDirection.HIGHER_IS_WORSE,
    "memory_delta": RegressionDirection.HIGHER_IS_WORSE,
    "pages_per_second": RegressionDirection.LOWER_IS_WORSE,
    "time_per_page": RegressionDirection.HIGHER_IS_WORSE
}

REQUIRED_SUCCESS_METRICS = [
    "execution_time",
    "pages_per_second"
]

MEMORY_UNITS = {
    "BYTES_PER_MB": 1024 * 1024,
    "BYTES_PER_KB": 1024
}

TEST_SIZE_LIMITS = {
    "small": 3,
    "medium": 5, 
    "large": 10
}

MONITORING_INTERVALS = {
    "MEMORY_CHECK": 0.1,
    "PROGRESS_DISPLAY": 0.1,
    "STATUS_POLL": 2
}

OUTPUT_FORMATS = {
    "JSON": "json",
    "TEXT": "text"
}