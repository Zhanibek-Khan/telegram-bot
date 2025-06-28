
import os
from replit import object_storage

def upload_service_account_file():
    """Upload the Google service account JSON file to object storage"""
    
    # Get the default bucket
    bucket = object_storage.get_default_bucket()
    
    # Path to the service account file
    service_account_file = "attached_assets/bustling-kayak-464310-m5-d27bcc4714fb_1751109477162.json"
    
    try:
        # Upload the file to object storage
        bucket.upload_from_filename(
            dest_object_name="google_service_account.json",
            src_filename=service_account_file
        )
        print("✅ Service account file uploaded successfully to object storage!")
        print("Object name: google_service_account.json")
        
        # Verify upload
        if bucket.exists("google_service_account.json"):
            print("✅ Upload verified - file exists in object storage")
        else:
            print("❌ Upload verification failed")
            
    except Exception as e:
        print(f"❌ Error uploading file: {e}")

if __name__ == "__main__":
    upload_service_account_file()
