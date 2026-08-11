"""Fælles HTTP-funktioner til Prisme 365 API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin

import requests
from automation_server_client import AutomationServer
from automation_server_client import Credential

from q_prisme365_api.exceptions import PrismeApiError
from q_prisme365_api.exceptions import (
    PrismeAuthenticationError,
)
from q_prisme365_api.exceptions import (
    PrismeNotFoundError,
)
from q_prisme365_api.exceptions import (
    PrismePermissionError,
)
from q_prisme365_api.exceptions import (
    PrismeRateLimitError,
)
from q_prisme365_api.exceptions import (
    PrismeResponseError,
)
from q_prisme365_api.exceptions import (
    PrismeServerError,
)


__all__ = [
    "initialiser_prisme",
    "get_aktivt_credential_navn",
    "get_token",
    "get",
    "patch",
    "post",
    "delete",
]


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# KONFIGURATIONSMODEL
# ------------------------------------------------------------

@dataclass(frozen=True)
class PrismeConfiguration:
    """Aktiv konfiguration til Prisme."""

    credential_name: str
    tenant_id: str
    client_id: str
    client_secret: str
    resource: str
    grant_type: str
    token_url: str
    base_url: str


# ------------------------------------------------------------
# AKTIV TILSTAND
# ------------------------------------------------------------

_config: PrismeConfiguration | None = None

_access_token: str | None = None
_token_expiry = 0.0

_automation_server_initialized = False

_session = requests.Session()


# ------------------------------------------------------------
# TOKENKONFIGURATION
# ------------------------------------------------------------

# Tokenet fornyes, når der er mindre end
# 10 minutter tilbage af tokenets levetid.
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


# ------------------------------------------------------------
# INITIALISERING
# ------------------------------------------------------------

def initialiser_prisme(
    credential_name: str,
) -> None:
    """
    Initialisér Prisme med valgt credential.

    Funktionen skal kaldes én gang ved
    processtart.

    Credential-navnet bruges til at hente
    loginoplysninger fra Automation Server.

    Der findes ingen standardcredential.
    Et tomt credential-navn giver en fejl.

    Funktionen henter et token med det samme,
    så loginfejl opdages ved processtart.

    Args:
        credential_name:
            Navnet på credential-posten i
            Automation Server.
    """

    global _config
    global _access_token
    global _token_expiry
    global _session

    clean_credential_name = (
        _validate_credential_name(
            credential_name
        )
    )

    _initialize_automation_server()

    logger.info(
        "Initialiserer Prisme API med "
        "credential: %s",
        clean_credential_name,
    )

    try:
        credential = Credential.get_credential(
            clean_credential_name
        )
    except Exception as error:
        raise PrismeAuthenticationError(
            "Credential kunne ikke hentes fra "
            "Automation Server. "
            f"Credential-navn: "
            f"{clean_credential_name!r}.",
            method="CREDENTIAL",
            endpoint=clean_credential_name,
            response_text=str(error),
        ) from error

    credential_data = getattr(
        credential,
        "data",
        None,
    )

    if not isinstance(
        credential_data,
        dict,
    ):
        raise PrismeAuthenticationError(
            "Credential-data skal være en "
            "dictionary.",
            method="CREDENTIAL",
            endpoint=clean_credential_name,
        )

    client_secret = getattr(
        credential,
        "password",
        None,
    )

    if client_secret is None:
        raise PrismeAuthenticationError(
            "Credential mangler password med "
            "Prisme client secret.",
            method="CREDENTIAL",
            endpoint=clean_credential_name,
        )

    clean_client_secret = str(
        client_secret
    ).strip()

    if not clean_client_secret:
        raise PrismeAuthenticationError(
            "Credential har et tomt password.",
            method="CREDENTIAL",
            endpoint=clean_credential_name,
        )

    config = PrismeConfiguration(
        credential_name=clean_credential_name,
        tenant_id=_require_config_text(
            credential_data,
            "tenant_id",
            clean_credential_name,
        ),
        client_id=_require_config_text(
            credential_data,
            "client_id",
            clean_credential_name,
        ),
        client_secret=clean_client_secret,
        resource=_require_config_text(
            credential_data,
            "resource",
            clean_credential_name,
        ),
        grant_type=_require_config_text(
            credential_data,
            "grant_type",
            clean_credential_name,
        ),
        token_url=_require_config_text(
            credential_data,
            "token_url",
            clean_credential_name,
        ),
        base_url=_require_config_text(
            credential_data,
            "base_url",
            clean_credential_name,
        ),
    )

    _validate_absolute_url(
        config.token_url,
        "token_url",
        clean_credential_name,
    )

    _validate_absolute_url(
        config.base_url,
        "base_url",
        clean_credential_name,
    )

    # Den nye konfiguration gemmes først,
    # når alle felter er valideret.
    _config = config

    # Et token fra en tidligere credential
    # må aldrig genbruges.
    _access_token = None
    _token_expiry = 0.0

    # En ny session sikrer, at forbindelser
    # fra en tidligere credential ikke bevares.
    try:
        _session.close()
    except Exception:
        logger.debug(
            "Den tidligere HTTP-session "
            "kunne ikke lukkes."
        )

    _session = requests.Session()

    # Token hentes med det samme.
    get_token()

    logger.info(
        "Prisme API er initialiseret med "
        "credential: %s",
        clean_credential_name,
    )


def get_aktivt_credential_navn() -> str:
    """
    Returnér navnet på aktiv credential.

    Funktionen afslører ikke loginoplysninger.
    """

    config = _require_initialised()

    return config.credential_name


def _initialize_automation_server() -> None:
    """Initialisér Automation Server én gang."""

    global _automation_server_initialized

    if _automation_server_initialized:
        return

    logger.info(
        "Initialiserer Automation Server"
    )

    try:
        AutomationServer.from_environment()
    except Exception as error:
        raise PrismeAuthenticationError(
            "Automation Server kunne ikke "
            "initialiseres fra miljøet.",
            method="AUTOMATION_SERVER",
            endpoint="from_environment",
            response_text=str(error),
        ) from error

    _automation_server_initialized = True


def _validate_credential_name(
    credential_name: Any,
) -> str:
    """Kontrollér credential-navnet."""

    if not isinstance(
        credential_name,
        str,
    ):
        raise TypeError(
            "credential_name skal være tekst."
        )

    clean_name = credential_name.strip()

    if not clean_name:
        raise ValueError(
            "credential_name skal udfyldes. "
            "Angiv navnet på en credential i "
            "Automation Server, før Prisme API "
            "kan initialiseres."
        )

    return clean_name


def _require_config_text(
    data: dict,
    field_name: str,
    credential_name: str,
) -> str:
    """Hent obligatorisk konfigurationsfelt."""

    if field_name not in data:
        raise PrismeAuthenticationError(
            "Credential mangler obligatorisk "
            f"felt: {field_name!r}.",
            method="CREDENTIAL",
            endpoint=credential_name,
        )

    value = data[field_name]

    if value is None:
        raise PrismeAuthenticationError(
            "Credential-feltet er tomt: "
            f"{field_name!r}.",
            method="CREDENTIAL",
            endpoint=credential_name,
        )

    text_value = str(
        value
    ).strip()

    if not text_value:
        raise PrismeAuthenticationError(
            "Credential-feltet er tomt: "
            f"{field_name!r}.",
            method="CREDENTIAL",
            endpoint=credential_name,
        )

    return text_value


def _validate_absolute_url(
    value: str,
    field_name: str,
    credential_name: str,
) -> None:
    """Kontrollér en URL fra credentialen."""

    if not value.startswith(
        (
            "https://",
            "http://",
        )
    ):
        raise PrismeAuthenticationError(
            "Credential-feltet skal indeholde "
            f"en fuld URL: {field_name!r}.",
            method="CREDENTIAL",
            endpoint=credential_name,
        )


def _require_initialised() -> PrismeConfiguration:
    """Kræv at Prisme er initialiseret."""

    if _config is None:
        raise PrismeAuthenticationError(
            "Prisme API er ikke initialiseret. "
            "Kald "
            "initialiser_prisme("
            "credential_name) "
            "ved processtart.",
            method="INITIALISE",
            endpoint="initialiser_prisme",
        )

    return _config


# ------------------------------------------------------------
# TOKEN
# ------------------------------------------------------------

def get_token() -> str:
    """
    Hent eller genbrug access token.

    Token hentes kun, når:

        Token mangler.
        Token snart udløber.
        Token blev nulstillet efter HTTP 401.
        En ny credential blev initialiseret.
    """

    global _access_token
    global _token_expiry

    config = _require_initialised()

    logger.debug(
        "get_token blev kaldt"
    )

    token_is_valid = (
        _access_token is not None
        and bool(_access_token)
        and time.time()
        < (
            _token_expiry
            - TOKEN_BUFFER
        )
    )

    if token_is_valid:
        logger.debug(
            "Bruger cached access token"
        )

        return _access_token

    logger.info(
        "Henter nyt Prisme access token "
        "for credential: %s",
        config.credential_name,
    )

    payload = {
        "tenant_id": config.tenant_id,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "resource": config.resource,
        "grant_type": config.grant_type,
    }

    headers = {
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
        "Accept": "application/json",
    }

    try:
        response = _session.post(
            config.token_url,
            data=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as error:
        raise PrismeAuthenticationError(
            "Timeout ved hentning af token.",
            method="POST",
            endpoint=config.token_url,
        ) from error
    except requests.RequestException as error:
        raise PrismeAuthenticationError(
            "Teknisk fejl ved hentning af token.",
            method="POST",
            endpoint=config.token_url,
            response_text=str(error),
        ) from error

    if response.status_code >= 300:
        raise PrismeAuthenticationError(
            "Token kunne ikke hentes.",
            method="POST",
            endpoint=config.token_url,
            status_code=response.status_code,
            response_text=response.text,
        )

    try:
        data = response.json()
    except ValueError as error:
        raise PrismeAuthenticationError(
            "Token-svaret var ikke gyldig JSON.",
            method="POST",
            endpoint=config.token_url,
            status_code=response.status_code,
            response_text=response.text,
        ) from error

    if not isinstance(
        data,
        dict,
    ):
        raise PrismeAuthenticationError(
            "Token-svaret var ikke et "
            "JSON-objekt.",
            method="POST",
            endpoint=config.token_url,
            status_code=response.status_code,
            response_text=response.text,
        )

    raw_access_token = data.get(
        "access_token"
    )

    if not raw_access_token:
        raise PrismeAuthenticationError(
            "Token-svaret mangler access_token.",
            method="POST",
            endpoint=config.token_url,
            status_code=response.status_code,
            response_text=response.text,
        )

    access_token = str(
        raw_access_token
    ).strip()

    if not access_token:
        raise PrismeAuthenticationError(
            "Token-svaret har et tomt "
            "access_token.",
            method="POST",
            endpoint=config.token_url,
            status_code=response.status_code,
            response_text=response.text,
        )

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
            "Token-svaret har ugyldig "
            "expires_in.",
            method="POST",
            endpoint=config.token_url,
            status_code=response.status_code,
            response_text=response.text,
        ) from error

    if expires_in_seconds <= 0:
        raise PrismeAuthenticationError(
            "Token-svaret har en ugyldig "
            "udløbstid.",
            method="POST",
            endpoint=config.token_url,
            status_code=response.status_code,
            response_text=response.text,
        )

    _access_token = access_token

    _token_expiry = (
        time.time()
        + expires_in_seconds
    )

    logger.info(
        "Nyt Prisme access token modtaget"
    )

    return _access_token


def _clear_token() -> None:
    """Nulstil det cachede token."""

    global _access_token
    global _token_expiry

    _access_token = None
    _token_expiry = 0.0


# ------------------------------------------------------------
# GET
# ------------------------------------------------------------

def get(
    endpoint: str,
):
    """
    Udfør GET-kald til Prisme.

    OData-svar med value returneres som
    en liste.

    Alle OData-sider hentes automatisk.

    Andre JSON-svar returneres uændret.
    """

    _require_initialised()

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

    _require_initialised()

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

    _require_initialised()

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

    _require_initialised()

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

        HTTP 401 én gang med nyt token.
        HTTP 429.
        HTTP 502.
        HTTP 503.
        HTTP 504.
        Timeout.
    """

    attempt = 0
    authentication_retry_used = False

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

        if (
            response.status_code == 401
            and not authentication_retry_used
        ):
            logger.warning(
                "GET returnerede HTTP 401. "
                "Henter nyt token og gentager "
                "kaldet én gang."
            )

            _clear_token()

            authentication_retry_used = True

            continue

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

    Skrivende kald genforsøges normalt ikke.

    Ved HTTP 401 hentes et nyt token, og det
    samme kald gentages præcis én gang.
    """

    authentication_retry_used = False

    while True:
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
                method=(
                    request_arguments["method"]
                ),
                url=request_arguments["url"],
                headers=(
                    request_arguments["headers"]
                ),
                timeout=(
                    request_arguments["timeout"]
                ),
                json=request_arguments.get(
                    "json"
                ),
            )
        except requests.Timeout as error:
            raise PrismeApiError(
                f"{method}-kaldet fik timeout.",
                method=method,
                endpoint=url,
            ) from error
        except requests.RequestException as error:
            raise PrismeApiError(
                "Teknisk fejl ved "
                f"{method}-kald.",
                method=method,
                endpoint=url,
                response_text=str(error),
            ) from error

        if (
            response.status_code == 401
            and not authentication_retry_used
        ):
            logger.warning(
                "%s returnerede HTTP 401. "
                "Henter nyt token og gentager "
                "kaldet én gang.",
                method,
            )

            _clear_token()

            authentication_retry_used = True

            continue

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

    config = _require_initialised()

    if endpoint.startswith(
        (
            "https://",
            "http://",
        )
    ):
        return endpoint

    normalized_base_url = (
        config.base_url.rstrip("/")
        + "/"
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
            "Prisme afviste godkendelsen, "
            "og et nyt token løste ikke "
            "problemet.",
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