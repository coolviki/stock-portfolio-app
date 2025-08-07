# Multi-stage build for monorepo deployment
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Python backend stage
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY backend/requirements.txt backend/
RUN cd backend && pip install --upgrade pip && pip install -r requirements.txt

# Copy backend code
COPY backend/ backend/

# Copy frontend build from previous stage
COPY --from=frontend-builder /app/frontend/build /app/static

# Create nginx configuration
RUN echo 'server { \
    listen 3001; \
    root /app/static; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://localhost:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/sites-available/default

# Environment variables
ENV PYTHONPATH=/app
ENV NODE_ENV=production
ENV GENERATE_SOURCEMAP=false
ENV CI=false

# Expose port
EXPOSE $PORT

# Create startup script
RUN echo '#!/bin/bash\n\
# Start nginx in background\n\
nginx -g "daemon off;" &\n\
# Start backend\n\
cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]