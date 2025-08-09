# 🚀 Railway PostgreSQL Setup Guide

## Step 1: Add PostgreSQL to Your Railway Project

1. **Go to Railway Dashboard**: https://railway.app/dashboard
2. **Open your `stock-portfolio-app` project**
3. **Click "New Service" → "Database" → "PostgreSQL"**
4. **Railway will automatically provision PostgreSQL and generate connection details**

## Step 2: Configure Environment Variables

In your Railway project dashboard, go to **Variables** tab and add:

```env
DATABASE_URL=${PGDATABASE_URL}
PYTHONPATH=/app/backend
PORT=8000
CORS_ORIGINS=https://your-app.railway.app,http://localhost:3000
```

> **Note**: Railway automatically provides `${PGDATABASE_URL}` when you add PostgreSQL service.

## Step 3: Deploy Your Application 

Your app should now automatically deploy with PostgreSQL support. Railway will:

1. ✅ **Build** using the updated `railway.json` configuration
2. ✅ **Install** PostgreSQL dependencies from `requirements.txt`  
3. ✅ **Create tables** automatically on startup via `main.py:22`
4. ✅ **Start** the FastAPI backend on the configured port

## Step 4: Initialize Database Tables

### Option A: Automatic Initialization (Recommended)

Your app will automatically create tables when it starts up because of this line in `main.py`:
```python
Base.metadata.create_all(bind=engine)  # Line 22
```

### Option B: Manual Initialization via Railway CLI

If you want to manually initialize or verify:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link to your project
railway login
railway link [select your project]

# Initialize PostgreSQL tables
railway run python backend/init_postgresql.py

# Verify tables were created
railway run python -c "
from backend.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT table_name FROM information_schema.tables WHERE table_schema=\\'public\\';'))
    tables = [row[0] for row in result.fetchall()]
    print('Tables created:', tables)
"
```

## Step 5: Migrate Existing Data (If Needed)

If you have existing SQLite data to migrate:

```bash
# Set your Railway PostgreSQL URL locally for testing
export DATABASE_URL="your-railway-postgresql-url"

# Test connection
python backend/migrate_to_postgresql.py test

# Run migration
python backend/migrate_to_postgresql.py

# Or run migration directly on Railway
railway run python backend/migrate_to_postgresql.py
```

## Step 6: Update Frontend URL

Update your frontend environment to point to the new Railway backend URL:

```env
# In your frontend deployment
REACT_APP_API_URL=https://your-backend.railway.app
```

## Verification Checklist

- [ ] PostgreSQL service added to Railway project
- [ ] Environment variables configured (`DATABASE_URL`, `PYTHONPATH`, `PORT`)
- [ ] Application deployed successfully
- [ ] Database tables created (`users`, `securities`, `transactions`)
- [ ] API endpoints responding correctly
- [ ] Frontend can connect to backend
- [ ] Contract note upload working
- [ ] Price tooltips functioning

## Troubleshooting

### Connection Issues
```bash
# Check Railway logs
railway logs --follow

# Test database connection
railway run python -c "
import os
from sqlalchemy import create_engine, text
url = os.getenv('DATABASE_URL')
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT version();'))
    print('PostgreSQL:', result.fetchone()[0])
"
```

### Table Creation Issues
```bash
# Manually create tables
railway run python backend/init_postgresql.py

# Check what tables exist
railway run python -c "
from backend.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT table_name FROM information_schema.tables WHERE table_schema=\\'public\\';'))
    print('Existing tables:', [row[0] for row in result.fetchall()])
"
```

### Migration Issues
```bash
# Verify your local SQLite data first
sqlite3 backend/stock_portfolio.db ".tables"
sqlite3 backend/stock_portfolio.db "SELECT COUNT(*) FROM users;"
sqlite3 backend/stock_portfolio.db "SELECT COUNT(*) FROM securities;"
sqlite3 backend/stock_portfolio.db "SELECT COUNT(*) FROM transactions;"

# Then run migration
railway run python backend/migrate_to_postgresql.py
```

## 🎉 Success!

Once setup is complete, your stock portfolio app will be running on Railway with:

- ✅ **Production PostgreSQL database**
- ✅ **Scalable connection pooling**
- ✅ **All existing features working**
- ✅ **Contract note parsing**
- ✅ **Price tooltips with real-time data**
- ✅ **Multi-user support**
- ✅ **Portfolio analytics**

Your Railway URLs will be:
- **Backend API**: `https://your-backend.railway.app`
- **Frontend App**: `https://your-frontend.railway.app` (if deployed)
- **PostgreSQL**: Available via `${PGDATABASE_URL}` environment variable