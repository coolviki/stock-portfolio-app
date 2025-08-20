# Railway Deployment Guide

This guide explains how to deploy the Stock Portfolio App to Railway as a **monorepo** using GitHub integration.

## Prerequisites

1. A [Railway](https://railway.app/) account
2. This repository connected to your GitHub account

## Deployment Steps (Monorepo Approach)

### 1. Create New Railway Project

1. Go to [Railway](https://railway.app/) and click "**Start a New Project**"
2. Select "**Deploy from GitHub repo**"
3. Connect your GitHub account and select this repository
4. **IMPORTANT**: Leave **Root Directory** blank (deploy entire repo)

### 2. Add PostgreSQL Database

1. In the same Railway project, click "**+ New**" → "**Database**" → "**PostgreSQL**"
2. This creates a PostgreSQL database that will auto-connect to your application

### 3. How It Works (Monorepo Deployment)

The monorepo deployment:
- **Builds both** frontend and backend in one service
- **Serves backend** on Railway's assigned PORT (usually 8000)
- **Frontend is built** but served as static files with the backend
- **Single database** connection for the entire application

### 4. Environment Variables

**Required**: Set these in your Railway service:
- `DATABASE_URL`: Will be automatically provided by Railway PostgreSQL service
- `PORT`: Automatically set by Railway 
- `SECRET_KEY`: Set a secure random key for production (e.g., `openssl rand -hex 32`)
- `CORS_ORIGINS`: Set to your Railway domain (e.g., `https://your-app.railway.app`)

**Optional** (already configured in nixpacks.toml):
- `PYTHONPATH`: `/app`
- `NODE_ENV`: `production`
- `GENERATE_SOURCEMAP`: `false`
- `CI`: `false`

### 4. Database Setup

The PostgreSQL database will be automatically created and connected. The FastAPI application will:
- Automatically create database tables on startup
- Handle migrations through SQLAlchemy

#### Order Date Column Removal (For Existing Deployments)

If you have an existing Railway deployment that includes the old `order_date` column in the transactions table, you need to run the removal migration:

1. Connect to your Railway project via Railway CLI:
   ```bash
   railway login
   railway link [your-project-id]
   ```

2. Run the PostgreSQL migration script:
   ```bash
   railway run python backend/remove_order_date_postgresql.py
   ```

3. Or test the connection first:
   ```bash
   railway run python backend/remove_order_date_postgresql.py test
   ```

This migration will:
- ✅ Remove the redundant `order_date` column from the transactions table
- ✅ Preserve all other data and columns
- ✅ Work safely with PostgreSQL (no downtime required)
- ✅ Auto-verify the migration completed successfully

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