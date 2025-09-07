import os
import logging
import tempfile
import fitz
from .celery_app import celery_app
from .batch_manager import get_batch_manager, BatchStates
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
from docling.datamodel.base_models import InputFormat

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
    def __init__(self, pipeline_options):
        from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
        self.pipeline_cls = StandardPdfPipeline
        self.pipeline_options = pipeline_options
        self.backend = DoclingParseV4DocumentBackend


def _process_pdf_logic(source_path: str, output_dir: str, batch_id: str, task_id: str):
    sanitized_pdf_path = None
    try:
        logger.info(f"Starting processing for: {source_path} [Task ID: {task_id}]")
        sanitized_pdf_path, kept, skipped = sanitize_pdf(source_path)
        logger.info(f"Sanitized '{source_path}': {kept} pages kept, {skipped} pages skipped.")
        pipeline_options = PdfPipelineOptions(
            do_ocr=True, ocr_options=TesseractCliOcrOptions(lang=['eng']),
            do_table_structure=False, do_code_enrichment=False, do_formula_enrichment=False,
            do_picture_classification=False, do_picture_description=False,
            generate_page_images=False, generate_picture_images=False,
            images_scale=0.7, generate_parsed_pages=True
        )
        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options)}
        )
        result = converter.convert(sanitized_pdf_path)
        markdown_output = result.document.export_to_markdown()
        os.makedirs(output_dir, exist_ok=True)
        base_filename = os.path.basename(source_path)
        filename_without_ext = os.path.splitext(base_filename)[0]
        output_path = os.path.join(output_dir, f"{filename_without_ext}.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_output)
        logger.info(f"Successfully processed and saved: {output_path}")
        return {
            'status': 'SUCCESS', 'input_file': source_path, 'output_file': output_path,
            'pages_kept': kept, 'pages_skipped': skipped
        }
    except Exception as e:
        logger.error(f"A critical error occurred for {source_path}: {e}", exc_info=True)
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


@celery_app.task(name='tasks.process_pdf', bind=True)
def process_pdf(self, source_path: str, output_dir: str, batch_id: str):
    batch_manager = get_batch_manager()
    try:
        result = _process_pdf_logic(
            source_path, output_dir, batch_id, self.request.id)
        _update_batch_state(batch_manager, batch_id, source_path, True)
        return result
    except Exception as e:
        logger.error(f"A critical error or timeout occurred for {source_path}: {e}", exc_info=True)
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
    total_files = batch_info.get("total_files", 0)
    completed_count = batch_info.get("completed_count", 0)
    if completed_count < total_files:
        lost_tasks = total_files - completed_count
        notes = f"Auditor marked {lost_tasks} task(s) as lost due to timeout or crash."
        logger.warning(f"[Audit] Batch {batch_id} is stuck at {completed_count}/{total_files}. Finalizing.")
        batch_manager.finalize_batch(batch_id, notes)
        return f"Batch {batch_id} was stuck and has been finalized by the auditor."
    return f"Batch {batch_id} completed normally."
