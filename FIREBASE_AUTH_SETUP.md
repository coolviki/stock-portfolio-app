# Firebase Authentication Setup Guide

This guide will help you set up Firebase Authentication with Google Sign-In for both local development and remote deployment.

## Prerequisites

- Google/Firebase account
- Domain name for remote deployment (if using Railway or similar)

## Step 1: Firebase Project Setup

1. **Create Firebase Project**
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Click "Create a project" or select existing project
   - Follow the setup wizard

2. **Enable Authentication**
   - In Firebase Console, go to "Authentication" > "Sign-in method"
   - Enable "Google" sign-in provider
   - Set your support email

3. **Configure OAuth consent screen (if needed)**
   - Go to Google Cloud Console for your project
   - Navigate to "APIs & Services" > "OAuth consent screen"
   - Configure the consent screen with your app details

## Step 2: Get Firebase Configuration

### Frontend Configuration

1. **Add Firebase Web App**
   - In Firebase Console, go to Project Settings (gear icon)
   - Click "Add app" and select Web (</> icon)
   - Register your app with a nickname
   - Copy the Firebase configuration object

2. **Web App Configuration Example**:
   ```javascript
   const firebaseConfig = {
     apiKey: "AIzaSyC...",
     authDomain: "your-project.firebaseapp.com",
     projectId: "your-project-id",
     storageBucket: "your-project.firebasestorage.app",
     messagingSenderId: "123456789",
     appId: "1:123456789:web:abcdef123456"
   };
   ```

### Backend Configuration

1. **Generate Service Account Key**
   - In Firebase Console, go to Project Settings > "Service accounts"
   - Click "Generate new private key"
   - Download the JSON file
   - Save as `firebase-service-account.json` in your backend directory
   
   **⚠️ SECURITY WARNING:**
   - This file contains sensitive credentials
   - NEVER commit it to version control
   - It's already added to .gitignore
   - Use secure environment variables for production

## Step 3: Environment Configuration

### Frontend Environment (.env)

Create `/frontend/.env`:

```env
# Firebase Configuration
REACT_APP_FIREBASE_API_KEY=AIzaSyC...
REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your-project-id
REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
REACT_APP_FIREBASE_APP_ID=1:123456789:web:abcdef123456

# API Configuration
REACT_APP_API_URL=http://localhost:8000

# Build configuration
GENERATE_SOURCEMAP=false
CI=false
```

### Backend Environment (.env)

Update `/backend/.env`:

```env
# Database Configuration
DATABASE_URL=sqlite:///./stock_portfolio.db

# Security
SECRET_KEY=your-secret-key-here-change-in-production

# Firebase Configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json

# Application Settings
ENVIRONMENT=development
DEBUG=True
CORS_ORIGINS=http://localhost:3000
```

## Step 4: Configure Authorized Domains

### Local Development
In Firebase Console > Authentication > Settings > Authorized domains:
- Add: `localhost`

### Production Deployment
- Add your production domain: `your-app-domain.com`
- For Railway: `your-service.railway.app`

## Step 5: Environment-Specific Setup

### Local Development

1. **Frontend (.env)**:
   ```env
   REACT_APP_FIREBASE_API_KEY=your_api_key
   REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   REACT_APP_FIREBASE_PROJECT_ID=your-project-id
   REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
   REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
   REACT_APP_FIREBASE_APP_ID=your_app_id
   REACT_APP_API_URL=http://localhost:8000
   ```

