import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from stress_memory import run_memory_stress_tests
from stress_concurrent import run_concurrent_stress_tests


def run_stress_tests():
    memory_success = run_memory_stress_tests()
    concurrent_success = run_concurrent_stress_tests()
    return memory_success and concurrent_success


if __name__ == "__main__":
    success = run_stress_tests()
    exit(0 if success else 1)