# Railway Deployment Guide

This guide explains how to deploy the Stock Portfolio App to Railway using GitHub integration.

## Prerequisites

1. A [Railway](https://railway.app/) account
2. This repository connected to your GitHub account

## Deployment Steps

### 1. Create New Railway Project

1. Go to [Railway](https://railway.app/) and click "**Start a New Project**"
2. You'll create **3 separate services** in this project

### 2. Deploy Backend Service (FIRST)

1. Click "**+ New**" → "**Deploy from GitHub repo**"
2. Connect your GitHub account and select this repository  
3. **CRITICAL**: Set **Root Directory** to `backend` 
4. Click "**Deploy**"
5. Railway will use `backend/nixpacks.toml` and build only the Python FastAPI backend

### 3. Deploy Frontend Service (SECOND)

1. In the same Railway project, click "**+ New**" → "**Deploy from GitHub repo**" 
2. Select the same repository
3. **CRITICAL**: Set **Root Directory** to `frontend`
4. Click "**Deploy**" 
5. Railway will use `frontend/nixpacks.toml` and build only the React frontend

### 4. Add Database (THIRD)

1. Click "**+ New**" → "**Database**" → "**PostgreSQL**"
2. This creates a PostgreSQL database that will auto-connect to your backend

### 2. Service Configuration

- **Backend Service**: FastAPI application running on port 8000
- **Frontend Service**: React application served with nginx  
- **PostgreSQL Database**: Automatically provisioned

### 3. Environment Variables

#### Backend Environment Variables
**Required**: Set these in the Railway backend service:
- `DATABASE_URL`: Will be automatically provided by Railway PostgreSQL service
- `PORT`: Automatically set by Railway (usually 8000)
- `SECRET_KEY`: Set a secure random key for production (e.g., `openssl rand -hex 32`)
- `CORS_ORIGINS`: Set to your frontend Railway domain (e.g., `https://your-frontend.railway.app`)

**Optional environment variables**:
- `PYTHONPATH`: Set to `/app` (already configured in nixpacks.toml)

#### Frontend Environment Variables  
**Required**: Set these in the Railway frontend service:
- `REACT_APP_API_URL`: Set to your backend Railway domain (e.g., `https://your-backend.railway.app`)
- `PORT`: Automatically set by Railway (usually 3000)

**Optional**:
- `GENERATE_SOURCEMAP`: Set to `false` for production (already configured)
- `CI`: Set to `false` to avoid build warnings (already configured)

### 4. Database Setup

The PostgreSQL database will be automatically created and connected. The FastAPI application will:
- Automatically create database tables on startup
- Handle migrations through SQLAlchemy

### 5. Custom Domains (Optional)

1. Go to your Railway project dashboard
2. Click on the service you want to add a domain to
3. Go to "Settings" → "Domains"
4. Add your custom domain
5. Update the CORS_ORIGINS environment variable in the backend if needed

## File Structure for Railway

The following files have been added/modified for Railway deployment:

```
├── railway.toml                 # Main Railway configuration
├── backend/
│   ├── Procfile                # Process definition for backend
│   ├── nixpacks.toml          # Backend build configuration
│   └── .env.example           # Updated environment template
├── frontend/
│   ├── nixpacks.toml          # Frontend build configuration
│   └── .env.example           # Frontend environment template
└── RAILWAY_DEPLOYMENT.md      # This guide
```

## Key Configuration Changes Made

### Backend Changes
- Updated CORS origins to use environment variables
- Made port configurable via environment variable
- Updated `.env.example` for production settings
- Added Railway-specific build configurations

### Frontend Changes  
- Updated API URL to use environment variables
- Added `serve` package for production static file serving
- Created Nixpacks configuration for Railway builds

### Database
- PostgreSQL support already existed in requirements.txt
- Database connection automatically configured for Railway PostgreSQL

## Monitoring and Logs

1. **View Logs**: Go to your Railway project → Select service → "Logs" tab
2. **Monitor Performance**: Use Railway's built-in metrics
3. **Database Access**: Use Railway's database tools or connect via DATABASE_URL

## Troubleshooting

### Common Issues

1. **Build Failures**: Check the build logs in Railway dashboard
2. **CORS Errors**: Ensure CORS_ORIGINS includes your Railway frontend domain
3. **Database Connection Issues**: Verify DATABASE_URL is properly set
4. **Static Files Not Loading**: Check that the frontend build completed successfully

### Support

- Railway Documentation: https://docs.railway.app/
- Railway Discord: https://discord.gg/railway
- GitHub Issues: Create issues in this repository for app-specific problems

## Cost Considerations

- Railway offers a generous free tier
- Costs scale based on usage (CPU, memory, bandwidth)
- PostgreSQL database included in usage calculations
- Monitor usage in Railway dashboard

## Security Notes

- Environment variables are securely managed by Railway
- Database passwords auto-generated and managed
- HTTPS automatically enabled for all Railway domains
- Consider adding authentication for production use

## Manual Deployment Alternative

If you prefer manual deployment over GitHub integration:

1. Install Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`  
3. Initialize: `railway init`
4. Deploy: `railway up`