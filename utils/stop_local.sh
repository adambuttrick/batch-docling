#!/bin/bash

echo "Stopping Docling Batch Processor"
echo "===================================================="

# Stop daemon
if [ -f "daemon.pid" ]; then
    echo "Stopping daemon..."
    source .venv/bin/activate
    python -m docling_service.daemon stop
    sleep 2
    echo "Daemon stopped"
else
    echo "No daemon PID file found"
fi

# Stop Celery workers
if pgrep -f "celery.*worker" > /dev/null 2>&1; then
    echo "Stopping Celery workers..."
    pkill -f "celery.*worker"
    sleep 2
    echo "Celery workers stopped"
else
    echo "No Celery workers running"
fi

# Stop Redis with confirmation
if redis-cli ping > /dev/null 2>&1; then
    echo ""
    read -p "Stop Redis? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping Redis..."
        redis-cli shutdown
        sleep 2
        if redis-cli ping > /dev/null 2>&1; then
            echo "Failed to stop Redis"
        else
            echo "Redis stopped"
        fi
    else
        echo "Redis kept running (preserves state between sessions)"
    fi
else
    echo "Redis is not running"
fi

echo ""
echo "===================================================="
echo "Services stopped"
echo "===================================================="
