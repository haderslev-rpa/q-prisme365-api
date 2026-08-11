"""Fælles HTTP-funktioner til Prisme 365 API."""

import logging
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests
from automation_server_client import AutomationServer
from automation_server_client import Credential

from q_prisme365_api.exceptions import PrismeApiError
from q_prisme365_api.exceptions import PrismeAuthenticationError
from q_prisme365_api.exceptions import PrismeNotFoundError
from q_prisme365_api.exceptions import PrismePermissionError
from q_prisme365_api.exceptions import PrismeRateLimitError
from q_prisme365_api.exceptions import PrismeResponseError
from q_prisme365_api.exceptions import PrismeServerError


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# AUTOMATION SERVER
# ------------------------------------------------------------

logger.info(
    "Initialiserer Automation Server"
)

AutomationServer.from_environment()


# ------------------------------------------------------------
# CREDENTIAL
# ------------------------------------------------------------

CREDENTIAL_NAME = "API_PRISME365_1"

logger.info(
    "Henter Prisme-credential: %s",
    CREDENTIAL_NAME,
)

credential = Credential.get_credential(
    CREDENTIAL_NAME
)

cfg = credential.data


# ------------------------------------------------------------
# KONFIGURATION FRA CREDENTIAL
# ------------------------------------------------------------

TENANT_ID = cfg["tenant_id"]
CLIENT_ID = cfg["client_id"]
CLIENT_SECRET = credential.password
RESOURCE = cfg["resource"]
GRANT_TYPE = cfg["grant_type"]
TOKEN_URL = cfg["token_url"]
BASE_URL = cfg["base_url"]

logger.info(
    "Prisme-konfiguration er indlæst"
)


# ------------------------------------------------------------
# TOKEN-CACHE
# ------------------------------------------------------------

_access_token = None
_token_expiry = 0

TOKEN_BUFFER = 600


# ------------------------------------------------------------
# HTTP-KONFIGURATION
# ------------------------------------------------------------

REQUEST_TIMEOUT = 30

GET_MAX_RETRIES = 3
GET_RETRY_BASE_DELAY = 1.0

RETRY_STATUS_CODES = {
    429,
    502,
    503,
    504,
}

_session = requests.Session()


# ------------------------------------------------------------
# TOKEN
# ------------------------------------------------------------

