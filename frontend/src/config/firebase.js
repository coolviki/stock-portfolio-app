import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

// Check if Firebase environment variables are available
const hasFirebaseConfig = () => {
  return !!(
    process.env.REACT_APP_FIREBASE_API_KEY &&
    process.env.REACT_APP_FIREBASE_AUTH_DOMAIN &&
    process.env.REACT_APP_FIREBASE_PROJECT_ID &&
    process.env.REACT_APP_FIREBASE_API_KEY !== 'your_firebase_api_key'
  );
};

// Firebase configuration with fallback
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY || 'demo-api-key',
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN || 'demo-project.firebaseapp.com',
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID || 'demo-project',
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET || 'demo-project.firebasestorage.app',
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID || '123456789',
  appId: process.env.REACT_APP_FIREBASE_APP_ID || '1:123456789:web:demo'
};

// Initialize Firebase only if proper configuration is available
let app = null;
let auth = null;
let googleProvider = null;

export const FIREBASE_AVAILABLE = hasFirebaseConfig();

if (FIREBASE_AVAILABLE) {
  try {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    googleProvider = new GoogleAuthProvider();
    
    // Configure Google Auth Provider
    googleProvider.setCustomParameters({
      prompt: 'select_account'
    });
    
    console.log('Firebase initialized successfully');
  } catch (error) {
    console.warn('Firebase initialization failed:', error);
    console.warn('Firebase authentication will be disabled');
  }
} else {
  console.warn('Firebase configuration not available. Firebase authentication will be disabled.');
  console.warn('To enable Firebase auth, set the following environment variables:');
  console.warn('- REACT_APP_FIREBASE_API_KEY');
  console.warn('- REACT_APP_FIREBASE_AUTH_DOMAIN');
  console.warn('- REACT_APP_FIREBASE_PROJECT_ID');
  console.warn('- REACT_APP_FIREBASE_STORAGE_BUCKET');
  console.warn('- REACT_APP_FIREBASE_MESSAGING_SENDER_ID');
  console.warn('- REACT_APP_FIREBASE_APP_ID');
}

// Export with null checks
export { auth, googleProvider };
export default app;