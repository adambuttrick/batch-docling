import unittest
from pathlib import Path


class TestBenchmarkFunctionality(unittest.TestCase):
    def setUp(self):
        self.test_small_dir = Path("test_small")
        if not self.test_small_dir.exists() or not list(self.test_small_dir.glob("*.pdf")):
            self.skipTest("No test PDFs found in test_small directory")
    
    def test_benchmark_runner_initialization(self):
        from benchmarks.benchmark import BenchmarkRunner
        
        runner = BenchmarkRunner(test_dir="test_small")
        self.assertGreater(len(runner.test_pdfs), 0)
    
    def test_benchmark_sanitize_pdf(self):
        from benchmarks.benchmark import BenchmarkRunner
        
        runner = BenchmarkRunner(test_dir="test_small")
        if not runner.test_pdfs:
            self.skipTest("No test PDFs found")
        
        result = runner._benchmark_sanitize_pdf(runner.test_pdfs[0])
        self.assertIn('status', result)
        self.assertIn('execution_time', result)
    
    def test_benchmark_process_pdf(self):
        from benchmarks.benchmark import BenchmarkRunner
        
        runner = BenchmarkRunner(test_dir="test_small")
        if not runner.test_pdfs:
            self.skipTest("No test PDFs found")
        
        result = runner._benchmark_process_pdf(runner.test_pdfs[0])
        self.assertIn('status', result)
        self.assertIn('execution_time', result)
    
    def test_run_benchmarks(self):
        from benchmarks.benchmark import BenchmarkRunner
        
        runner = BenchmarkRunner(test_dir="test_small")
        results = runner.run_benchmarks()
        
        self.assertIn('sanitize_pdf', results)
        self.assertIn('process_pdf', results)


def run_benchmark_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestBenchmarkFunctionality)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_benchmark_tests()
    exit(0 if success else 1)