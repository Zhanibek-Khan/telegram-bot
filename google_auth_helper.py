import os
import json
from google.oauth2 import service_account

def get_google_credentials():
    credentials_path = "/etc/secrets/credentials.json"
    with open(credentials_path) as f:
        service_account_info = json.load(f)
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return credentials
