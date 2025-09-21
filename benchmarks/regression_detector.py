import json
import sys
from pathlib import Path
from typing import Dict, Optional


class RegressionDetector:
    def __init__(self, baseline_path: str = "benchmarks/baseline.json", 
                 threshold_percent: float = 10.0):
        if threshold_percent < 0:
            raise ValueError("Threshold percent cannot be negative")
        self.baseline_path = baseline_path
        self.threshold_percent = threshold_percent
        self.metrics_to_check = ["execution_time", "pages_per_second", "memory_delta"]
    
    def load_baseline(self) -> Optional[Dict]:
        baseline_file = Path(self.baseline_path)
        if not baseline_file.exists():
            return None
        try:
            with open(baseline_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load baseline file: {e}", file=sys.stderr)
            return None
    
    def validate_baseline(self, baseline: Dict) -> bool:
        if not isinstance(baseline, dict):
            return False
        for component in baseline.values():
            if not isinstance(component, dict):
                continue
            for file_data in component.values():
                if not isinstance(file_data, dict) or file_data.get("status") != "success":
                    continue
                required_metrics = ["execution_time", "pages_per_second"]
                if not all(metric in file_data for metric in required_metrics):
                    return False
        return True
    
    def calculate_regression_percentage(self, current: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return ((current - baseline) / baseline) * 100
    
    def is_metric_regression(self, metric: str, current: float, baseline: float) -> bool:
        change_percent = self.calculate_regression_percentage(current, baseline)
        if metric == "execution_time" or metric == "memory_delta":
            return change_percent > self.threshold_percent
        elif metric == "pages_per_second":
            return change_percent < -self.threshold_percent
        return False
    
    def detect_regressions(self, current_results: Dict) -> Dict:
        baseline = self.load_baseline()
        if not baseline:
            return {"error": "baseline_not_found", "message": "No baseline file found"}
        
        if not self.validate_baseline(baseline):
            return {"error": "invalid_baseline", "message": "Baseline data is invalid"}
        
        regressions = {"components": {}, "summary": {"total_regressions": 0, "has_regressions": False}}
        
        for component, current_data in current_results.items():
            if component not in baseline:
                continue
                
            component_regressions = {}
            baseline_component = baseline[component]
            
            for file_name, current_metrics in current_data.items():
                if file_name not in baseline_component:
                    continue
                    
                baseline_metrics = baseline_component[file_name]
                
                if (current_metrics.get("status") != "success" or 
                    baseline_metrics.get("status") != "success"):
                    continue
                
                file_regressions = []
                
                for metric in self.metrics_to_check:
                    if metric in current_metrics and metric in baseline_metrics:
                        current_val = current_metrics[metric]
                        baseline_val = baseline_metrics[metric]
                        
                        if current_val is None or baseline_val is None:
                            continue
                        
                        if baseline_val != 0 and self.is_metric_regression(metric, current_val, baseline_val):
                            change_percent = self.calculate_regression_percentage(current_val, baseline_val)
                            file_regressions.append({
                                "metric": metric,
                                "current": current_val,
                                "baseline": baseline_val,
                                "change_percent": change_percent,
                                "threshold": self.threshold_percent
                            })
                
                if file_regressions:
                    component_regressions[file_name] = file_regressions
                    regressions["summary"]["total_regressions"] += len(file_regressions)
            
            if component_regressions:
                regressions["components"][component] = component_regressions
        
        regressions["summary"]["has_regressions"] = regressions["summary"]["total_regressions"] > 0
        return regressions
    
    def format_regression_report(self, regressions: Dict, format_type: str = "text") -> str:
        if format_type == "json":
            return json.dumps(regressions, indent=2)
        
        if "error" in regressions:
            return f"Error: {regressions['message']}"
        
        summary = regressions["summary"]
        report = []
        
        if not summary["has_regressions"]:
            report.append("No performance regressions detected.")
            return "\n".join(report)
        
        report.append(f"REGRESSION DETECTED: {summary['total_regressions']} issues found")
        report.append(f"Threshold: {self.threshold_percent}%")
        report.append("")
        
        for component, files in regressions["components"].items():
            report.append(f"Component: {component}")
            for file_name, file_regressions in files.items():
                report.append(f"  File: {file_name}")
                for regression in file_regressions:
                    metric = regression["metric"]
                    change = regression["change_percent"]
                    current = regression["current"]
                    baseline = regression["baseline"]
                    report.append(f"    {metric}: {change:+.1f}% ({baseline:.3f} -> {current:.3f})")
                report.append("")
        
        return "\n".join(report)