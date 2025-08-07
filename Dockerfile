# Multi-stage build for monorepo deployment
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./

# Install dependencies with npm install instead of ci
RUN npm install

COPY frontend/ ./
RUN CI=false GENERATE_SOURCEMAP=false npm run build

# Python backend stage  
FROM python:3.9-slim

WORKDIR /app

# Set environment variables to avoid warnings
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH=/app
ENV NODE_ENV=production

# Install backend dependencies
COPY backend/requirements.txt backend/
RUN pip install --upgrade pip && \
    cd backend && pip install -r requirements.txt

# Copy backend code
COPY backend/ backend/

# Copy frontend build from previous stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Expose port
EXPOSE $PORT

# Start backend (which serves frontend in production)
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"]