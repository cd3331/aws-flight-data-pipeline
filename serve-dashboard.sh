#!/bin/bash

# Flight Data Dashboard Server
# Starts a local HTTP server to serve the dashboard

PORT=${1:-8000}
echo "🚀 Starting Flight Data Dashboard..."
echo "📊 Dashboard will be available at: http://localhost:$PORT/dashboard.html"
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

# Start Python HTTP server
python3 -m http.server $PORT