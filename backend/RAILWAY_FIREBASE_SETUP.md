# Firebase Service Account Setup for Railway

## 🔐 Secure Environment Variable Setup

To deploy your Firebase-enabled backend on Railway, you need to set your Firebase service account credentials as environment variables.

### Step 1: Get Your Firebase Service Account JSON

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your project
3. Go to Project Settings → Service Accounts
4. Click "Generate New Private Key"
5. Download the JSON file

### Step 2: Extract Individual Fields

From your `firebase-service-account.json`, extract these fields:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "your-private-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYour-Private-Key\n-----END PRIVATE KEY-----",
  "client_email": "firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com",
  "client_id": "your-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

### Step 3: Set Railway Environment Variables

#### Method 1: Railway CLI (Recommended)
```bash
cd backend
railway login
railway variables set FIREBASE_PROJECT_ID="your-project-id"
railway variables set FIREBASE_PRIVATE_KEY_ID="your-private-key-id"
railway variables set FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYour-Private-Key\n-----END PRIVATE KEY-----"
railway variables set FIREBASE_CLIENT_EMAIL="firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com"
railway variables set FIREBASE_CLIENT_ID="your-client-id"
railway variables set FIREBASE_AUTH_URI="https://accounts.google.com/o/oauth2/auth"
railway variables set FIREBASE_TOKEN_URI="https://oauth2.googleapis.com/token"
```

#### Method 2: Railway Dashboard
1. Go to Railway dashboard
2. Select your backend service
3. Go to Variables tab
4. Add each variable manually

#### Method 3: Base64 Alternative
If you prefer single variable approach:

```bash
# Encode your JSON to base64
base64 -i firebase-service-account.json

# Set the encoded string
railway variables set FIREBASE_SERVICE_ACCOUNT_BASE64="your-base64-encoded-json-here"
```

### Step 4: Required Environment Variables

Make sure these are set in Railway:

**Firebase Credentials (Choose Method 1 OR Method 3):**

**Method 1 - Individual Variables:**
- `FIREBASE_PROJECT_ID`
- `FIREBASE_PRIVATE_KEY_ID`
- `FIREBASE_PRIVATE_KEY` (include the full key with \\n for newlines)
- `FIREBASE_CLIENT_EMAIL`
- `FIREBASE_CLIENT_ID`
- `FIREBASE_AUTH_URI`
- `FIREBASE_TOKEN_URI`

**Method 3 - Base64:**
- `FIREBASE_SERVICE_ACCOUNT_BASE64`

**Additional Variables:**
- `DATABASE_URL=sqlite:///./stock_portfolio.db`
- `SECRET_KEY=your-secret-key`

### Step 5: Deploy

```bash
railway deploy
```

## 🔍 Verification

After deployment, check your logs to ensure Firebase initializes correctly:

```bash
railway logs
```

You should see successful Firebase initialization without credential errors.

## 🚨 Security Notes

- Never commit `firebase-service-account.json` to git
- Use individual environment variables for production
- The backend code automatically handles multiple credential methods
- Environment variables are encrypted and secure on Railway

## 🛠️ Troubleshooting

**Error: "No valid Firebase credentials found"**
- Check all environment variables are set correctly
- Ensure FIREBASE_PRIVATE_KEY includes proper newline formatting
- Try the base64 method as alternative

**Error: "Invalid private key"**
- Make sure FIREBASE_PRIVATE_KEY includes the full key with headers
- Check for escaped newlines (\\n in the environment variable)

**Authentication failures:**
- Verify Firebase project ID matches your frontend configuration
- Check that service account has proper permissions