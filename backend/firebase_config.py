import os
import json
import base64
import logging
from typing import Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional Firebase imports - handle gracefully if not available
try:
    import firebase_admin
    from firebase_admin import credentials, auth
    FIREBASE_AVAILABLE = True
    logger.info("Firebase admin SDK imported successfully")
except ImportError:
    logger.warning("firebase_admin not available. Firebase authentication will be disabled.")
    print("Warning: firebase_admin not available. Firebase authentication will be disabled.")
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    credentials = None
    auth = None

def print_environment_variables():
    """Print environment variables for debugging, excluding secrets"""
    logger.info("=== ENVIRONMENT VARIABLES (excluding secrets) ===")
    
    # List of secret/sensitive environment variable patterns to exclude
    secret_patterns = [
        'KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'PRIVATE', 'CREDENTIAL', 
        'CLIENT_SECRET', 'API_SECRET', 'AUTH_TOKEN', 'FIREBASE_PRIVATE_KEY'
    ]
    
    # Get all environment variables
    env_vars = dict(os.environ)
    
    # Print environment variables, filtering out secrets
    for key, value in sorted(env_vars.items()):
        # Check if this is a secret variable
        is_secret = any(pattern in key.upper() for pattern in secret_patterns)
        
        if is_secret:
            if value:
                logger.info(f"{key}: *** (REDACTED - {len(value)} characters)")
            else:
                logger.info(f"{key}: *** (REDACTED - empty)")
        else:
            logger.info(f"{key}: {value}")
    
    logger.info("=== END ENVIRONMENT VARIABLES ===")

