import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL")

_access_token = None
_token_expiry = 0
TOKEN_BUFFER = 600


def get_token():
    global _access_token, _token_expiry

    if _access_token:
        if (time.time() < (_token_expiry - TOKEN_BUFFER)):
            return _access_token

    url = "https://fs.prisme-365.dk/adfs/oauth2/token"

    payload = {
        "tenant_id": os.getenv("TENANT_ID"),
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "resource": os.getenv("RESOURCE"),
        "grant_type": os.getenv("GRANT_TYPE")
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=payload, headers=headers)
    data = response.json()

    _access_token = data.get("access_token")
    expires_in = data.get("expires_in", 3600)
    _token_expiry = time.time() + expires_in

    return _access_token


def get(endpoint: str):
    token = get_token()

    url = f"{BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)


    print("\n--- GET REQUEST ---")
    print("Fuld URL:")
    print(url)

    print("Status:", response.status_code)

    return response.json()


def patch(endpoint: str, body: dict):
    token = get_token()

    url = f"{BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.patch(url, json=body, headers=headers)

    print("\n--- PATCH ---")
    print("URL:", url)
    print("Status:", response.status_code)

    return response.status_code < 300