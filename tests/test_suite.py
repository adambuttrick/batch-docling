import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from test_core import run_core_tests
from test_benchmark import run_benchmark_tests


def run_tests():
    core_success = run_core_tests()
    benchmark_success = run_benchmark_tests()
    return core_success and benchmark_success


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)