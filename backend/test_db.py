#!/usr/bin/env python3

import sys
sys.path.append('.')

from database import engine, Base
from models import User, Transaction

# Create all tables
print("Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
    
    # Test creating a user
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Try to create a test user
    test_user = User(username="testuser")
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    print(f"User created successfully: {test_user.id}, {test_user.username}")
    
    db.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()