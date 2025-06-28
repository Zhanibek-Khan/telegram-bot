
import json
import tempfile
from replit import object_storage
from google.auth import service_account

def get_google_credentials():
    """Retrieve Google service account credentials from object storage"""
    
    bucket = object_storage.get_default_bucket()
    
    try:
        # Check if credentials exist in object storage
        if not bucket.exists("google_service_account.json"):
            raise FileNotFoundError("Google service account file not found in object storage")
        
        # Download credentials to a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
            bucket.download_to_filename("google_service_account.json", temp_file.name)
            
            # Load credentials
            credentials = service_account.Credentials.from_service_account_file(temp_file.name)
            
            # Clean up temp file
            import os
            os.unlink(temp_file.name)
            
            return credentials
            
    except Exception as e:
        print(f"Error retrieving Google credentials: {e}")
        return None

def get_credentials_as_dict():
    """Get credentials as dictionary for direct API usage"""
    
    bucket = object_storage.get_default_bucket()
    
    try:
        if not bucket.exists("google_service_account.json"):
            raise FileNotFoundError("Google service account file not found in object storage")
        
        # Download as text and parse JSON
        credentials_text = bucket.download_as_text("google_service_account.json")
        return json.loads(credentials_text)
        
    except Exception as e:
        print(f"Error retrieving credentials as dict: {e}")
        return None
