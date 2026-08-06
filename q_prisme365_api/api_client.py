import requests
import time

from automation_server_client import AutomationServer, Credential

print("Starter API-klient...")

# -------------------------------------------------
# Forbind til Automation Server
# -------------------------------------------------
print("Initialiserer Automation Server fra environment")
AutomationServer.from_environment()  # klassemetode (funktion på klasse)

# -------------------------------------------------
# Hent credential
# -------------------------------------------------
print("Henter credential: API_PRISME365_1")
credential = Credential.get_credential("API_PRISME365_1")  # objekt (konkret instans)

print("Credential hentet OK")
print("Credential data (uden secret):")
print(credential.data)

cfg = credential.data  # dict (nøgle/værdi-data)

# -------------------------------------------------
# Konfiguration KUN fra credentials
# -------------------------------------------------
TENANT_ID = cfg["tenant_id"]
CLIENT_ID = cfg["client_id"]
CLIENT_SECRET = credential.password
RESOURCE = cfg["resource"]
GRANT_TYPE = cfg["grant_type"]
TOKEN_URL = cfg["token_url"]
BASE_URL = cfg["base_url"]

print("Konfiguration indlæst fra credential")
print("TOKEN_URL:", TOKEN_URL)
print("BASE_URL:", BASE_URL)

# -------------------------------------------------
# Token cache
# -------------------------------------------------
_access_token = None
_token_expiry = 0
TOKEN_BUFFER = 600  # sekunder


def get_token():
    """Henter og cacher access token."""
    global _access_token, _token_expiry  # global (delt variabel)

    print("\n[get_token] Kaldes...")

    # Brug cached token hvis stadig gyldig
    if _access_token and time.time() < (_token_expiry - TOKEN_BUFFER):
        print("[get_token] Bruger cached token")
        return _access_token

    print("[get_token] Ingen gyldig cache – henter nyt token")

    payload = {
        "tenant_id": TENANT_ID,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "resource": RESOURCE,
        "grant_type": GRANT_TYPE
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    print("[get_token] POST til token endpoint")
    print("[get_token] URL:", TOKEN_URL)
    print("[get_token] Payload keys:", list(payload.keys()))

    response = requests.post(
        TOKEN_URL,
        data=payload,
        headers=headers,
        timeout=30
    )

    print("[get_token] Status:", response.status_code)

    if response.status_code >= 300:
        print("[get_token] FEJL – token kunne ikke hentes")
        raise RuntimeError(
            f"Token-fejl {response.status_code}: {response.text}"
        )

    data = response.json()

    _access_token = data["access_token"]
    expires_in = data.get("expires_in", 3600)
    _token_expiry = time.time() + int(expires_in)

    print("[get_token] Token modtaget OK")
    print("[get_token] Expires in (sek):", expires_in)

    return _access_token


def get(endpoint: str):
    """GET request til API (returnerer rækker, ikke metadata)."""

    print("\n[get] Kaldes med endpoint:", endpoint)

    token = get_token()

    url = f"{BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers, timeout=30)

    print("\n--- GET REQUEST ---")
    print("Fuld URL:")
    print(url)
    print("Status:", response.status_code)

    if response.status_code >= 300:
        raise RuntimeError(
            f"GET-fejl {response.status_code}: {response.text}"
        )

    data = response.json()  # dict (key/value data)

    # -------------------------------------------------
    # Udpak OData-respons (vigtigt)
    # -------------------------------------------------
    if isinstance(data, dict) and "value" in data:
        value = data["value"]

        if isinstance(value, list):
            print("[get] OData 'value' fundet – returnerer rækker")
            return value  # liste (ordnet samling)

    # Fallback: returnér som det er
    print("[get] Ingen 'value' – returnerer rå data")
    return data



def patch(endpoint: str, body: dict):
    """PATCH request til API."""
    print("\n[patch] Kaldes med endpoint:", endpoint)

    token = get_token()

    url = f"{BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.patch(
        url,
        json=body,
        headers=headers,
        timeout=30
    )

    print("\n--- PATCH ---")
    print("URL:", url)
    print("Status:", response.status_code)

    if response.status_code >= 300:
        raise RuntimeError(
            f"PATCH-fejl {response.status_code}: {response.text}"
        )

    return True