# 🔒 Firebase Security Notice

## Required File: firebase-service-account.json

This file is required for Firebase Authentication but is **NOT** included in the repository for security reasons.

### How to obtain this file:

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Project Settings (⚙️) > Service Accounts tab
4. Click "Generate new private key"
5. Download the JSON file
6. Rename it to `firebase-service-account.json`
7. Place it in this `backend/` directory

### Security Guidelines:

- ✅ **DO**: Keep this file in your local `backend/` directory
- ✅ **DO**: Add it to production deployments securely
- ❌ **DON'T**: Commit this file to git (it's already in .gitignore)
- ❌ **DON'T**: Share this file or its contents

### File Template:

See `firebase-service-account.json.template` for the expected structure.

### Production Deployment:

For production, upload this file to your deployment platform or use secure environment variables.

---

**⚠️ This file contains sensitive credentials that allow access to your Firebase project. Handle with care!**