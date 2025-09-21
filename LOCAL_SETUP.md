# Local Setup

## Prerequisites

Ensure you have the following installed:
- Python 3.12+
- Homebrew
- Redis
- Tesseract OCR

## Installation

1. System dependenciea:
```bash
brew install redis tesseract
```

2. Virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install python dependencies:
```bash
pip install uv
uv pip install -e .
```

## Setup

The processor uses `config.local.yaml` for local development. This file is already provided and configured correctly. The processor will automatically detect and use it.

- Redis URL: `redis://localhost:6379/0`
- Input directory: `./data/input`
- Output directory: `./data/output`

## Quick Start with Scripts

The easiest way to start everything:

```bash
./utils/start_local.sh
```

To stop everything:

```bash
./utils/stop_local.sh
```

## Manual Setup - Step by Step

### Step 1: Start Redis
```bash
redis-server --daemonize yes
```

### Step 2: Start Celery Workers
```bash
source .venv/bin/activate
celery -A docling_service.celery_app worker --loglevel=info --concurrency=4
```

Note: Default concurrency (16) can result in `XPC_ERROR_CONNECTION_INVALID` errors on macOS when using PyTorch with Metal acceleration. Use `--concurrency=4` or lower to prevent.

### Step 3: Start the Daemon
```bash
source .venv/bin/activate
python -m docling_service.daemon start config.local.yaml
```

The daemon will:
- Watch `./data/input` for new directories containing PDFs
- Process them automatically every 10 seconds
- Output markdown files to `./data/output`

### Step 4: Add PDFs to Process
Create a subdirectory in `data/input/` and add your PDFs:
```bash
mkdir data/input/my_batch
cp *.pdf data/input/my_batch/
```

### Step 5: Monitor Processing
```bash
# Check output
ls -la data/output/my_batch/

# View Celery logs (if running in foreground)
# Watch for "Task ... succeeded" messages

# Check Redis for batch status
redis-cli keys "docling_batch:*"
```

### Option 2: Using the Local Config

The `config.local.yaml` file contains settings for running locally:

- Redis URL: `redis://localhost:6379/0`
- Input directory: `./data/input`
- Output directory: `./data/output`
- Timeouts suitable for local processing

To use:

```bash
# Start services using local config
source .venv/bin/activate
python -m docling_service.daemon start config.local.yaml
```


### Option 3: Background Services

```bash
# Start all services in background
redis-server --daemonize yes
source .venv/bin/activate
celery -A docling_service.celery_app worker --loglevel=info --detach
python -m docling_service.daemon start config.local.yaml &

# Check status
python -m docling_service.daemon status

# Stop daemon
python -m docling_service.daemon stop

# Stop Celery workers
pkill -f "celery.*worker"

# Stop Redis
redis-cli shutdown
```

## Data Directory Structure

```
data/
├── input/       # Place PDF batches here
│   └── batch_001/
│       ├── document1.pdf
│       └── document2.pdf
└── output/      # Processed files appear here
    └── batch_001/
        ├── document1.md
        └── document2.md
```

## Configuration

The `config.local.yaml` file contains settings optimized for local development:

- Redis URL: `redis://localhost:6379/0`
- Input directory: `./data/input`
- Output directory: `./data/output`
- Timeouts suitable for local processing

## Troubleshooting

### Issue: XPC_ERROR_CONNECTION_INVALID on macOS
**Symptom**: Tasks fail with `SyntaxError: Compiler encountered XPC_ERROR_CONNECTION_INVALID`

**Cause**: PyTorch with Metal (MPS) acceleration doesn't work well with high concurrency forking.

**Solution**: Always use `--concurrency=4` or lower when starting Celery workers:
```bash
celery -A docling_service.celery_app worker --loglevel=info --concurrency=4
```

### Issue: Redis Connection to wrong host
**Symptom**: Tasks fail with `ConnectionError: Error 61 connecting to redis:6379`

**Cause**: Processor is using Docker config (`config.yaml`) instead of local config.

**Solution**: Ensure `config.local.yaml` exists and restart all services. The system auto-detects this file.

### Issue: Files not being re-processed
**Symptom**: New files added to an existing directory aren't processed.

**Cause**: The daemon tracks processed directories and won't reprocess them.

**Solution**: Reset the processed directories:
```bash
python utils/reset_daemon.py
# Then restart the daemon
python -m docling_service.daemon restart
```

### Issue: Only some files in directory get processed
**Symptom**: Processing stops partway through a batch (e.g., 4 out of 10 files).

**Cause**: Usually XPC errors causing tasks to fail silently.

**Solution**: 
1. Check Celery worker logs for errors
2. Reduce concurrency: `--concurrency=4`
3. Reset and reprocess: `python utils/reset_daemon.py`

### Redis Connection Refused
```bash
# Check if Redis is running
redis-cli ping

# If not, start it
redis-server --daemonize yes
```

### No Workers Available
```bash
# Check if Celery workers are running
ps aux | grep "[c]elery.*worker"

# If not, start them with correct concurrency
celery -A docling_service.celery_app worker --loglevel=info --concurrency=4
```

### Files Not Processing
1. Check daemon is running: `python -m docling_service.daemon status`
2. Check Redis has tasks: `redis-cli keys "docling_batch:*"`
3. Check worker logs for errors
4. Ensure PDFs are in subdirectories under `data/input/`
5. Check `.processed_dirs.txt` - may need reset if directory was already processed

### Permission Errors
```bash
# Ensure directories exist and are writable
mkdir -p data/input data/output
chmod 755 data/input data/output
```

## Monitoring

### View Processing Logs
```bash
# Watch daemon logs (if running in foreground)
python -m docling_service.daemon start

# Watch Celery worker logs
celery -A docling_service.celery_app worker --loglevel=info
```

### Check Batch Status
```bash
# View batches in Redis
redis-cli keys "docling_batch:*"

# Get batch details
redis-cli hgetall "docling_batch:<batch_id>"
```

### Web Monitoring with Flower
```bash
# Install and run Flower
pip install flower
celery -A docling_service.celery_app flower

# Open browser to http://localhost:5555
```

## Stopping Services

```bash
# Stop daemon
python -m docling_service.daemon stop

# Stop Celery workers
pkill -f "celery.*worker"

# Stop Redis
redis-cli shutdown

# Or stop all at once
pkill -f "docling_service.daemon"
pkill -f "celery.*worker"
redis-cli shutdown
```