def get_token():
    """
    Hent og cache access token.

    Tokenhåndteringen svarer til den tidligere
    fungerende løsning.
    """

    global _access_token
    global _token_expiry

    logger.debug(
        "get_token blev kaldt"
    )

    token_is_valid = (
        _access_token
        and time.time()
        < (_token_expiry - TOKEN_BUFFER)
    )

    if token_is_valid:
        logger.debug(
            "Bruger cached access token"
        )

        return _access_token

    logger.info(
        "Henter nyt Prisme access token"
    )

    payload = {
        "tenant_id": TENANT_ID,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "resource": RESOURCE,
        "grant_type": GRANT_TYPE,
    }

    headers = {
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
        "Accept": "application/json",
    }

    try:
        response = _session.post(
            TOKEN_URL,
            data=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as error:
        raise PrismeAuthenticationError(
            "Timeout ved hentning af token.",
            method="POST",
            endpoint=TOKEN_URL,
        ) from error
    except requests.RequestException as error:
        raise PrismeAuthenticationError(
            "Teknisk fejl ved hentning af token.",
            method="POST",
            endpoint=TOKEN_URL,
            response_text=str(error),
        ) from error

    if response.status_code >= 300:
        raise PrismeAuthenticationError(
            "Token kunne ikke hentes.",
            method="POST",
            endpoint=TOKEN_URL,
            status_code=response.status_code,
            response_text=response.text,
        )

    try:
        data = response.json()
    except ValueError as error:
        raise PrismeAuthenticationError(
            "Token-svaret var ikke gyldig JSON.",
            method="POST",
            endpoint=TOKEN_URL,
            status_code=response.status_code,
            response_text=response.text,
        ) from error

    if "access_token" not in data:
        raise PrismeAuthenticationError(
            "Token-svaret mangler access_token.",
            method="POST",
            endpoint=TOKEN_URL,
            status_code=response.status_code,
            response_text=response.text,
        )

    _access_token = data["access_token"]

    expires_in = data.get(
        "expires_in",
        3600,
    )

    try:
        expires_in_seconds = int(
            expires_in
        )
    except (TypeError, ValueError) as error:
        raise PrismeAuthenticationError(
            "Token-svaret har ugyldig expires_in.",
            method="POST",
            endpoint=TOKEN_URL,
            status_code=response.status_code,
            response_text=response.text,
        ) from error

    _token_expiry = (
        time.time()
        + expires_in_seconds
    )

    logger.info(
        "Nyt Prisme access token modtaget"
    )

    return _access_token


# ------------------------------------------------------------
# GET
# ------------------------------------------------------------

def get(
    endpoint: str,
):
    """
    Udfør GET-kald til Prisme.

    OData-svar med value returneres som en liste.
    Alle OData-sider hentes automatisk.
    Andre JSON-svar returneres uændret.
    """

    _validate_endpoint(
        endpoint
    )

    logger.info(
        "GET %s",
        endpoint,
    )

    url = _build_url(
        endpoint
    )

    data = _get_json_with_retry(
        url
    )

    is_odata_list = (
        isinstance(data, dict)
        and isinstance(
            data.get("value"),
            list,
        )
    )

    if not is_odata_list:
        logger.info(
            "GET returnerer rå JSON"
        )

        return data

    rows = list(
        data["value"]
    )

    next_link = _get_next_link(
        data
    )

    while next_link:
        logger.info(
            "Henter næste OData-side"
        )

        next_url = _build_url(
            next_link
        )

        next_data = _get_json_with_retry(
            next_url
        )

        if not isinstance(
            next_data,
            dict,
        ):
            raise PrismeResponseError(
                "Næste OData-side var ikke "
                "et JSON-objekt.",
                method="GET",
                endpoint=next_url,
            )

        next_rows = next_data.get(
            "value"
        )

        if not isinstance(
            next_rows,
            list,
        ):
            raise PrismeResponseError(
                "Næste OData-side mangler "
                "listen value.",
                method="GET",
                endpoint=next_url,
            )

        rows.extend(
            next_rows
        )

        next_link = _get_next_link(
            next_data
        )

    logger.info(
        "GET returnerer %s rækker",
        len(rows),
    )

    return rows


# ------------------------------------------------------------
# PATCH
# ------------------------------------------------------------

def patch(
    endpoint: str,
    body: dict,
):
    """
    Udfør PATCH-kald til Prisme.

    Returnerer True ved succes.
    """

    _validate_endpoint(
        endpoint
    )

    _validate_body(
        body
    )

    logger.info(
        "PATCH %s",
        endpoint,
    )

    url = _build_url(
        endpoint
    )

    response = _send_request(
        method="PATCH",
        url=url,
        body=body,
    )

    _raise_for_status(
        response=response,
        method="PATCH",
        endpoint=url,
    )

    logger.info(
        "PATCH gennemført med status %s",
        response.status_code,
    )

    return True


# ------------------------------------------------------------
# POST
# ------------------------------------------------------------

def post(
    endpoint: str,
    body: dict,
):
    """
    Udfør POST-kald til Prisme.

    JSON-svar returneres som Python-data.
    Et tomt succesrespons returnerer True.
    """

    _validate_endpoint(
        endpoint
    )

    _validate_body(
        body
    )

    logger.info(
        "POST %s",
        endpoint,
    )

    url = _build_url(
        endpoint
    )

    response = _send_request(
        method="POST",
        url=url,
        body=body,
    )

    _raise_for_status(
        response=response,
        method="POST",
        endpoint=url,
    )

    logger.info(
        "POST gennemført med status %s",
        response.status_code,
    )

    return _parse_optional_json_response(
        response=response,
        method="POST",
        endpoint=url,
    )


# ------------------------------------------------------------
# DELETE
# ------------------------------------------------------------

def delete(
    endpoint: str,
):
    """
    Udfør DELETE-kald til Prisme.

    Returnerer True ved succes.
    HTTP 204 betragtes som succes.
    """

    _validate_endpoint(
        endpoint
    )

    logger.info(
        "DELETE %s",
        endpoint,
    )

    url = _build_url(
        endpoint
    )

    response = _send_request(
        method="DELETE",
        url=url,
        body=None,
    )

    _raise_for_status(
        response=response,
        method="DELETE",
        endpoint=url,
    )

    logger.info(
        "DELETE gennemført med status %s",
        response.status_code,
    )

    return True


# ------------------------------------------------------------
# GET MED GENFORSØG
# ------------------------------------------------------------

def _get_json_with_retry(
    url: str,
):
    """
    Udfør GET-kald med genforsøg.

    Der genforsøges ved:
    HTTP 429
    HTTP 502
    HTTP 503
    HTTP 504
    Timeout
    """

    attempt = 0

    while True:
        token = get_token()

        headers = {
            "Authorization": (
                f"Bearer {token}"
            ),
            "Accept": "application/json",
        }

        try:
            response = _session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.Timeout as error:
            retries_are_used = (
                attempt >= GET_MAX_RETRIES
            )

            if retries_are_used:
                raise PrismeApiError(
                    "GET-kaldet fik timeout.",
                    method="GET",
                    endpoint=url,
                ) from error

            delay = _calculate_retry_delay(
                attempt=attempt,
                response=None,
            )

            logger.warning(
                "GET-timeout. "
                "Genforsøger om %s sekunder",
                delay,
            )

            time.sleep(
                delay
            )

            attempt += 1

            continue
        except requests.RequestException as error:
            raise PrismeApiError(
                "Teknisk fejl ved GET-kald.",
                method="GET",
                endpoint=url,
                response_text=str(error),
            ) from error

        should_retry = (
            response.status_code
            in RETRY_STATUS_CODES
            and attempt < GET_MAX_RETRIES
        )

        if should_retry:
            delay = _calculate_retry_delay(
                attempt=attempt,
                response=response,
            )

            logger.warning(
                "GET returnerede HTTP %s. "
                "Genforsøger om %s sekunder",
                response.status_code,
                delay,
            )

            time.sleep(
                delay
            )

            attempt += 1

            continue

        _raise_for_status(
            response=response,
            method="GET",
            endpoint=url,
        )

        if not response.content:
            return None

        if not response.text.strip():
            return None

        try:
            return response.json()
        except ValueError as error:
            raise PrismeResponseError(
                "GET-svaret var ikke gyldig JSON.",
                method="GET",
                endpoint=url,
                status_code=response.status_code,
                response_text=response.text,
            ) from error


# ------------------------------------------------------------
# FÆLLES SKRIVENDE KALD
# ------------------------------------------------------------

def _send_request(
    method: str,
    url: str,
    body: dict | None = None,
):
    """
    Send PATCH, POST eller DELETE.

    Skrivende kald genforsøges ikke automatisk.
    """

    token = get_token()

    headers = {
        "Authorization": (
            f"Bearer {token}"
        ),
        "Accept": "application/json",
    }

    request_arguments = {
        "method": method,
        "url": url,
        "headers": headers,
        "timeout": REQUEST_TIMEOUT,
    }

    if body is not None:
        headers["Content-Type"] = (
            "application/json"
        )

        request_arguments["json"] = body

    try:
        response = _session.request(
            method=request_arguments["method"],
            url=request_arguments["url"],
            headers=request_arguments["headers"],
            timeout=request_arguments["timeout"],
            json=request_arguments.get("json"),
        )
    except requests.Timeout as error:
        raise PrismeApiError(
            f"{method}-kaldet fik timeout.",
            method=method,
            endpoint=url,
        ) from error
    except requests.RequestException as error:
        raise PrismeApiError(
            f"Teknisk fejl ved {method}-kald.",
            method=method,
            endpoint=url,
            response_text=str(error),
        ) from error

    return response


# ------------------------------------------------------------
# URL
# ------------------------------------------------------------

def _build_url(
    endpoint: str,
) -> str:
    """
    Byg en fuld URL.

    Et fuldt OData-nextLink bevares uændret.
    """

    if endpoint.startswith(
        (
            "https://",
            "http://",
        )
    ):
        return endpoint

    normalized_base_url = (
        BASE_URL.rstrip("/") + "/"
    )

    normalized_endpoint = (
        endpoint.lstrip("/")
    )

    return urljoin(
        normalized_base_url,
        normalized_endpoint,
    )


# ------------------------------------------------------------
# ODATA-SIDEINDDELING
# ------------------------------------------------------------

def _get_next_link(
    data: dict,
):
    """Find linket til næste OData-side."""

    next_link = data.get(
        "@odata.nextLink"
    )

    if not next_link:
        next_link = data.get(
            "odata.nextLink"
        )

    if not next_link:
        return None

    return str(
        next_link
    )


# ------------------------------------------------------------
# RETRY-AFSTAND
# ------------------------------------------------------------

def _calculate_retry_delay(
    attempt: int,
    response,
) -> float:
    """
    Beregn ventetiden før genforsøg.

    Retry-After bruges først.
    Ellers bruges 1, 2 og 4 sekunder.
    """

    if response is not None:
        retry_after = response.headers.get(
            "Retry-After"
        )

        parsed_retry_after = (
            _parse_retry_after(
                retry_after
            )
        )

        if parsed_retry_after is not None:
            return parsed_retry_after

    exponential_factor = pow(
        2,
        attempt,
    )

    return (
        GET_RETRY_BASE_DELAY
        * exponential_factor
    )


def _parse_retry_after(
    retry_after: str | None,
) -> float | None:
    """
    Fortolk Retry-After.

    Værdien kan være antal sekunder
    eller en HTTP-dato.
    """

    if not retry_after:
        return None

    try:
        seconds = float(
            retry_after
        )

        if seconds < 0:
            return 0.0

        return seconds
    except ValueError:
        pass

    try:
        retry_datetime = (
            parsedate_to_datetime(
                retry_after
            )
        )
    except (TypeError, ValueError):
        return None

    delay = (
        retry_datetime.timestamp()
        - time.time()
    )

    if delay < 0:
        return 0.0

    return delay


# ------------------------------------------------------------
# VALGFRIT JSON-SVAR
# ------------------------------------------------------------

def _parse_optional_json_response(
    response,
    method: str,
    endpoint: str,
):
    """
    Fortolk et valgfrit JSON-svar.

    Tomt svar returnerer True.
    OData value returneres som liste.
    Anden JSON returneres uændret.
    Tekst returneres som tekst.
    """

    if not response.content:
        return True

    if not response.text.strip():
        return True

    try:
        data = response.json()
    except ValueError:
        logger.debug(
            "%s returnerede tekst "
            "i stedet for JSON",
            method,
        )

        return response.text

    is_odata_list = (
        isinstance(data, dict)
        and isinstance(
            data.get("value"),
            list,
        )
    )

    if is_odata_list:
        return data["value"]

    return data


# ------------------------------------------------------------
# FEJLSTATUS
# ------------------------------------------------------------

def _raise_for_status(
    response,
    method: str,
    endpoint: str,
) -> None:
    """Omsæt HTTP-status til tydelige fejl."""

    status_code = response.status_code
    response_text = response.text

    if status_code < 300:
        return

    if status_code == 401:
        raise PrismeAuthenticationError(
            "Prisme afviste godkendelsen.",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_text=response_text,
        )

    if status_code == 403:
        raise PrismePermissionError(
            "Der mangler rettigheder i Prisme.",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_text=response_text,
        )

    if status_code == 404:
        raise PrismeNotFoundError(
            "Prisme-posten blev ikke fundet.",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_text=response_text,
        )

    if status_code == 429:
        raise PrismeRateLimitError(
            "Prisme begrænsede antal kald.",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_text=response_text,
        )

    if status_code >= 500:
        raise PrismeServerError(
            "Prisme returnerede en serverfejl.",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_text=response_text,
        )

    raise PrismeApiError(
        "Prisme returnerede en HTTP-fejl.",
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        response_text=response_text,
    )


# ------------------------------------------------------------
# INPUTKONTROL
# ------------------------------------------------------------

def _validate_endpoint(
    endpoint,
) -> None:
    """Kontrollér endpointet."""

    if not isinstance(
        endpoint,
        str,
    ):
        raise TypeError(
            "endpoint skal være tekst."
        )

    if not endpoint.strip():
        raise ValueError(
            "endpoint skal udfyldes."
        )


def _validate_body(
    body,
) -> None:
    """Kontrollér JSON-indholdet."""

    if not isinstance(
        body,
        dict,
    ):
        raise TypeError(
            "body skal være en dictionary."
        )