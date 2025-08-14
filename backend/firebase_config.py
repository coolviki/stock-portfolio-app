import os
import json
import base64
from typing import Dict, Optional

# Optional Firebase imports - handle gracefully if not available
try:
    import firebase_admin
    from firebase_admin import credentials, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    print("Warning: firebase_admin not available. Firebase authentication will be disabled.")
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    credentials = None
    auth = None

def get_firebase_credentials():
    """Get Firebase credentials from environment variables or file"""
    if not FIREBASE_AVAILABLE:
        return None
    # Method 1: Individual environment variables (Production recommended)
    if os.getenv('FIREBASE_PRIVATE_KEY'):
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
        return credentials.Certificate(cred_dict)
    
    # Method 2: Base64 encoded JSON (Alternative)
    elif os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64'):
        try:
            service_account_json = base64.b64decode(os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64'))
            cred_dict = json.loads(service_account_json)
            return credentials.Certificate(cred_dict)
        except Exception as e:
            print(f"Error decoding base64 service account: {e}")
            return None
    
    # Method 3: File path (Development fallback)
    elif os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH'):
        service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
        if os.path.exists(service_account_path):
            return credentials.Certificate(service_account_path)
    
    # Method 4: Default local file (Development)
    elif os.path.exists('firebase-service-account.json'):
        return credentials.Certificate('firebase-service-account.json')
    
    # Method 5: Application default credentials (Cloud deployment)
    else:
        try:
            return credentials.ApplicationDefault()
        except Exception as e:
            print(f"No Firebase credentials found: {e}")
            return None

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    if not FIREBASE_AVAILABLE:
        print("Firebase not available - skipping initialization")
        return False
    
    if not firebase_admin._apps:
        cred = get_firebase_credentials()
        
        if cred is None:
            raise Exception("No valid Firebase credentials found. Please set environment variables or add service account file.")
        
        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('FIREBASE_PROJECT_ID')
        })
    
    return True

def verify_firebase_token(id_token: str) -> Optional[Dict]:
    """
    Verify Firebase ID token and return user information
    """
    if not FIREBASE_AVAILABLE:
        print("Firebase not available - cannot verify token")
        return None
    
    try:
        # Initialize Firebase if not already done
        initialize_firebase()
        
        # Verify the token
        decoded_token = auth.verify_id_token(id_token)
        
        # Extract user information
        return {
            'firebase_uid': decoded_token['uid'],
            'email': decoded_token.get('email', ''),
            'email_verified': decoded_token.get('email_verified', False),
            'name': decoded_token.get('name', ''),
            'picture': decoded_token.get('picture', ''),
            'provider': decoded_token.get('firebase', {}).get('sign_in_provider', 'unknown')
        }
    
    except FileNotFoundError as e:
        print(f"Firebase service account key not found: {e}")
        print("Please add firebase-service-account.json to the backend directory")
        print("See FIREBASE_SECURITY_NOTICE.md for instructions")
        return None
    except Exception as e:
        print(f"Firebase token verification error: {e}")
        return None

def get_firebase_user(uid: str) -> Optional[Dict]:
    """
    Get user information from Firebase by UID
    """
    if not FIREBASE_AVAILABLE:
        print("Firebase not available - cannot get user")
        return None
    
    try:
        initialize_firebase()
        user_record = auth.get_user(uid)
        
        return {
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
    
    except Exception as e:
        print(f"Firebase user lookup error: {e}")
        return None