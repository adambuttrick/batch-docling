import gc
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

class MemoryMonitor:
    def __init__(self):
        self.peak_memory = 0
        self.initial_memory = 0
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        if not psutil:
            return
        self.initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        self.peak_memory = self.initial_memory
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self):
        while self.monitoring:
            if psutil:
                current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
                self.peak_memory = max(self.peak_memory, current_memory)
            time.sleep(0.1)
    
    def get_memory_delta(self):
        if not psutil:
            return None
        return psutil.Process().memory_info().rss / (1024 * 1024) - self.initial_memory

class StressMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dirs = {"small": Path("test_small"), "medium": Path("test_medium"), "large": Path("test_large")}
        cls.test_pdfs = {}
        for size, path in cls.test_dirs.items():
            cls.test_pdfs[size] = list(path.glob("*.pdf"))[:3] if path.exists() else []
    
    def setUp(self):
        gc.collect()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
        gc.collect()
    
    def test_memory_cleanup_after_sanitize(self):
        if not self.test_pdfs["small"]:
            self.skipTest("No small test PDFs available")
        from docling_service.tasks import sanitize_pdf
        monitor = MemoryMonitor()
        monitor.start_monitoring()
        for pdf in self.test_pdfs["small"]:
            sanitized_path, kept, skipped = sanitize_pdf(str(pdf))
            self.assertGreater(kept, 0)
            if os.path.exists(sanitized_path):
                os.remove(sanitized_path)
            gc.collect()
        monitor.stop_monitoring()
        memory_delta = monitor.get_memory_delta()
        if memory_delta is not None:
            self.assertLess(memory_delta, 50, "Memory usage increased by more than 50MB")
    
    def test_process_pdf_memory_behavior(self):
        if not self.test_pdfs["small"]:
            self.skipTest("No small test PDFs available")
        from docling_service.tasks import _process_pdf_logic
        monitor = MemoryMonitor()
        monitor.start_monitoring()
        for pdf in self.test_pdfs["small"][:2]:
            result = _process_pdf_logic(str(pdf), self.temp_dir, "stress_test", "stress_task")
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue(os.path.exists(result["output_file"]))
            gc.collect()
        monitor.stop_monitoring()
        memory_delta = monitor.get_memory_delta()
        if memory_delta is not None:
            self.assertLess(memory_delta, 200, "Memory usage increased by more than 200MB")
    
    def test_large_pdf_handling(self):
        if not self.test_pdfs["medium"]:
            self.skipTest("No medium test PDFs available")
        from docling_service.tasks import sanitize_pdf, _process_pdf_logic
        test_pdf = str(self.test_pdfs["medium"][0])
        file_size = os.path.getsize(test_pdf) / (1024 * 1024)
        if file_size < 1:
            self.skipTest("Test PDF too small for large file test")
        monitor = MemoryMonitor()
        monitor.start_monitoring()
        sanitized_path, kept, skipped = sanitize_pdf(test_pdf)
        self.assertGreater(kept, 0)
        result = _process_pdf_logic(test_pdf, self.temp_dir, "large_test", "large_task")
        self.assertEqual(result["status"], "SUCCESS")
        if os.path.exists(sanitized_path):
            os.remove(sanitized_path)
        monitor.stop_monitoring()
        memory_delta = monitor.get_memory_delta()
        if memory_delta is not None:
            max_expected_memory = file_size * 10
            self.assertLess(memory_delta, max_expected_memory, f"Memory usage too high for {file_size:.1f}MB file")
    
    @unittest.skipIf(not psutil, "psutil not available for memory testing")
    def test_memory_leak_detection(self):
        if not self.test_pdfs["small"]:
            self.skipTest("No small test PDFs available")
        from docling_service.tasks import sanitize_pdf
        initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        for i in range(5):
            for pdf in self.test_pdfs["small"]:
                sanitized_path, kept, skipped = sanitize_pdf(str(pdf))
                if os.path.exists(sanitized_path):
                    os.remove(sanitized_path)
            gc.collect()
        final_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_growth = final_memory - initial_memory
        self.assertLess(memory_growth, 100, f"Potential memory leak detected: {memory_growth:.1f}MB growth")

def run_memory_stress_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(StressMemoryTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_memory_stress_tests()
    exit(0 if success else 1)