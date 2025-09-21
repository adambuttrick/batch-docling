import gc
import os
import tempfile
import time
import unittest
import concurrent.futures
from pathlib import Path


class StressConcurrentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dirs = {
            "small": Path("tests/sample_pdfs"),
            "medium": Path("test_medium"), 
            "large": Path("test_large")
        }
        cls.test_pdfs = {}
        for size, path in cls.test_dirs.items():
            if path.exists():
                cls.test_pdfs[size] = list(path.glob("*.pdf"))[:3]
            else:
                cls.test_pdfs[size] = []
    
    def setUp(self):
        gc.collect()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
        gc.collect()
    
    def test_concurrent_sanitize_operations(self):
        if not self.test_pdfs["small"]:
            self.skipTest("No small test PDFs available")
        
        from docling_service.tasks import sanitize_pdf
        
        def sanitize_worker(pdf_path):
            try:
                sanitized_path, kept, skipped = sanitize_pdf(str(pdf_path))
                if os.path.exists(sanitized_path):
                    os.remove(sanitized_path)
                return {"success": True, "kept": kept, "skipped": skipped}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(sanitize_worker, pdf) for pdf in self.test_pdfs["small"]]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        successful_results = [r for r in results if r["success"]]
        self.assertGreater(len(successful_results), 0, "No concurrent operations succeeded")
    
    def test_benchmark_under_load(self):
        if not self.test_pdfs["small"]:
            self.skipTest("No small test PDFs available")
        
        from benchmarks.benchmark import BenchmarkRunner
        
        runner = BenchmarkRunner(test_dir="tests/sample_pdfs")
        
        start_time = time.time()
        results = runner.run_benchmarks()
        end_time = time.time()
        
        self.assertIn("sanitize_pdf", results)
        self.assertIn("process_pdf", results)
        self.assertLess(end_time - start_time, 120, "Benchmarks took longer than 2 minutes")
    
    def test_error_resilience(self):
        from docling_service.tasks import sanitize_pdf, _process_pdf_logic
        
        invalid_paths = [
            "nonexistent.pdf",
            "/dev/null",
            "",
            "not_a_pdf.txt"
        ]
        
        for invalid_path in invalid_paths:
            with self.assertRaises(Exception):
                sanitize_pdf(invalid_path)
            
            with self.assertRaises(Exception):
                _process_pdf_logic(invalid_path, self.temp_dir, "error_test", "error_task")
    
    def test_concurrent_process_operations(self):
        if not self.test_pdfs["small"]:
            self.skipTest("No small test PDFs available")
        
        from docling_service.tasks import _process_pdf_logic
        
        def process_worker(pdf_path, temp_dir, job_id):
            try:
                result = _process_pdf_logic(str(pdf_path), temp_dir, job_id, "concurrent_test")
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for i, pdf in enumerate(self.test_pdfs["small"][:2]):
                temp_dir = tempfile.mkdtemp()
                job_id = f"concurrent_{i}"
                futures.append(executor.submit(process_worker, pdf, temp_dir, job_id))
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        successful_results = [r for r in results if r["success"]]
        self.assertGreater(len(successful_results), 0, "No concurrent process operations succeeded")


def run_concurrent_stress_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(StressConcurrentTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_concurrent_stress_tests()
    exit(0 if success else 1)
