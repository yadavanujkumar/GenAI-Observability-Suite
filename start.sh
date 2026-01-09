#!/bin/bash
set -e

echo "Starting LLM Observability & Governance Gateway..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please update .env with your API keys and configuration"
    exit 1
fi

# Start Redis in the background (if docker available)
if command -v docker &> /dev/null; then
    echo "Starting Redis container..."
    docker run -d --name llm-redis -p 6379:6379 redis:7-alpine || echo "Redis container already running"
    
    echo "Starting Qdrant container..."
    docker run -d --name llm-qdrant -p 6333:6333 qdrant/qdrant || echo "Qdrant container already running"
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -q -r requirements.txt

# Start FastAPI server
echo "Starting FastAPI gateway on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

sleep 2

# Start Streamlit dashboard
echo "Starting Streamlit dashboard on http://localhost:8501"
streamlit run streamlit/dashboard.py --server.port 8501 &
STREAMLIT_PID=$!

echo "Gateway running!"
echo "- API: http://localhost:8000"
echo "- Dashboard: http://localhost:8501"
echo "- API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

wait
