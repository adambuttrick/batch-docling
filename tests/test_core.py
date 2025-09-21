import os
import tempfile
import unittest
import shutil
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from pathlib import Path


SAMPLE_PDF_DIR = Path("tests/sample_pdfs")


class TestSanitizePdf(unittest.TestCase):
    def setUp(self):
        if not SAMPLE_PDF_DIR.exists():
            self.skipTest("Sample PDF directory is missing")
        self.valid_pdf = SAMPLE_PDF_DIR / "valid_text.pdf"
        self.image_pdf = SAMPLE_PDF_DIR / "image_only.pdf"
        self.invalid_pdf = SAMPLE_PDF_DIR / "invalid_content.pdf"
        if not self.valid_pdf.exists() or not self.image_pdf.exists():
            self.skipTest("Sample PDFs not generated")
    
    def test_sanitize_pdf_valid_file(self):
        from docling_service.tasks import sanitize_pdf
        
        sanitized_path, kept_pages, skipped_pages = sanitize_pdf(str(self.valid_pdf))
        
        self.assertTrue(os.path.exists(sanitized_path))
        self.assertGreater(kept_pages, 0)
        self.assertGreaterEqual(skipped_pages, 0)
        self.assertTrue(sanitized_path.endswith('.pdf'))
        
        os.remove(sanitized_path)
    
    def test_sanitize_pdf_invalid_file(self):
        from docling_service.tasks import sanitize_pdf
        
        with self.assertRaises(Exception):
            sanitize_pdf(str(self.invalid_pdf))
    
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
        if not SAMPLE_PDF_DIR.exists():
            self.skipTest("Sample PDF directory is missing")
        self.valid_pdf = SAMPLE_PDF_DIR / "valid_text.pdf"
        self.image_pdf = SAMPLE_PDF_DIR / "image_only.pdf"
        self.invalid_pdf = SAMPLE_PDF_DIR / "invalid_content.pdf"
        if not self.valid_pdf.exists() or not self.image_pdf.exists():
            self.skipTest("Sample PDFs not generated")
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_process_pdf_logic_success(self):
        from docling_service.tasks import _process_pdf_logic
        
        result = _process_pdf_logic(str(self.valid_pdf), self.temp_dir, "test_job", "test_task")

        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(result['input_file'], str(self.valid_pdf))
        self.assertTrue(os.path.exists(result['output_file']))
        self.assertGreater(result['pages_kept'], 0)
        self.assertGreaterEqual(result['pages_skipped'], 0)
    
    def test_process_pdf_logic_invalid_input(self):
        from docling_service.tasks import _process_pdf_logic
        
        with self.assertRaises(Exception):
            _process_pdf_logic(str(self.invalid_pdf), self.temp_dir, "test_job", "test_task")


