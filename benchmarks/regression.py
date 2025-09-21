import sys
from typing import Dict, Optional, Tuple
from .regression_detector import RegressionDetector


def generate_regression_report(detector: RegressionDetector, current_results: Dict, output_path: Optional[str] = None) -> Tuple[Dict, str]:
    regressions = detector.detect_regressions(current_results)
    text_report = detector.format_regression_report(regressions, "text")
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(text_report)
    
    return regressions, text_report

def check_and_exit(detector: RegressionDetector, current_results: Dict, fail_on_regression: bool = True) -> int:
    regressions, report = generate_regression_report(detector, current_results)
    print(report)
    
    if "error" in regressions:
        print("Warning: Could not perform regression check", file=sys.stderr)
        return 0
    
    if regressions["summary"]["has_regressions"] and fail_on_regression:
        return 1
    
    return 0

def run_regression_check(threshold: float = 10.0, baseline_path: str = "benchmarks/baseline.json") -> int:
    from benchmark import BenchmarkRunner
    
    runner = BenchmarkRunner()
    current_results = runner.run_benchmarks()
    
    detector = RegressionDetector(baseline_path, threshold)
    return check_and_exit(detector, current_results, fail_on_regression=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run regression detection")
    parser.add_argument("--threshold", type=float, default=10.0, help="Regression threshold percentage")
    parser.add_argument("--baseline", type=str, default="benchmarks/baseline.json", help="Baseline file path")
    parser.add_argument("--no-fail", action="store_true", help="Don't fail on regression detection")
    
    args = parser.parse_args()
    exit_code = run_regression_check(args.threshold, args.baseline)
    sys.exit(exit_code if not args.no_fail else 0)