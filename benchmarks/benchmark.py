import gc
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

try:
    import psutil
except ImportError:
    psutil = None


class BenchmarkRunner:
    def __init__(self, test_dir: str = "tests/sample_pdfs", baseline_path: str = "benchmarks/baseline.json"):
        self.baseline_path = baseline_path
        self.test_pdfs = self._discover_test_pdfs(test_dir)
        
    def _discover_test_pdfs(self, test_dir: str) -> List[str]:
        test_path = Path(test_dir)
        return [str(p) for p in test_path.glob("*.pdf")] if test_path.exists() else []
    
    def _get_memory_usage(self) -> Optional[float]:
        if not psutil:
            return None
        gc.collect()
        return psutil.Process().memory_info().rss / (1024 * 1024)
    
    def _create_success_result(self, execution_time: float, memory_delta: Optional[float], 
                             total_pages: int, kept_pages: int, skipped_pages: int) -> Dict:
        result = {
            "status": "success", "execution_time": execution_time, "total_pages": total_pages,
            "kept_pages": kept_pages, "skipped_pages": skipped_pages,
            "pages_per_second": total_pages / execution_time if execution_time > 0 else 0,
            "time_per_page": execution_time / total_pages if total_pages > 0 else 0
        }
        if memory_delta is not None:
            result["memory_delta"] = memory_delta
        return result
    
    def _benchmark_sanitize_pdf(self, pdf_path: str) -> Dict:
        from docling_service.tasks import sanitize_pdf
        
        memory_before = self._get_memory_usage()
        start_time = time.perf_counter()
        
        try:
            sanitized_path, kept_pages, skipped_pages = sanitize_pdf(pdf_path)
            end_time = time.perf_counter()
            memory_after = self._get_memory_usage()
            
            if os.path.exists(sanitized_path):
                os.remove(sanitized_path)
            
            total_pages = kept_pages + skipped_pages
            execution_time = end_time - start_time
            memory_delta = (memory_after - memory_before) if memory_before and memory_after else None
            
            return self._create_success_result(execution_time, memory_delta, total_pages, kept_pages, skipped_pages)
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "execution_time": time.perf_counter() - start_time
            }
    
    def _benchmark_process_pdf(self, pdf_path: str) -> Dict:
        from docling_service.tasks import _process_pdf_logic
        
        memory_before = self._get_memory_usage()
        start_time = time.perf_counter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                job_id = f"benchmark_{uuid.uuid4().hex[:8]}"
                result = _process_pdf_logic(pdf_path, temp_dir, job_id, "benchmark_task")
                
                end_time = time.perf_counter()
                memory_after = self._get_memory_usage()
                
                execution_time = end_time - start_time
                memory_delta = (memory_after - memory_before) if memory_before and memory_after else None
                
                if isinstance(result, dict) and result.get("status") == "SUCCESS":
                    pages_kept = result.get("pages_kept", 0)
                    pages_skipped = result.get("pages_skipped", 0)
                    total_pages = pages_kept + pages_skipped
                    
                    return self._create_success_result(execution_time, memory_delta, total_pages, pages_kept, pages_skipped)
                else:
                    return {"status": "error", "error": "Task failed", "execution_time": execution_time}
                    
            except Exception as e:
                return {"status": "error", "error": str(e), "execution_time": time.perf_counter() - start_time}
    
    def run_benchmarks(self) -> Dict:
        return {
            "sanitize_pdf": {os.path.basename(pdf): self._benchmark_sanitize_pdf(pdf) for pdf in self.test_pdfs},
            "process_pdf": {os.path.basename(pdf): self._benchmark_process_pdf(pdf) for pdf in self.test_pdfs}
        }
    
    def save_baseline(self, results: Dict) -> None:
        os.makedirs(os.path.dirname(self.baseline_path), exist_ok=True)
        with open(self.baseline_path, 'w') as f:
            json.dump(results, f, indent=2)
    
    def load_baseline(self) -> Optional[Dict]:
        return json.load(open(self.baseline_path, 'r')) if os.path.exists(self.baseline_path) else None
    
    def compare_to_baseline(self, current_results: Dict) -> Dict:
        baseline = self.load_baseline()
        if not baseline:
            return {"error": "No baseline found"}
        comparison = {}
        for component, current_data in current_results.items():
            if component in baseline:
                comparison[component] = {}
                for file_name, current_metrics in current_data.items():
                    if file_name in baseline[component]:
                        baseline_metrics = baseline[component][file_name]
                        if current_metrics.get("status") == "success" and baseline_metrics.get("status") == "success":
                            file_comparison = {}
                            for metric in ["execution_time", "pages_per_second", "time_per_page", "memory_delta"]:
                                if metric in current_metrics and metric in baseline_metrics and baseline_metrics[metric] != 0:
                                    current_val, baseline_val = current_metrics[metric], baseline_metrics[metric]
                                    change_pct = ((current_val - baseline_val) / baseline_val) * 100
                                    file_comparison[metric] = {"current": current_val, "baseline": baseline_val, "change_percent": change_pct}
                            comparison[component][file_name] = file_comparison
        return comparison


def run_benchmark():
    runner = BenchmarkRunner()
    results = runner.run_benchmarks()
    print("Benchmark Results:")
    print(json.dumps(results, indent=2))
    baseline = runner.load_baseline()
    if baseline:
        comparison = runner.compare_to_baseline(results)
        print("\nComparison to Baseline:")
        print(json.dumps(comparison, indent=2))
    else:
        runner.save_baseline(results)
        print(f"\nBaseline saved to: {runner.baseline_path}")
    return results


if __name__ == "__main__":
    run_benchmark()