class TestVlmFallback(unittest.TestCase):
    def setUp(self):
        self.batch_manager = MagicMock()
        if not SAMPLE_PDF_DIR.exists():
            self.skipTest("Sample PDF directory is missing")
        self.image_pdf = SAMPLE_PDF_DIR / "image_only.pdf"
        if not self.image_pdf.exists():
            self.skipTest("Image-only sample PDF missing")
        self.temp_dir = tempfile.mkdtemp()
        from docling_service import tasks as tasks_module
        tasks_module._ACCELERATOR_CFG_CACHE.clear()
        tasks_module._detect_accelerator.cache_clear()

    def tearDown(self):
        if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_schedule_vlm_fallback_disabled(self):
        from docling_service.tasks import schedule_vlm_fallback

        mock_config = MagicMock()
        vlm_cfg = {"enabled": False}
        accelerator_cfg = {
            "standard_device": "cpu",
            "vlm_device": "cpu",
            "prefer_mps": False,
            "prefer_cuda": False,
            "num_threads": 1,
        }
        def _section(section):
            if section == "vlm_fallback":
                return vlm_cfg
            if section == "accelerator":
                return accelerator_cfg
            return {}
        mock_config.get_section.side_effect = _section

        with patch("docling_service.tasks.get_config", return_value=mock_config):
            result = schedule_vlm_fallback(
                self.batch_manager,
                "sample.pdf",
                "out",
                "batch-1",
                Exception("fail"),
                1,
                "parent",
                vlm_cfg,
            )

        self.assertIsNone(result)
        self.batch_manager.add_task_to_batch.assert_not_called()
        self.batch_manager.increment_fallback_pending.assert_not_called()

    @patch("docling_service.tasks.process_pdf_vlm.apply_async")
    def test_schedule_vlm_fallback_enabled(self, mock_apply_async):
        from docling_service.tasks import schedule_vlm_fallback

        mock_task = MagicMock()
        mock_task.id = "fallback-123"
        mock_apply_async.return_value = mock_task

        self.batch_manager.get_batch_info.return_value = {"fallback_pending": 1}

        mock_config = MagicMock()
        monitoring_cfg = {
            "task_timeout_profiles": {
                "standard": {"soft_seconds": 600, "hard_seconds": 1200, "max_retries": 1},
                "vlm": {"soft_seconds": 1800, "hard_seconds": 3600, "max_retries": 1},
            }
        }
        vlm_cfg = {
            "enabled": True,
            "queue_name": "vlm_pdf",
            "primary_mode": "standard",
        }
        accelerator_cfg = {
            "standard_device": "cpu",
            "vlm_device": "cpu",
            "prefer_mps": False,
            "prefer_cuda": False,
            "num_threads": 1,
        }

        def _section(section):
            if section == "vlm_fallback":
                return vlm_cfg
            if section == "monitoring":
                return monitoring_cfg
            if section == "accelerator":
                return accelerator_cfg
            return {}

        mock_config.get_section.side_effect = _section

        with patch("docling_service.tasks.get_config", return_value=mock_config):
            result = schedule_vlm_fallback(
                self.batch_manager,
                "sample.pdf",
                "out",
                "batch-1",
                Exception("fail"),
                1,
                "parent",
                vlm_cfg,
            )

        self.batch_manager.add_task_to_batch.assert_called_once_with("batch-1", "fallback-123")
        self.batch_manager.increment_fallback_pending.assert_called_once_with("batch-1")
        mock_apply_async.assert_called_once()
        self.assertIsNotNone(result)
        self.assertEqual(result["fallback_task_id"], "fallback-123")
        self.assertEqual(result["fallback_queue"], vlm_cfg["queue_name"])
        self.assertEqual(result.get("status"), "FALLBACK_SCHEDULED")

    @patch("docling_service.tasks.process_pdf_standard.apply_async")
    def test_schedule_standard_fallback_enabled(self, mock_apply_async):
        from docling_service.tasks import schedule_standard_fallback

        mock_task = MagicMock()
        mock_task.id = "standard-456"
        mock_apply_async.return_value = mock_task

        self.batch_manager.get_batch_info.return_value = {"fallback_pending": 2}

        mock_config = MagicMock()
        monitoring_cfg = {
            "task_timeout_profiles": {
                "standard": {"soft_seconds": 600, "hard_seconds": 1200, "max_retries": 1},
                "vlm": {"soft_seconds": 1800, "hard_seconds": 3600, "max_retries": 1},
            }
        }
        vlm_cfg = {
            "enabled": True,
            "queue_name": "vlm_pdf",
            "primary_mode": "vlm",
        }
        accelerator_cfg = {
            "standard_device": "cpu",
            "vlm_device": "cpu",
            "prefer_mps": False,
            "prefer_cuda": False,
            "num_threads": 1,
        }

        def _section(section):
            if section == "vlm_fallback":
                return vlm_cfg
            if section == "monitoring":
                return monitoring_cfg
            if section == "accelerator":
                return accelerator_cfg
            return {}

        mock_config.get_section.side_effect = _section

        with patch("docling_service.tasks.get_config", return_value=mock_config):
            result = schedule_standard_fallback(
                self.batch_manager,
                "sample.pdf",
                "out",
                "batch-1",
                Exception("fail"),
                1,
                "parent",
                vlm_cfg,
            )

        self.batch_manager.add_task_to_batch.assert_called_once_with("batch-1", "standard-456")
        self.batch_manager.increment_fallback_pending.assert_called_once_with("batch-1")
        mock_apply_async.assert_called_once()
        self.assertIsNotNone(result)
        self.assertEqual(result["fallback_task_id"], "standard-456")
        self.assertEqual(result["fallback_queue"], "celery")
        self.assertEqual(result.get("status"), "FALLBACK_SCHEDULED")

    @patch("docling_service.tasks.process_pdf_vlm.apply_async")
    @patch("docling_service.tasks.get_config")
    @patch("docling_service.tasks.get_batch_manager")
    @patch("docling_service.tasks._process_pdf_logic")
    def test_process_pdf_triggers_vlm_fallback_in_standard_mode(
        self,
        mock_process_logic,
        mock_get_batch_manager,
        mock_get_config,
        mock_apply_async,
    ):
        from docling_service.tasks import process_pdf

        mock_process_logic.side_effect = Exception("conversion failed")
        mock_task = MagicMock()
        mock_task.id = "vlm-task"
        mock_apply_async.return_value = mock_task

        config_mock = MagicMock()
        monitoring_cfg = {
            "task_timeout_profiles": {
                "standard": {"soft_seconds": 600, "hard_seconds": 1200, "max_retries": 1},
                "vlm": {"soft_seconds": 1800, "hard_seconds": 3600, "max_retries": 1},
            }
        }
        vlm_cfg = {
            "enabled": True,
            "queue_name": "vlm_pdf",
            "primary_mode": "standard",
        }
        accelerator_cfg = {
            "standard_device": "cpu",
            "vlm_device": "cpu",
            "prefer_mps": False,
            "prefer_cuda": False,
            "num_threads": 1,
        }
        def _section(section):
            if section == "vlm_fallback":
                return vlm_cfg
            if section == "monitoring":
                return monitoring_cfg
            if section == "accelerator":
                return accelerator_cfg
            return {}
        config_mock.get_section.side_effect = _section
        mock_get_config.return_value = config_mock

        batch_manager = MagicMock()
        batch_manager.get_batch_info.return_value = {
            "status": "RUNNING",
            "completed_count": 0,
            "total_files": 1,
            "fallback_pending": 1,
        }
        batch_manager.increment_completed.return_value = {
            "completed_count": 0,
            "total_files": 1,
        }
        mock_get_batch_manager.return_value = batch_manager

        fake_task = SimpleNamespace(request=SimpleNamespace(id="test-task"))

        result = process_pdf.__wrapped__.__func__(
            fake_task,
            source_path=str(self.image_pdf),
            output_dir=self.temp_dir,
            batch_id="batch-123",
        )

        mock_process_logic.assert_called_once()
        mock_apply_async.assert_called_once()
        batch_manager.add_task_to_batch.assert_called_once_with("batch-123", "vlm-task")
        batch_manager.increment_fallback_pending.assert_called_once_with("batch-123")
        self.assertEqual(result["status"], "FALLBACK_SCHEDULED")

    @patch("docling_service.tasks.process_pdf_standard.apply_async")
    @patch("docling_service.tasks.get_config")
    @patch("docling_service.tasks.get_batch_manager")
    @patch("docling_service.tasks._process_pdf_logic")
    def test_process_pdf_vlm_mode_falls_back_to_standard(
        self,
        mock_process_logic,
        mock_get_batch_manager,
        mock_get_config,
        mock_apply_async,
    ):
        from docling_service.tasks import process_pdf

        mock_process_logic.side_effect = Exception("conversion failed")
        mock_task = MagicMock()
        mock_task.id = "standard-task"
        mock_apply_async.return_value = mock_task

        config_mock = MagicMock()
        monitoring_cfg = {
            "task_timeout_profiles": {
                "standard": {"soft_seconds": 600, "hard_seconds": 1200, "max_retries": 1},
                "vlm": {"soft_seconds": 1800, "hard_seconds": 3600, "max_retries": 1},
            }
        }
        vlm_cfg = {
            "enabled": True,
            "queue_name": "vlm_pdf",
            "primary_mode": "vlm",
        }
        accelerator_cfg = {
            "standard_device": "cpu",
            "vlm_device": "cpu",
            "prefer_mps": False,
            "prefer_cuda": False,
            "num_threads": 1,
        }
        def _section(section):
            if section == "vlm_fallback":
                return vlm_cfg
            if section == "monitoring":
                return monitoring_cfg
            if section == "accelerator":
                return accelerator_cfg
            return {}
        config_mock.get_section.side_effect = _section
        mock_get_config.return_value = config_mock

        batch_manager = MagicMock()
        batch_manager.get_batch_info.return_value = {
            "status": "RUNNING",
            "completed_count": 0,
            "total_files": 1,
            "fallback_pending": 1,
        }
        batch_manager.increment_completed.return_value = {
            "completed_count": 0,
            "total_files": 1,
        }
        mock_get_batch_manager.return_value = batch_manager

        fake_task = SimpleNamespace(request=SimpleNamespace(id="test-task"))

        result = process_pdf.__wrapped__.__func__(
            fake_task,
            source_path=str(self.image_pdf),
            output_dir=self.temp_dir,
            batch_id="batch-123",
        )

        mock_process_logic.assert_called_once()
        mock_apply_async.assert_called_once()
        batch_manager.add_task_to_batch.assert_called_once_with("batch-123", "standard-task")
        batch_manager.increment_fallback_pending.assert_called_once_with("batch-123")
        self.assertEqual(result["status"], "FALLBACK_SCHEDULED")


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


class TestVlmAutoSelection(unittest.TestCase):
    def test_granite_uses_mlx_on_mac(self):
        from docling_service import tasks as tasks_module

        with patch.dict('sys.modules', {'mlx_vlm': MagicMock()}), \
             patch('docling_service.tasks.sys.platform', 'darwin'), \
             patch('docling_service.tasks.get_vlm_config', return_value={'model': 'GRANITE_VISION_TRANSFORMERS', 'granite_mlx_repo': 'ibm-granite/vision-mlx-test'}), \
             patch('docling_service.tasks._get_accelerator_options') as mock_accel:
            mock_accel.return_value = MagicMock()
            tasks_module._ACCELERATOR_CFG_CACHE.clear()
            tasks_module._detect_accelerator.cache_clear()
            options = tasks_module._build_vlm_pipeline_options()
            self.assertEqual(options.vlm_options.repo_id, 'ibm-granite/vision-mlx-test')
            self.assertEqual(options.vlm_options.inference_framework, tasks_module.InferenceFramework.MLX)


def run_core_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestSanitizePdf,
        TestProcessPdfLogic,
        TestVlmFallback,
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
