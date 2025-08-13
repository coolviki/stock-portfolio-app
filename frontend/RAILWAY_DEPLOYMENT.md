# Frontend Railway Deployment Guide

This directory contains multiple Railway configuration files for deploying the React frontend.

## 📁 Configuration Files

### 1. **railway.toml** (Primary)
- Main Railway configuration file
- Defines build and deployment settings
- Recommended approach for most deployments

### 2. **railway.json** (Alternative)
- JSON format Railway configuration
- Includes health checks and restart policies
- More detailed configuration options

### 3. **nixpacks.toml** (Build System)
- Nixpacks configuration for Railway's build system
- Defines Node.js version and build commands
- Automatically detected by Railway

### 4. **Dockerfile** (Container)
- Docker-based deployment option
- Multi-stage build for optimized production
- Alternative to Nixpacks

### 5. **Procfile** (Process)
- Simple process definition
- Railway/Heroku compatible
- Defines web server command

## 🚀 Deployment Methods

### Method 1: Railway CLI (Recommended)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Add environment variables
railway variables set REACT_APP_FIREBASE_API_KEY="your_api_key"
railway variables set REACT_APP_FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
railway variables set REACT_APP_FIREBASE_PROJECT_ID="your-project-id"
railway variables set REACT_APP_FIREBASE_STORAGE_BUCKET="your-project.firebasestorage.app"
railway variables set REACT_APP_FIREBASE_MESSAGING_SENDER_ID="123456789"
railway variables set REACT_APP_FIREBASE_APP_ID="your_app_id"
railway variables set REACT_APP_API_URL="https://your-backend.railway.app"

# Deploy
railway deploy
```

### Method 2: GitHub Integration
1. Push code to GitHub repository
2. Connect repository to Railway
3. Set environment variables in Railway dashboard
4. Deploy automatically on push

### Method 3: Railway Dashboard
1. Create new project in Railway dashboard
2. Connect GitHub repository or upload files
3. Set environment variables
4. Deploy

## 🔧 Environment Variables

Set these in Railway dashboard or via CLI:

### Required Firebase Variables:
```bash
REACT_APP_FIREBASE_API_KEY=your_firebase_api_key
REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your-project-id
REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
REACT_APP_FIREBASE_APP_ID=your_app_id
```

### Required API Variables:
```bash
REACT_APP_API_URL=https://your-backend.railway.app
```

### Build Variables (Optional):
```bash
NODE_ENV=production
GENERATE_SOURCEMAP=false
CI=false
PORT=3000
```

## 📋 Deployment Checklist

- [ ] Firebase project created and configured
- [ ] All environment variables set in Railway
- [ ] Backend deployed and API URL updated
- [ ] Domain configured (if using custom domain)
- [ ] Firebase authorized domains updated with Railway domain
- [ ] CORS configured in backend for Railway frontend domain

## 🔍 Build Process

Railway will automatically:
1. Detect Node.js project
2. Run `npm ci` to install dependencies
3. Run `npm run build` to create production build
4. Serve static files using `serve` package
5. Expose on port 3000 (or Railway-assigned port)

## 🐛 Troubleshooting

### Build Failures:
- Check Node.js version compatibility (using 18.x)
- Verify all environment variables are set
- Check build logs in Railway dashboard

### Runtime Issues:
- Verify Firebase configuration
- Check API URL is correct and backend is deployed
- Review browser console for errors

### Environment Variable Issues:
- Remember REACT_APP_ prefix for frontend variables
- Check variables are set in Railway dashboard
- Restart deployment after changing variables

## 🔗 Useful Commands

```bash
# Check Railway status
railway status

# View logs
railway logs

# Open deployed app
railway open

# List environment variables
railway variables

# Connect to existing project
railway link
```

## 📚 Documentation

- [Railway Documentation](https://docs.railway.app/)
- [Nixpacks Documentation](https://nixpacks.com/)
- [React Deployment Guide](https://create-react-app.dev/docs/deployment/)