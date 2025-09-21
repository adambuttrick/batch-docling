import os
import logging
import tempfile
from typing import Any, Dict, Optional

import fitz
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractCliOcrOptions,
    VlmPipelineOptions,
)

from .batch_manager import BatchStates, get_batch_manager
from .celery_app import celery_app
from .config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sanitize_pdf(source_path: str) -> (str, int, int):
    kept_pages = 0
    skipped_pages = 0
    try:
        original_doc = fitz.open(source_path)
    except Exception as e:
        logger.error(f"Failed to open PDF '{source_path}' with PyMuPDF: {e}")
        raise
    sanitized_doc = fitz.open()
    for i, page in enumerate(original_doc):
        try:
            pix = page.get_pixmap(dpi=72)
            if pix.width > 10 and pix.height > 10:
                sanitized_doc.insert_pdf(original_doc, from_page=i, to_page=i)
                kept_pages += 1
            else:
                logger.warning(f"Skipping invalid page {i+1} in '{source_path}' (dimensions: {pix.width}x{pix.height})")
                skipped_pages += 1
        except Exception as e:
            logger.warning(f"Could not process or render page {i+1} in '{source_path}': {e}")
            skipped_pages += 1
    if kept_pages == 0:
        original_doc.close()
        sanitized_doc.close()
        raise ValueError(f"No valid pages found in '{source_path}' after sanitization.")
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    sanitized_doc.save(temp_file.name)
    original_doc.close()
    sanitized_doc.close()
    return temp_file.name, kept_pages, skipped_pages


class PdfFormatOption:
    def __init__(self, pipeline_options, pipeline_cls=None):
        from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

        self.pipeline_cls = pipeline_cls or StandardPdfPipeline
        self.pipeline_options = pipeline_options
        self.backend = DoclingParseV4DocumentBackend


def _build_standard_pdf_pipeline_options() -> PdfPipelineOptions:
    return PdfPipelineOptions(
        do_ocr=True,
        ocr_options=TesseractCliOcrOptions(lang=['eng']),
        do_table_structure=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        do_picture_classification=False,
        do_picture_description=False,
        generate_page_images=False,
        generate_picture_images=False,
        images_scale=0.7,
        generate_parsed_pages=True,
    )


_VLM_MODEL_ALIASES = {
    "smoldocling": "SMOLDOCLING_TRANSFORMERS",
    "smoldocling_transformers": "SMOLDOCLING_TRANSFORMERS",
    "smoldocling_mlx": "SMOLDOCLING_MLX",
    "granite_vision": "GRANITE_VISION_TRANSFORMERS",
    "granite_vision_ollama": "GRANITE_VISION_OLLAMA",
    "pixtral": "PIXTRAL_12B_TRANSFORMERS",
    "pixtral_12b_transformers": "PIXTRAL_12B_TRANSFORMERS",
    "pixtral_12b_mlx": "PIXTRAL_12B_MLX",
    "phi4": "PHI4_TRANSFORMERS",
    "phi4_transformers": "PHI4_TRANSFORMERS",
    "qwen25_vl_3b_mlx": "QWEN25_VL_3B_MLX",
    "gemma3_12b_mlx": "GEMMA3_12B_MLX",
    "gemma3_27b_mlx": "GEMMA3_27B_MLX",
}


def _load_vlm_model_specs():
    import importlib

    return importlib.import_module("docling.datamodel.vlm_model_specs")


def _resolve_vlm_model_option(model_name: Optional[str]):
    default_name = "GRANITE_VISION_TRANSFORMERS"
    if not model_name:
        model_name = default_name

    lookup_key = model_name.strip()
    normalized_attr = lookup_key.upper()

    if lookup_key.lower() in _VLM_MODEL_ALIASES:
        normalized_attr = _VLM_MODEL_ALIASES[lookup_key.lower()]

    vlm_model_specs = _load_vlm_model_specs()

    if hasattr(vlm_model_specs, normalized_attr):
        return getattr(vlm_model_specs, normalized_attr)

    logger.warning(
        "Unknown VLM model '%s'; defaulting to %s",
        model_name,
        default_name,
    )
    return getattr(vlm_model_specs, default_name)