def get_firebase_credentials():
    """Get Firebase credentials from environment variables or file"""
    logger.info("Attempting to get Firebase credentials...")
    
    if not FIREBASE_AVAILABLE:
        logger.error("Firebase SDK not available, cannot get credentials")
        return None
    
    # Method 1: Individual environment variables (Production recommended)
    if os.getenv('FIREBASE_PRIVATE_KEY'):
        logger.info("Using individual environment variables for Firebase credentials")
        logger.info(f"Firebase Project ID: {os.getenv('FIREBASE_PROJECT_ID', 'NOT SET')}")
        logger.info(f"Firebase Client Email: {os.getenv('FIREBASE_CLIENT_EMAIL', 'NOT SET')}")
        logger.info(f"Firebase Private Key ID: {os.getenv('FIREBASE_PRIVATE_KEY_ID', 'NOT SET')}")
        logger.info(f"Firebase Client ID: {os.getenv('FIREBASE_CLIENT_ID', 'NOT SET')}")
        
        try:
            cred_dict = {
                "type": "service_account",
                "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
                "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                "auth_uri": os.getenv('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                "token_uri": os.getenv('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('FIREBASE_CLIENT_EMAIL', '').replace('@', '%40')}"
            }
            logger.info("Successfully created credentials dictionary from environment variables")
            return credentials.Certificate(cred_dict)
        except Exception as e:
            logger.error(f"Failed to create credentials from environment variables: {e}")
            return None
    
    # Method 2: Base64 encoded JSON (Alternative)
    elif os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64'):
        logger.info("Using base64 encoded service account for Firebase credentials")
        try:
            service_account_json = base64.b64decode(os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64'))
            cred_dict = json.loads(service_account_json)
            logger.info(f"Successfully decoded base64 service account for project: {cred_dict.get('project_id', 'UNKNOWN')}")
            return credentials.Certificate(cred_dict)
        except Exception as e:
            logger.error(f"Error decoding base64 service account: {e}")
            print(f"Error decoding base64 service account: {e}")
            return None
    
    # Method 3: File path (Development fallback)
    elif os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH'):
        service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
        logger.info(f"Using service account file path: {service_account_path}")
        if os.path.exists(service_account_path):
            logger.info(f"Service account file exists: {service_account_path}")
            try:
                return credentials.Certificate(service_account_path)
            except Exception as e:
                logger.error(f"Failed to load credentials from file {service_account_path}: {e}")
                return None
        else:
            logger.error(f"Service account file does not exist: {service_account_path}")
            return None
    
    # Method 4: Default local file (Development)
    elif os.path.exists('firebase-service-account.json'):
        logger.info("Using default local firebase-service-account.json file")
        try:
            return credentials.Certificate('firebase-service-account.json')
        except Exception as e:
            logger.error(f"Failed to load credentials from firebase-service-account.json: {e}")
            return None
    
    # Method 5: Application default credentials (Cloud deployment)
    else:
        logger.info("Attempting to use application default credentials")
        try:
            creds = credentials.ApplicationDefault()
            logger.info("Successfully loaded application default credentials")
            return creds
        except Exception as e:
            logger.error(f"No Firebase credentials found: {e}")
            print(f"No Firebase credentials found: {e}")
            return None

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    logger.info("Initializing Firebase Admin SDK...")
    
    if not FIREBASE_AVAILABLE:
        logger.error("Firebase not available - skipping initialization")
        print("Firebase not available - skipping initialization")
        return False
    
    if not firebase_admin._apps:
        logger.info("No existing Firebase apps found, creating new one")
        
        # Print environment variables for debugging
        print_environment_variables()
        
        cred = get_firebase_credentials()
        
        if cred is None:
            logger.error("No valid Firebase credentials found")
            raise Exception("No valid Firebase credentials found. Please set environment variables or add service account file.")
        
        try:
            project_id = os.getenv('FIREBASE_PROJECT_ID')
            logger.info(f"Initializing Firebase app with project ID: {project_id}")
            
            firebase_admin.initialize_app(cred, {
                'projectId': project_id
            })
            
            logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            raise
    else:
        logger.info("Firebase app already exists, skipping initialization")
    
    return True

def verify_firebase_token(id_token: str) -> Optional[Dict]:
    """
    Verify Firebase ID token and return user information
    """
    logger.info("Attempting to verify Firebase ID token...")
    
    if not FIREBASE_AVAILABLE:
        logger.error("Firebase not available - cannot verify token")
        print("Firebase not available - cannot verify token")
        return None
    
    if not id_token or not id_token.strip():
        logger.error("Empty or null ID token provided")
        return None
    
    # Mask the token for logging (show first/last few characters)
    masked_token = f"{id_token[:10]}...{id_token[-10:]}" if len(id_token) > 20 else "***"
    logger.info(f"Verifying token: {masked_token}")
    
    try:
        # Initialize Firebase if not already done
        logger.info("Ensuring Firebase is initialized...")
        if not initialize_firebase():
            logger.error("Failed to initialize Firebase")
            return None
        
        logger.info("Calling Firebase auth.verify_id_token()...")
        # Verify the token
        decoded_token = auth.verify_id_token(id_token)
        
        logger.info(f"Token verification successful for UID: {decoded_token.get('uid', 'UNKNOWN')}")
        logger.info(f"Email: {decoded_token.get('email', 'NO EMAIL')}")
        logger.info(f"Email verified: {decoded_token.get('email_verified', False)}")
        logger.info(f"Provider: {decoded_token.get('firebase', {}).get('sign_in_provider', 'unknown')}")
        
        # Extract user information
        user_info = {
            'firebase_uid': decoded_token['uid'],
            'email': decoded_token.get('email', ''),
            'email_verified': decoded_token.get('email_verified', False),
            'name': decoded_token.get('name', ''),
            'picture': decoded_token.get('picture', ''),
            'provider': decoded_token.get('firebase', {}).get('sign_in_provider', 'unknown')
        }
        
        logger.info(f"Returning user info for: {user_info['email']}")
        return user_info
    
    except FileNotFoundError as e:
        logger.error(f"Firebase service account key not found: {e}")
        print(f"Firebase service account key not found: {e}")
        print("Please add firebase-service-account.json to the backend directory")
        print("See FIREBASE_SECURITY_NOTICE.md for instructions")
        return None
    except Exception as e:
        logger.error(f"Firebase token verification error: {e}")
        logger.error(f"Token verification failed for token: {masked_token}")
        print(f"Firebase token verification error: {e}")
        return None

def get_firebase_user(uid: str) -> Optional[Dict]:
    """
    Get user information from Firebase by UID
    """
    logger.info(f"Getting Firebase user by UID: {uid}")
    
    if not FIREBASE_AVAILABLE:
        logger.error("Firebase not available - cannot get user")
        print("Firebase not available - cannot get user")
        return None
    
    if not uid or not uid.strip():
        logger.error("Empty or null UID provided")
        return None
    
    try:
        logger.info("Ensuring Firebase is initialized...")
        if not initialize_firebase():
            logger.error("Failed to initialize Firebase")
            return None
        
        logger.info(f"Calling Firebase auth.get_user() for UID: {uid}")
        user_record = auth.get_user(uid)
        
        logger.info(f"Successfully retrieved user record for UID: {uid}")
        logger.info(f"User email: {user_record.email}")
        logger.info(f"User display name: {user_record.display_name}")
        logger.info(f"Email verified: {user_record.email_verified}")
        
        user_info = {
            'firebase_uid': user_record.uid,
            'email': user_record.email or '',
            'email_verified': user_record.email_verified,
            'display_name': user_record.display_name or '',
            'photo_url': user_record.photo_url or '',
            'provider_data': [
                {
                    'provider_id': provider.provider_id,
                    'uid': provider.uid,
                    'display_name': provider.display_name,
                    'email': provider.email,
                    'photo_url': provider.photo_url
                } for provider in user_record.provider_data
            ]
        }
        
        logger.info(f"Returning user info for UID: {uid}")
        return user_info
    
    except Exception as e:
        logger.error(f"Firebase user lookup error for UID {uid}: {e}")
        print(f"Firebase user lookup error: {e}")
        return None