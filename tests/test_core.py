import os
import tempfile
import unittest
import shutil
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestSanitizePdf(unittest.TestCase):
    def setUp(self):
        self.test_small_dir = Path("test_small")
        self.test_pdfs = list(self.test_small_dir.glob("*.pdf")) if self.test_small_dir.exists() else []
        if not self.test_pdfs:
            self.skipTest("No test PDFs found in test_small directory")
    
    def test_sanitize_pdf_valid_file(self):
        from docling_service.tasks import sanitize_pdf
        
        test_pdf = str(self.test_pdfs[0])
        sanitized_path, kept_pages, skipped_pages = sanitize_pdf(test_pdf)
        
        self.assertTrue(os.path.exists(sanitized_path))
        self.assertGreater(kept_pages, 0)
        self.assertGreaterEqual(skipped_pages, 0)
        self.assertTrue(sanitized_path.endswith('.pdf'))
        
        os.remove(sanitized_path)
    
    def test_sanitize_pdf_invalid_file(self):
        from docling_service.tasks import sanitize_pdf
        
        with self.assertRaises(Exception):
            sanitize_pdf("nonexistent_file.pdf")
    
    @patch('fitz.open')
    def test_sanitize_pdf_no_valid_pages(self, mock_fitz_open):
        from docling_service.tasks import sanitize_pdf
        
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.width = 5
        mock_pix.height = 5
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__iter__ = lambda x: iter([mock_page])
        mock_fitz_open.return_value = mock_doc
        
        with self.assertRaises(ValueError):
            sanitize_pdf("dummy.pdf")


class TestProcessPdfLogic(unittest.TestCase):
    def setUp(self):
        self.test_small_dir = Path("test_small")
        self.test_pdfs = list(self.test_small_dir.glob("*.pdf")) if self.test_small_dir.exists() else []
        if not self.test_pdfs:
            self.skipTest("No test PDFs found in test_small directory")
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_process_pdf_logic_success(self):
        from docling_service.tasks import _process_pdf_logic
        
        test_pdf = str(self.test_pdfs[0])
        result = _process_pdf_logic(test_pdf, self.temp_dir, "test_job", "test_task")
        
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(result['input_file'], test_pdf)
        self.assertTrue(os.path.exists(result['output_file']))
        self.assertGreater(result['pages_kept'], 0)
        self.assertGreaterEqual(result['pages_skipped'], 0)
    
    def test_process_pdf_logic_invalid_input(self):
        from docling_service.tasks import _process_pdf_logic
        
        with self.assertRaises(Exception):
            _process_pdf_logic("nonexistent.pdf", self.temp_dir, "test_job", "test_task")


class TestRegressionDetection(unittest.TestCase):
    def test_regression_detector_initialization(self):
        from benchmarks.regression_detector import RegressionDetector
        
        detector = RegressionDetector(threshold_percent=10.0)
        self.assertEqual(detector.threshold_percent, 10.0)
    
    def test_regression_detector_invalid_threshold(self):
        from benchmarks.regression_detector import RegressionDetector
        
        with self.assertRaises(ValueError):
            RegressionDetector(threshold_percent=-5.0)
    
    def test_calculate_regression_percentage(self):
        from benchmarks.regression_detector import RegressionDetector
        
        detector = RegressionDetector()
        
        self.assertEqual(detector.calculate_regression_percentage(11, 10), 10.0)
        self.assertEqual(detector.calculate_regression_percentage(9, 10), -10.0)
        self.assertEqual(detector.calculate_regression_percentage(10, 0), 0.0)
    
    def test_is_metric_regression(self):
        from benchmarks.regression_detector import RegressionDetector
        
        detector = RegressionDetector(threshold_percent=10.0)
        
        self.assertTrue(detector.is_metric_regression("execution_time", 11.1, 10))
        self.assertFalse(detector.is_metric_regression("execution_time", 10.5, 10))
        self.assertTrue(detector.is_metric_regression("pages_per_second", 8.9, 10))
        self.assertFalse(detector.is_metric_regression("pages_per_second", 9.5, 10))


def run_core_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestSanitizePdf,
        TestProcessPdfLogic,
        TestRegressionDetection
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_core_tests()
    exit(0 if success else 1)