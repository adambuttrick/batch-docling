#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from benchmarks.benchmark import BenchmarkRunner
from benchmarks.regression_detector import RegressionDetector
from benchmarks.regression import check_and_exit


def main():
    parser = argparse.ArgumentParser(description="Run regression detection")
    parser.add_argument("--threshold", type=float, default=10.0, help="Regression threshold percentage")
    parser.add_argument("--baseline", type=str, default="benchmarks/baseline.json", help="Baseline file path")
    parser.add_argument("--no-fail", action="store_true", help="Don't fail on regression detection")
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner()
    current_results = runner.run_benchmarks()
    
    detector = RegressionDetector(args.baseline, args.threshold)
    exit_code = check_and_exit(detector, current_results, fail_on_regression=not args.no_fail)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()