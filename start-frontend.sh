#!/bin/bash

echo "🚀 Starting Stock Portfolio Frontend..."

# Navigate to frontend directory
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Start the development server
echo "🌟 Starting React development server..."
npm start