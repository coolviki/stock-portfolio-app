#\!/bin/bash
# Railway startup script for stock portfolio application

echo "🚀 Starting Stock Portfolio Backend on Railway..."
echo "📍 Working directory: $(pwd)"
echo "📂 Contents: $(ls -la)"
echo "🔌 Port: ${PORT:-8000}"

# Ensure backend module is accessible
export PYTHONPATH="/app:${PYTHONPATH}"

# Start the server
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
EOF < /dev/null