def _build_vlm_pipeline_options() -> VlmPipelineOptions:
    config = get_config()
    vlm_config: Dict[str, Any] = config.get_section("vlm_fallback") or {}

    pipeline_options = VlmPipelineOptions(
        enable_remote_services=vlm_config.get("enable_remote_services", False),
    )

    pipeline_options.force_backend_text = vlm_config.get("force_backend_text", False)
    pipeline_options.generate_page_images = vlm_config.get("generate_page_images", True)
    pipeline_options.generate_picture_images = vlm_config.get("generate_picture_images", False)

    images_scale = vlm_config.get("images_scale")
    if images_scale is not None:
        try:
            pipeline_options.images_scale = float(images_scale)
        except (TypeError, ValueError):
            logger.warning("Invalid images_scale '%s'; using default", images_scale)

    artifacts_path = vlm_config.get("artifacts_path")
    if artifacts_path:
        pipeline_options.artifacts_path = artifacts_path

    pipeline_options.vlm_options = _resolve_vlm_model_option(vlm_config.get("model"))

    return pipeline_options


def _get_vlm_pipeline_cls():
    from docling.pipeline.vlm_pipeline import VlmPipeline

    return VlmPipeline


def _process_pdf_logic(
    source_path: str,
    output_dir: str,
    batch_id: str,
    task_id: str,
    use_vlm: bool = False,
):
    sanitized_pdf_path = None
    try:
        mode = "VLM" if use_vlm else "STANDARD"
        logger.info(
            "Starting %s processing for: %s [Batch: %s | Task ID: %s]",
            mode,
            source_path,
            batch_id,
            task_id,
        )
        sanitized_pdf_path, kept, skipped = sanitize_pdf(source_path)
        logger.info(f"Sanitized '{source_path}': {kept} pages kept, {skipped} pages skipped.")

        if use_vlm:
            pipeline_options = _build_vlm_pipeline_options()
            pipeline_cls = _get_vlm_pipeline_cls()
        else:
            pipeline_options = _build_standard_pdf_pipeline_options()
            pipeline_cls = None

        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    pipeline_cls=pipeline_cls,
                )
            },
        )
        result = converter.convert(sanitized_pdf_path)
        markdown_output = result.document.export_to_markdown()
        os.makedirs(output_dir, exist_ok=True)
        base_filename = os.path.basename(source_path)
        filename_without_ext = os.path.splitext(base_filename)[0]
        output_path = os.path.join(output_dir, f"{filename_without_ext}.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_output)
        logger.info("Successfully processed and saved: %s [%s mode]", output_path, mode)
        return {
            'status': 'SUCCESS',
            'input_file': source_path,
            'output_file': output_path,
            'pages_kept': kept,
            'pages_skipped': skipped,
            'mode': mode,
        }
    except Exception as e:
        logger.error(
            "A critical error occurred for %s [%s mode]: %s",
            source_path,
            "VLM" if use_vlm else "STANDARD",
            e,
            exc_info=True,
        )
        raise
    finally:
        if sanitized_pdf_path and os.path.exists(sanitized_pdf_path):
            os.remove(sanitized_pdf_path)


def _update_batch_state(batch_manager, batch_id: str, source_path: str, success: bool):
    batch_info = batch_manager.get_batch_info(batch_id)
    if batch_info and batch_info.get("status") not in [BatchStates.COMPLETED, BatchStates.CANCELLED]:
        batch_data = batch_manager.increment_completed(
            batch_id, success=success)
        if batch_data and batch_data["completed_count"] >= batch_data["total_files"]:
            batch_manager.finalize_batch(batch_id)
    else:
        status = "finished" if success else "failed"
        logger.warning(f"Task for '{source_path}' {status} after batch {batch_id} was already finalized. Ignoring result.")


def _maybe_schedule_vlm_fallback(
    batch_manager,
    source_path: str,
    output_dir: str,
    batch_id: str,
    error: Exception,
) -> Optional[Dict[str, Any]]:
    config = get_config()
    vlm_config: Dict[str, Any] = config.get_section("vlm_fallback") or {}

    if not vlm_config.get("enabled", False):
        return None

    queue_name = vlm_config.get("queue_name", "vlm_pdf")

    try:
        fallback_task = process_pdf_vlm.apply_async(
            args=[source_path, output_dir, batch_id],
            queue=queue_name,
        )
    except Exception as dispatch_error:
        logger.error(
            "Unable to schedule VLM fallback for %s: %s",
            source_path,
            dispatch_error,
            exc_info=True,
        )
        return None

    batch_manager.add_task_to_batch(batch_id, fallback_task.id)
    batch_manager.increment_fallback_pending(batch_id)

    batch_info = batch_manager.get_batch_info(batch_id) or {}
    fallback_pending = batch_info.get("fallback_pending", 0)

    logger.info(
        "Scheduled VLM fallback task %s for %s on queue '%s'",
        fallback_task.id,
        source_path,
        queue_name,
    )

    return {
        "status": "FALLBACK_SCHEDULED",
        "input_file": source_path,
        "original_error": str(error),
        "fallback_task_id": fallback_task.id,
        "fallback_queue": queue_name,
        "fallback_pending": fallback_pending,
    }


@celery_app.task(name='tasks.process_pdf', bind=True)
def process_pdf(self, source_path: str, output_dir: str, batch_id: str):
    batch_manager = get_batch_manager()
    try:
        result = _process_pdf_logic(
            source_path, output_dir, batch_id, self.request.id)
        _update_batch_state(batch_manager, batch_id, source_path, True)
        return result
    except Exception as e:
        logger.error(
            "Initial conversion failed for %s: %s",
            source_path,
            e,
            exc_info=True,
        )
        fallback_result = _maybe_schedule_vlm_fallback(
            batch_manager=batch_manager,
            source_path=source_path,
            output_dir=output_dir,
            batch_id=batch_id,
            error=e,
        )

        if fallback_result is not None:
            return fallback_result

        _update_batch_state(batch_manager, batch_id, source_path, False)
        raise


@celery_app.task(name='tasks.process_pdf_vlm', bind=True)
def process_pdf_vlm(self, source_path: str, output_dir: str, batch_id: str):
    batch_manager = get_batch_manager()
    try:
        result = _process_pdf_logic(
            source_path,
            output_dir,
            batch_id,
            self.request.id,
            use_vlm=True,
        )
        batch_manager.decrement_fallback_pending(batch_id)
        _update_batch_state(batch_manager, batch_id, source_path, True)
        return result
    except Exception as e:
        logger.error(
            "VLM fallback failed for %s: %s",
            source_path,
            e,
            exc_info=True,
        )
        batch_manager.decrement_fallback_pending(batch_id)
        _update_batch_state(batch_manager, batch_id, source_path, False)
        raise


@celery_app.task(name='tasks.audit_batch_status')
def audit_batch_status(batch_id: str):
    batch_manager = get_batch_manager()
    batch_info = batch_manager.get_batch_info(batch_id)
    if not batch_info:
        logger.warning(f"[Audit] Batch {batch_id} not found. Nothing to do.")
        return
    if batch_info.get("status") in [BatchStates.COMPLETED, BatchStates.CANCELLED]:
        logger.info(f"[Audit] Batch {batch_id} already finalized. Nothing to do.")
        return
    if batch_info.get("fallback_pending", 0):
        pending = batch_info.get("fallback_pending", 0)
        logger.info(
            "[Audit] Batch %s has %s fallback task(s) pending; postponing audit finalization.",
            batch_id,
            pending,
        )
        return f"Batch {batch_id} waiting on {pending} fallback task(s)."
    total_files = batch_info.get("total_files", 0)
    completed_count = batch_info.get("completed_count", 0)
    if completed_count < total_files:
        lost_tasks = total_files - completed_count
        notes = f"Auditor marked {lost_tasks} task(s) as lost due to timeout or crash."
        logger.warning(f"[Audit] Batch {batch_id} is stuck at {completed_count}/{total_files}. Finalizing.")
        batch_manager.finalize_batch(batch_id, notes)
        return f"Batch {batch_id} was stuck and has been finalized by the auditor."
    return f"Batch {batch_id} completed normally."
