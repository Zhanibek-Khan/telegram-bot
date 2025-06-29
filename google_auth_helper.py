import os
import json
from google.oauth2.service_account import Credentials

def get_credentials(scopes):
    # Получаем JSON из переменной окружения
    json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not json_str:
        raise Exception("Сервисный аккаунт не найден в переменных окружения GOOGLE_CREDENTIALS_JSON!")

    # Преобразуем JSON-строку в словарь
    info = json.loads(json_str)

    # Создаем credentials с указанными скоупами
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return creds
