#!/bin/bash
echo "Stopping existing services..."
pkill -f uvicorn || true
pkill -f worker_process.py || true
sleep 1

echo "Starting API server..."
PYTHONPATH=. nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
sleep 2

echo "Starting task worker..."
PYTHONPATH=. nohup python3 worker_process.py > worker.log 2>&1 &
sleep 2

echo "Services started. Checking port 8000:"
netstat -ltn | grep :8000 || echo "Port 8000 not listening!"
