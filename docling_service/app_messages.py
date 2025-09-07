ERROR_MESSAGES = {
    "BASELINE_NOT_FOUND": "No baseline file found",
    "INVALID_BASELINE": "Baseline data is invalid", 
    "JOB_NOT_FOUND": "Could not find job with ID",
    "REDIS_CONNECTION_ERROR": "Could not connect to Redis",
    "DIRECTORY_NOT_FOUND": "Directory does not exist",
    "DIRECTORY_NOT_WRITABLE": "Directory is not writable",
    "NO_PDF_FILES": "No PDF files found",
    "NEGATIVE_THRESHOLD": "Threshold percent cannot be negative",
    "YAML_DEPENDENCY_MISSING": "PyYAML is required for config file parsing. Install via: pip install pyyaml"
}

SUCCESS_MESSAGES = {
    "BASELINE_SAVED": "Baseline saved to",
    "JOB_DISPATCHED": "Job dispatched successfully",
    "JOB_COMPLETED": "Job completed successfully",
    "JOB_CANCELLED": "Job has been cancelled",
    "NO_REGRESSIONS": "No performance regressions detected"
}