import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

// Get API base URL
const getApiBaseUrl = () => {
  return process.env.REACT_APP_API_URL || 
         (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');
};

// Firebase configuration state
let app = null;
let auth = null;
let googleProvider = null;
let FIREBASE_AVAILABLE = false;
let configPromise = null;

// Helper function to get environment variable with fallbacks
const getEnvVar = (primaryKey, fallbackKey = null, defaultValue = null) => {
  return process.env[primaryKey] || (fallbackKey ? process.env[fallbackKey] : null) || defaultValue;
};

// Check if Firebase environment variables are available locally
const hasLocalFirebaseConfig = () => {
  const apiKey = getEnvVar('REACT_APP_FIREBASE_API_KEY');
  const projectId = getEnvVar('REACT_APP_FIREBASE_PROJECT_ID');
  
  return !!(
    apiKey &&
    projectId &&
    apiKey !== 'your_firebase_api_key' &&
    apiKey !== 'demo-api-key'
  );
};

// Local Firebase configuration
const getLocalFirebaseConfig = () => {
  return {
    apiKey: getEnvVar('REACT_APP_FIREBASE_API_KEY', null, 'demo-api-key'),
    authDomain: getEnvVar('REACT_APP_FIREBASE_AUTH_DOMAIN') || 
               getEnvVar('REACT_APP_FIREBASE_PROJECT_ID') + '.firebaseapp.com' ||
               'demo-project.firebaseapp.com',
    projectId: getEnvVar('REACT_APP_FIREBASE_PROJECT_ID', null, 'demo-project'),
    storageBucket: getEnvVar('REACT_APP_FIREBASE_STORAGE_BUCKET') ||
                   getEnvVar('REACT_APP_FIREBASE_PROJECT_ID') + '.appspot.com' ||
                   'demo-project.appspot.com',
    messagingSenderId: getEnvVar('REACT_APP_FIREBASE_MESSAGING_SENDER_ID', null, '123456789'),
    appId: getEnvVar('REACT_APP_FIREBASE_APP_ID', null, '1:123456789:web:demo')
  };
};

// Fetch Firebase configuration from backend API
const fetchFirebaseConfig = async () => {
  try {
    const response = await fetch(`${getApiBaseUrl()}/config/firebase`);
    if (response.ok) {
      return await response.json();
    }
    throw new Error(`Failed to fetch Firebase config: ${response.status}`);
  } catch (error) {
    console.warn('Failed to fetch Firebase config from API:', error);
    return null;
  }
};

// Initialize Firebase with configuration
const initializeFirebaseWithConfig = (config) => {
  try {
    if (!config || !config.apiKey || !config.projectId || config.apiKey === 'demo-api-key') {
      return false;
    }

    app = initializeApp(config);
    auth = getAuth(app);
    googleProvider = new GoogleAuthProvider();
    
    // Configure Google Auth Provider
    googleProvider.setCustomParameters({
      prompt: 'select_account'
    });
    
    console.log('Firebase initialized successfully with config:', {
      projectId: config.projectId,
      authDomain: config.authDomain
    });
    
    return true;
  } catch (error) {
    console.warn('Firebase initialization failed:', error);
    return false;
  }
};

// Initialize Firebase configuration
const initializeFirebase = async () => {
  if (configPromise) {
    return configPromise;
  }

  configPromise = (async () => {
    // Try local environment variables first
    if (hasLocalFirebaseConfig()) {
      console.log('Using local Firebase configuration');
      const localConfig = getLocalFirebaseConfig();
      FIREBASE_AVAILABLE = initializeFirebaseWithConfig(localConfig);
      return FIREBASE_AVAILABLE;
    }

    // Fall back to API configuration
    console.log('Fetching Firebase configuration from API');
    const apiConfig = await fetchFirebaseConfig();
    
    if (apiConfig && apiConfig.available) {
      console.log('Using API Firebase configuration');
      FIREBASE_AVAILABLE = initializeFirebaseWithConfig(apiConfig);
    } else {
      console.warn('Firebase configuration not available from API');
      FIREBASE_AVAILABLE = false;
    }

    if (!FIREBASE_AVAILABLE) {
      console.warn('Firebase authentication will be disabled.');
      console.warn('To enable Firebase auth, ensure environment variables are set in Railway:');
      console.warn('- FIREBASE_API_KEY');
      console.warn('- FIREBASE_AUTH_DOMAIN');
      console.warn('- FIREBASE_PROJECT_ID');
      console.warn('- FIREBASE_STORAGE_BUCKET');
      console.warn('- FIREBASE_MESSAGING_SENDER_ID');
      console.warn('- FIREBASE_APP_ID');
    }

    return FIREBASE_AVAILABLE;
  })();

  return configPromise;
};

// Initialize immediately
initializeFirebase();

// Export async getter functions
export const getAuth = async () => {
  await initializeFirebase();
  return auth;
};

export const getGoogleProvider = async () => {
  await initializeFirebase();
  return googleProvider;
};

export const isFirebaseAvailable = async () => {
  await initializeFirebase();
  return FIREBASE_AVAILABLE;
};

// Export synchronous versions for backward compatibility (may be null initially)
export { auth, googleProvider };

// Export the async availability checker
export const FIREBASE_AVAILABLE_PROMISE = initializeFirebase();

// Synchronous check (may be false initially, use isFirebaseAvailable() for accurate check)
export { FIREBASE_AVAILABLE };

export default app;