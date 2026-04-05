#!/bin/bash
set -e

echo "Starting FixFlow Full-Stack Environment..."

# Start FastAPI backend in the background on port 8000
echo "Booting FastAPI (Backend)..."
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Give backend a moment to start
sleep 3

# Start Next.js frontend on port 7860 (Hugging Face Spaces default)
echo "Booting Next.js (Frontend)..."
cd frontend
PORT=7860 npm start &
FRONTEND_PID=$!

echo "Both services started successfully."

# Wait for any process to exit
wait -n

echo "A service exited abruptly. Shutting down."
# Exit with status of process that exited first
exit $?
