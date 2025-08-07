#!/bin/bash
set -e

echo "🚀 Starting Stock Portfolio App (Monorepo)"

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
pip install --upgrade pip
pip install -r requirements.txt
cd ..

# Install frontend dependencies and build
echo "📦 Installing frontend dependencies..."
cd frontend
npm ci
echo "🔨 Building frontend..."
npm run build
cd ..

echo "✅ Build complete!"

# Start backend server
echo "🌟 Starting backend server on port ${PORT:-8000}..."
cd backend
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}