#!/bin/bash

echo "Starting Docling Batch Processor"
echo "===================================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Please run:"
    echo "python -m venv .venv"
    echo "source .venv/bin/activate"
    echo "pip install uv && uv pip install -e ."
    exit 1
fi

# Check if config.local.yaml exists
if [ ! -f "config.local.yaml" ]; then
    echo "config.local.yaml not found. This file is required for local development."
    exit 1
fi

# Function to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Start Redis if not running
if redis-cli ping > /dev/null 2>&1; then
    echo "Redis is already running"
else
    echo "Starting Redis..."
    redis-server --daemonize yes
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "Redis started successfully"
    else
        echo "Failed to start Redis. Please install with: brew install redis"
        exit 1
    fi
fi

# Kill any existing Celery workers
if is_running "celery.*worker"; then
    echo "Stopping existing Celery workers..."
    pkill -f "celery.*worker"
    sleep 2
fi

# Start Celery worker with reduced concurrency for macOS
echo "Starting Celery worker (concurrency=4)..."
source .venv/bin/activate
celery -A docling_service.celery_app worker --loglevel=info --concurrency=4 --detach
sleep 3

if is_running "celery.*worker"; then
    echo "Celery worker started successfully"
else
    echo "Failed to start Celery worker"
    exit 1
fi

# Stop any existing daemon
if [ -f "daemon.pid" ]; then
    echo "Stopping existing daemon..."
    source .venv/bin/activate
    python -m docling_service.daemon stop
    sleep 2
fi

# Start the daemon
echo "Starting daemon with config.local.yaml..."
source .venv/bin/activate
python -m docling_service.daemon start config.local.yaml &
sleep 3

if [ -f "daemon.pid" ]; then
    echo "Daemon started successfully"
else
    echo "Daemon may not have started properly"
fi

mkdir -p data/input data/output

echo ""
echo "===================================================="
echo "All services started successfully!"
echo ""
echo "To process PDFs:"
echo "  1. Create a directory: mkdir data/input/my_batch"
echo "  2. Copy PDFs there: cp *.pdf data/input/my_batch/"
echo "  3. Wait ~10 seconds for processing"
echo "  4. Check output: ls data/output/my_batch/"
echo ""
echo "To monitor:"
echo "  - Daemon status: python -m docling_service.daemon status"
echo "  - Redis batches: redis-cli keys 'docling_batch:*'"
echo "  - Worker logs: tail -f *.log (if using log files)"
echo ""
echo "To stop all services:"
echo "  ./stop_local.sh"
echo "===================================================="
