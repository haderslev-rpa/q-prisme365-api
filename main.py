import json
from automation_server_client import Client

# ---------------------------------------------------------------------------
# INITIALISERING AF AUTOMATION SERVER CLIENT
# ---------------------------------------------------------------------------
automation_client = Client()

# ---------------------------------------------------------------------------
# HENT API CONFIG CREDENTIAL
# ---------------------------------------------------------------------------
CREDENTIAL_NAME = "API_PRISME365_CONFIG_1"

credential = automation_client.get_credential(CREDENTIAL_NAME)

# ---------------------------------------------------------------------------
# PARSE JSON-DATA
# ---------------------------------------------------------------------------
config = json.loads(credential["data"])

# ---------------------------------------------------------------------------
# VARIABLER (klar til brug i token-request)
# ---------------------------------------------------------------------------

# Fra JSON
resource = config["resource"]
client_id = config["client_id"]
tenant_id = config["tenant_id"]          # forventet: "adfs"
token_url = config["token_url"]
grant_type = config["grant_type"]
token_type = config.get("token_type")    # optional, men god at have

# Fra PASSWORD
client_secret = credential["password"]

# (Optional) Username hvis du vil bruge/logge den
username = credential.get("username")

# ---------------------------------------------------------------------------
# DEBUG / TEST (fjern i PROD)
# ---------------------------------------------------------------------------
print("Credential loaded successfully")
print(f"client_id: {client_id}")
print(f"tenant_id: {tenant_id}")
print(f"token_url: {token_url}")
print(f"grant_type: {grant_type}")
print(f"resource: {resource}")