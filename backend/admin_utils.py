import json
import os
from typing import List, Optional

def load_admin_whitelist() -> List[str]:
    """Load admin emails from whitelist file"""
    whitelist_path = os.path.join(os.path.dirname(__file__), 'admin_whitelist.json')
    
    try:
        if os.path.exists(whitelist_path):
            with open(whitelist_path, 'r') as f:
                data = json.load(f)
                return data.get('admin_emails', [])
        else:
            # Create default whitelist if it doesn't exist
            default_whitelist = {
                "admin_emails": [
                    "vikram7june@gmail.com"
                ]
            }
            with open(whitelist_path, 'w') as f:
                json.dump(default_whitelist, f, indent=2)
            return default_whitelist['admin_emails']
    except Exception as e:
        print(f"Error loading admin whitelist: {e}")
        return []

def is_admin_user(email: Optional[str]) -> bool:
    """Check if a user email is in the admin whitelist"""
    if not email:
        return False
    
    admin_emails = load_admin_whitelist()
    return email.lower() in [admin_email.lower() for admin_email in admin_emails]

def add_admin_user(email: str) -> bool:
    """Add a user email to the admin whitelist"""
    whitelist_path = os.path.join(os.path.dirname(__file__), 'admin_whitelist.json')
    
    try:
        admin_emails = load_admin_whitelist()
        
        if email.lower() not in [admin_email.lower() for admin_email in admin_emails]:
            admin_emails.append(email)
            
            whitelist_data = {"admin_emails": admin_emails}
            with open(whitelist_path, 'w') as f:
                json.dump(whitelist_data, f, indent=2)
            
            return True
        return False  # User already exists
    except Exception as e:
        print(f"Error adding admin user: {e}")
        return False

def remove_admin_user(email: str) -> bool:
    """Remove a user email from the admin whitelist"""
    whitelist_path = os.path.join(os.path.dirname(__file__), 'admin_whitelist.json')
    
    try:
        admin_emails = load_admin_whitelist()
        original_count = len(admin_emails)
        
        admin_emails = [admin_email for admin_email in admin_emails 
                       if admin_email.lower() != email.lower()]
        
        if len(admin_emails) < original_count:
            whitelist_data = {"admin_emails": admin_emails}
            with open(whitelist_path, 'w') as f:
                json.dump(whitelist_data, f, indent=2)
            
            return True
        return False  # User was not in the list
    except Exception as e:
        print(f"Error removing admin user: {e}")
        return False

def get_admin_users() -> List[str]:
    """Get all admin users from whitelist"""
    return load_admin_whitelist()