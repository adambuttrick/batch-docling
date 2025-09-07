import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest
from test_core import run_core_tests
from test_benchmark import run_benchmark_tests
from stress_memory import run_memory_stress_tests
from stress_concurrent import run_concurrent_stress_tests


def run_all_tests():
    print("Running Core Tests...")
    core_success = run_core_tests()
    
    print("\nRunning Benchmark Tests...")
    benchmark_success = run_benchmark_tests()
    
    print("\nRunning Memory Stress Tests...")
    memory_success = run_memory_stress_tests()
    
    print("\nRunning Concurrent Stress Tests...")
    concurrent_success = run_concurrent_stress_tests()
    
    all_success = core_success and benchmark_success and memory_success and concurrent_success
    
    if all_success:
        print("\nAll tests passed")
    else:
        print("\nSome tests failed")
    
    return all_success


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)