2. **Backend Files**:
   - Download your Firebase service account JSON from Firebase Console
   - Rename it to `firebase-service-account.json` 
   - Place it in the backend directory (it's gitignored for security)
   - Update `.env` with Firebase project ID

3. **Start Services**:
   ```bash
   ./start-backend.sh
   ./start-frontend.sh
   ```

### Remote Deployment (Railway/Vercel/etc.)

1. **Frontend Environment Variables**:
   ```env
   REACT_APP_FIREBASE_API_KEY=your_api_key
   REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   REACT_APP_FIREBASE_PROJECT_ID=your-project-id
   REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
   REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
   REACT_APP_FIREBASE_APP_ID=your_app_id
   REACT_APP_API_URL=https://your-backend-domain.railway.app
   ```

2. **Backend Environment Variables**:
   ```env
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json
   CORS_ORIGINS=https://your-frontend-domain.railway.app
   ```

3. **Service Account Key**:
   - **For Railway/Heroku**: Upload `firebase-service-account.json` to your backend service
   - **For Google Cloud/Vercel**: Use Google Cloud Application Default Credentials
   - **Never include the key file in your git repository**

## Step 6: Database Migration

Run the database migration to add Firebase auth columns:

```bash
cd backend
python3 add_firebase_auth_migration.py
```

## Step 7: Testing

### Local Testing
1. Start both services
2. Navigate to `http://localhost:3000`
3. Click "Continue with Google"
4. Complete Google authentication
5. Verify user creation in database

### Production Testing
1. Deploy both frontend and backend
2. Set all environment variables
3. Update Firebase authorized domains
4. Test the complete authentication flow

## Step 8: Railway-Specific Configuration

### Environment Variables

**Backend Service:**
```
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json
CORS_ORIGINS=https://your-frontend.railway.app
```

**Frontend Service:**
```
REACT_APP_FIREBASE_API_KEY=your_api_key
REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your-project-id
REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
REACT_APP_FIREBASE_APP_ID=your_app_id
REACT_APP_API_URL=https://your-backend.railway.app
```

### File Upload
Upload the `firebase-service-account.json` file to your Railway backend service.

## Step 9: Security Configuration

### 🔒 Critical Security Guidelines

#### **Service Account Key Security**
```bash
# ✅ DO
- Keep firebase-service-account.json in .gitignore
- Store in secure environment variables for production
- Limit service account permissions to minimum required
- Rotate keys periodically

# ❌ DON'T
- NEVER commit service account keys to git
- NEVER share keys in chat/email
- NEVER store in public locations
- NEVER use in client-side code
```

#### **Firebase Security Rules**
No additional rules needed for Authentication, but consider:

1. **Rate Limiting**: Enable Firebase Authentication rate limiting
2. **Email Verification**: Enforce email verification if needed
3. **Authorized Domains**: Keep the list minimal and secure
4. **API Key Restrictions**: Restrict API keys by domain/IP

#### **Backend Security**
```python
# The backend verifies Firebase tokens on each request
# This ensures only authenticated users can access the API
# Tokens are validated against Firebase's public keys
```

#### **Production Security Checklist**
- [ ] Service account key stored securely (not in git)
- [ ] API keys restricted by domain
- [ ] Authorized domains configured properly
- [ ] CORS origins set correctly
- [ ] HTTPS enforced in production
- [ ] Rate limiting enabled
- [ ] Error messages don't expose sensitive info

## Troubleshooting

### Common Issues

1. **"Firebase: Error (auth/configuration-not-found)"**
   - Check that all Firebase config variables are set
   - Verify the project ID matches your Firebase project

2. **"Firebase: Error (auth/operation-not-supported-in-this-environment)"**
   - Check that your domain is in the authorized domains list
   - Ensure you're using HTTPS in production

3. **Backend Token Verification Fails**
   - Verify the service account key file is present
   - Check that FIREBASE_PROJECT_ID matches your project
   - Ensure the service account has proper permissions

4. **CORS Errors**
   - Update CORS_ORIGINS in backend to match frontend domain
   - Ensure both HTTP and HTTPS variants are configured

5. **"auth/popup-blocked" Errors**
   - The component automatically falls back to redirect method
   - Users should allow popups for better UX

### Debug Tips

1. **Check browser console** for Firebase errors
2. **Verify network requests** in browser dev tools
3. **Check backend logs** for token verification issues
4. **Test with incognito mode** to avoid cache issues

## Features

The Firebase Auth integration includes:

- **Google Sign-In** with popup and redirect fallback
- **Beautiful UI** with loading states and error handling
- **Automatic User Creation** with unique username generation
- **Profile Information** including name and picture
- **Email Verification Status** tracking
- **Secure Token Verification** on backend
- **Multi-User Support** with profile pictures in UI

## Migration from Username Auth

Existing username-based users can continue using the system:

1. **Parallel Authentication**: Both systems work simultaneously
2. **Email Matching**: Firebase users can link to existing accounts by email
3. **Gradual Migration**: Users can switch to Firebase auth over time
4. **Admin Panel**: Manage both user types in the admin interface

## Production Checklist

- [ ] Firebase project created and configured
- [ ] Google Sign-In provider enabled
- [ ] Service account key generated and uploaded
- [ ] Environment variables set in deployment platform
- [ ] Authorized domains configured for production
- [ ] CORS origins updated for production domains
- [ ] Database migration completed
- [ ] SSL/HTTPS enabled
- [ ] Error monitoring configured
- [ ] Backup strategy in place

## Support

For issues specific to:
- **Firebase Configuration**: Check Firebase Console documentation
- **Google Sign-In**: Refer to Google Identity documentation
- **Deployment Issues**: Check your platform's documentation (Railway, Vercel, etc.)
- **Database Issues**: Verify migration was successful