# Docling Batch Processor

PDF to markdown conversion with celery and docling.

## Quick Start

### Local Installation
```bash
uv pip install -e .
redis-server &
python -m docling_service.daemon

# Add PDFs to process
cp -r your_pdfs/ data/input/batch_001/
```

See `LOCAL_SETUP.md` for additional details

### Docker Installation
```bash
docker-compose up -d

# Add PDFs to process
cp -r your_pdfs/ data/input/batch_001/
```

Output files will appear in `data/output/batch_001/`

# Installation

## Local Installation

```bash
git clone <repository-url>
cd celery-docling

python -m venv .venv
source .venv/bin/activate

brew install redis

brew install tesseract
```

## Docker Installation

```bash
git clone <repository-url>
cd celery-docling

docker-compose up -d
```

# Configuration

Config is loaded from `config.yaml` with environment variable overrides.

## VLM Fallback

If `vlm_fallback.enabled` is set to `true` in your config, failed PDF conversions are re-queued onto a dedicated Celery worker that executes Docling's VLM pipeline with the Granit Dolcing models. The worker listens on `vlm_fallback.queue_name` with a default of `vlm_pdf`) and should be started separately because VLM jobs are slower and often require different hardware. Batch progress tracking now keeps pending VLM retries visible via the `fallback_pending` counter.

## Environment Variables

- `REDIS_URL`: Redis connection URL
- `CELERY_TASK_SOFT_TIME_LIMIT`: Soft time limit for tasks
- `CELERY_TASK_TIME_LIMIT`: Hard time limit for tasks
- `WORKER_MAX_TASKS_PER_CHILD`: Max tasks per worker process
- `WORKER_PREFETCH_MULTIPLIER`: Task prefetch multiplier
- `AUDIT_DELAY_SECONDS`: Delay for audit tasks
- `VLM_FALLBACK_ENABLED`: Enable VLM-based retry path for failed PDFs
- `VLM_QUEUE_NAME`: Celery queue name used by the VLM worker
- `VLM_FALLBACK_MODEL`: Model spec to load (e.g. `GRANITE_VISION_TRANSFORMERS`)
- `VLM_WORKER_CONCURRENCY`: Concurrency for the VLM worker processes
- `VLM_ARTIFACTS_PATH`: Optional local path with pre-downloaded models

## Example config.yaml

```yaml
redis:
  url: "redis://localhost:6379/0"

celery:
  task_soft_time_limit: 300
  task_time_limit: 600
  worker_max_tasks_per_child: 100

vlm_fallback:
  enabled: true
  queue_name: "vlm_pdf"
  model: "GRANITE_VISION_TRANSFORMERS"
  worker_concurrency: 1
```
