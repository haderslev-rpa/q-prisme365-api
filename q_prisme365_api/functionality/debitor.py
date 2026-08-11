"""
Funktioner til debitorer i Prisme 365.

Blue Prism-action:
    Debitor: Debitorer søg

Prisme-endpoint:
    CustTableDatasEntity_FUJ
"""

from typing import Any

from q_prisme365_api.api_client import get
from q_prisme365_api.odata import (
    DEFAULT_TOP,
    build_odata_endpoint,
    string_equals,
)


DEBITOR_ENDPOINT = "CustTableDatasEntity_FUJ"


def build_debitor_search_endpoint(
    *,
    cpr_cvr: str | None = None,
    debitorgruppe: str | None = None,
    debitorkonto: str | None = None,
    debitornummer: str | None = None,
    top: int = DEFAULT_TOP,
) -> str:
    """
    Bygger endpointet til søgning efter debitorer.

    Funktionen foretager ikke et API-kald. Den bygger kun adressen.
    Det gør filterlogikken nem at teste uden forbindelse til Prisme.

    Args:
        cpr_cvr:
            CPR- eller CVR-nummer.

        debitorgruppe:
            Prismes debitorgruppe.

        debitorkonto:
            Prismes debitorkonto.

        debitornummer:
            Debitornummer. Wildcard med * kan anvendes.

        top:
            Maksimalt antal rækker. Standard er 10000.

    Returns:
        Relativt endpoint til api_client.get.
    """
    filters = [
        string_equals("IdentificationNumber", cpr_cvr),
        string_equals("CustGroup", debitorgruppe),
        string_equals("AccountNum", debitorkonto),
        string_equals("DebtorNumber", debitornummer),
    ]

    return build_odata_endpoint(
        DEBITOR_ENDPOINT,
        filters=filters,
        top=top,
    )


def search_debitorer(
    *,
    cpr_cvr: str | None = None,
    debitorgruppe: str | None = None,
    debitorkonto: str | None = None,
    debitornummer: str | None = None,
    top: int = DEFAULT_TOP,
) -> list[dict[str, Any]]:
    """
    Søger efter debitorer i Prisme 365.

    Funktionen svarer til Blue Prism-actionen:
        Debitor: Debitorer søg

    Alle søgekriterier er valgfrie. Hvis flere kriterier angives,
    kombineres kriterierne med OData-operatoren "and".

    Args:
        cpr_cvr:
            CPR- eller CVR-nummer.

        debitorgruppe:
            Debitorgruppe, eksempelvis "289000".

        debitorkonto:
            Debitorkonto, eksempelvis "00110513".

        debitornummer:
            Debitornummer. Wildcard med * kan anvendes, hvis
            Prisme-endpointet understøtter den eksisterende
            Blue Prism-adfærd.

        top:
            Maksimalt antal rækker. Standard er 10000.

    Returns:
        En liste med debitorer fra Prisme.

    Eksempel:
        debitorer = search_debitorer(
            cpr_cvr="0104852289",
            debitorgruppe="289000",
        )

        antal = len(debitorer)
    """
    endpoint = build_debitor_search_endpoint(
        cpr_cvr=cpr_cvr,
        debitorgruppe=debitorgruppe,
        debitorkonto=debitorkonto,
        debitornummer=debitornummer,
        top=top,
    )

    response = get(endpoint)

    if response is None:
        return []

    if not isinstance(response, list):
        raise TypeError(
            "API-klientens get-funktion skal returnere en liste, "
            f"men returnerede {type(response).__name__}"
        )

    return response