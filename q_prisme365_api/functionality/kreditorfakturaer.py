"""Standardfunktioner til bogførte kreditorfakturaer i Prisme 365."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

from q_prisme365_api.api_client import get

__all__ = [
    "hent_kreditorfakturaer",
    "hent_kreditorfaktura",
    "hent_oprindelige_fakturaposter",
    "iterer_dato_intervaller",
]

logger = logging.getLogger(__name__)
VEND_TRANS_ENDPOINT = "VendTransDatasEntity_FUJ"
VEND_INVOICE_INFO_ENDPOINT = "VendInvoiceInfoTableDatasEntity_FUJ"
DEFAULT_COMPANY_ID = "had"
DEFAULT_TOP = 100000


def hent_kreditorfakturaer(
    fakturadato_fra: date,
    fakturadato_til: date,
    voucher_prefix: str | None = "EFAK-",
    data_area_id: str = DEFAULT_COMPANY_ID,
    top: int = DEFAULT_TOP,
    inkluder_raw: bool = False,
) -> list[dict[str, Any]]:
    """Hent bogførte kreditorfakturaer i et datointerval.

    Intervallet er halvåbent:

        fakturadato_fra er inklusive
        fakturadato_til er eksklusive

    Prisme filtreres server-side på:

        dataAreaId
        DocumentDate fra
        DocumentDate til

    Følgende filtreres lokalt i Python:

        TransType = Purch
        Invoice skal være udfyldt
        Voucher skal begynde med voucher_prefix

    Voucher filtreres lokalt, fordi startswith() ikke
    understøttes af OData-laget for denne Prisme-entitet.

    Args:
        fakturadato_fra:
            Første fakturadato, inklusive.

        fakturadato_til:
            Slutdato, eksklusive.

        voucher_prefix:
            Valgfrit præfiks til Voucher.

            Standard:
                "EFAK-"

            Hvis værdien er None eller tom tekst,
            filtreres der ikke på Voucher.

        data_area_id:
            Selskabet i Prisme.

            Standard:
                "had"

        top:
            Maksimalt antal rækker, der anmodes om.

        inkluder_raw:
            True tilføjer den rå Prisme-række under:

                raw

    Returns:
        En liste med normaliserede kreditorfakturaer.

        Eksempel:

        [
            {
                "Fakturanummer": "1114013",
                "Kreditorkonto": "000113",
                "Kreditornavn": "BANDAGIST-CENTRET ...",
                "Fakturadato": "2026-09-23T12:00:00Z",
                "Bogføringsdato": "2026-09-23T12:00:00Z",
                "Forfaldsdato": "2026-10-23T12:00:00Z",
                "Voucher": "EFAK-000336028",
                "Beløb": -2343.68,
                "Valuta": "DKK",
                "RecIdLoc": 5638132146,
                "AccountingEvent": 5638245807,
                "OprettetDato": "2026-09-24T07:36:21Z",
                "ÆndretDato": "2026-09-24T07:36:21Z",
                "dataAreaId": "had",
            }
        ]
    """
    dato_fra = _validate_date(
        fakturadato_fra,
        "fakturadato_fra",
    )
    dato_til = _validate_date(
        fakturadato_til,
        "fakturadato_til",
    )

    if dato_fra >= dato_til:
        raise ValueError(
            "fakturadato_fra skal være før "
            "fakturadato_til."
        )

    company = _required_text(
        data_area_id,
        "data_area_id",
    )
    validated_top = _positive_int(
        top,
        "top",
    )
    clean_voucher_prefix = _optional_text(
        voucher_prefix
    )

    # Voucher-præfikset er bevidst ikke med i
    # OData-filteret. Prisme understøtter ikke:
    #
    #     startswith(Voucher, 'EFAK-')
    #
    # Filtreringen udføres derfor lokalt nedenfor.
    endpoint = (
        f"{VEND_TRANS_ENDPOINT}"
        f"?$top={validated_top}"
        "&$filter="
        f"dataAreaId eq '{_escape(company)}'"
        " and "
        f"DocumentDate ge {_odata_datetime(dato_fra)}"
        " and "
        f"DocumentDate lt {_odata_datetime(dato_til)}"
    )

    logger.info(
        "Henter kreditorfakturaer fra %s "
        "til før %s",
        dato_fra,
        dato_til,
    )

    logger.debug(
        "Kreditorfaktura endpoint: %s",
        endpoint,
    )

    response = get(
        endpoint
    )

    rows = _normalize_list(
        response,
        "kreditorfakturaudtrækket",
    )

    result: list[dict[str, Any]] = []

    for row in rows:
        trans_type = str(
            row.get(
                "TransType",
                "",
            )
            or ""
        ).strip().casefold()

        if trans_type != "purch":
            continue

        invoice_number = str(
            row.get(
                "Invoice",
                "",
            )
            or ""
        ).strip()

        if not invoice_number:
            continue

        voucher = str(
            row.get(
                "Voucher",
                "",
            )
            or ""
        ).strip()

        if clean_voucher_prefix is not None:
            if not voucher.casefold().startswith(
                clean_voucher_prefix.casefold()
            ):
                continue

        item = _normalize_vendor_transaction(
            row
        )

        if inkluder_raw:
            item["raw"] = dict(
                row
            )

        result.append(
            item
        )

    logger.info(
        "Kreditorfakturaudtrækket returnerede "
        "%s fakturaer efter lokal filtrering",
        len(result),
    )

    return result


def hent_kreditorfaktura(
    fakturanummer: str,
    kreditorkonto: str,
    data_area_id: str = DEFAULT_COMPANY_ID,
    top: int = 20,
    inkluder_raw: bool = False,
) -> list[dict[str, Any]]:
    """Hent bogførte kreditorfakturaer på nummer og kreditorkonto.

    Output er en liste, da samme nummer i sjældne tilfælde kan forekomme
    mere end én gang. Kun TransType=Purch returneres.
    """
    invoice = _required_text(fakturanummer, "fakturanummer")
    vendor = _required_text(kreditorkonto, "kreditorkonto")
    company = _required_text(data_area_id, "data_area_id")
    endpoint = (
        f"{VEND_TRANS_ENDPOINT}?$top={_positive_int(top, 'top')}&$filter="
        f"Invoice eq '{_escape(invoice)}' and AccountNum eq '{_escape(vendor)}' "
        f"and dataAreaId eq '{_escape(company)}'"
    )
    rows = _normalize_list(get(endpoint), "kreditorfakturaopslaget")
    result = []
    for row in rows:
        if str(row.get("TransType") or "").strip().casefold() != "purch":
            continue
        item = _normalize_vendor_transaction(row)
        if inkluder_raw:
            item["raw"] = dict(row)
        result.append(item)
    return result


def hent_oprindelige_fakturaposter(
    fakturadato_fra: date | None = None,
    fakturadato_til: date | None = None,
    fakturanummer: str | None = None,
    kreditorkonto: str | None = None,
    data_area_id: str = DEFAULT_COMPANY_ID,
    top: int = DEFAULT_TOP,
    inkluder_raw: bool = False,
) -> list[dict[str, Any]]:
    """Hent oprindelige fakturaposter fra VendInvoiceInfo.

    Output indeholder Num, OrderAccount, DocumentDate,
    ImportedInvoiceAmount, RecIdLoc og HeaderReference.
    Brug enten et halvåbent datointerval eller fakturanummer+kreditorkonto.
    """
    company = _required_text(data_area_id, "data_area_id")
    filters = [f"dataAreaId eq '{_escape(company)}'"]
    has_dates = fakturadato_fra is not None or fakturadato_til is not None
    has_keys = fakturanummer is not None or kreditorkonto is not None
    if has_dates:
        if fakturadato_fra is None or fakturadato_til is None:
            raise ValueError("Begge fakturadatoer skal angives.")
        dato_fra = _validate_date(fakturadato_fra, "fakturadato_fra")
        dato_til = _validate_date(fakturadato_til, "fakturadato_til")
        if dato_fra >= dato_til:
            raise ValueError("fakturadato_fra skal være før fakturadato_til.")
        filters.extend([
            f"DocumentDate ge {_odata_datetime(dato_fra)}",
            f"DocumentDate lt {_odata_datetime(dato_til)}",
        ])
    if has_keys:
        if fakturanummer is None or kreditorkonto is None:
            raise ValueError("Både fakturanummer og kreditorkonto skal angives.")
        filters.extend([
            f"Num eq '{_escape(_required_text(fakturanummer, 'fakturanummer'))}'",
            f"OrderAccount eq '{_escape(_required_text(kreditorkonto, 'kreditorkonto'))}'",
        ])
    if not has_dates and not has_keys:
        raise ValueError("Angiv datointerval eller fakturanummer+kreditorkonto.")
    endpoint = (
        f"{VEND_INVOICE_INFO_ENDPOINT}?$top={_positive_int(top, 'top')}"
        f"&$filter={' and '.join(filters)}"
    )
    rows = _normalize_list(get(endpoint), "opslaget i VendInvoiceInfo")
    result = []
    for row in rows:
        item = {
            "Fakturanummer": str(row.get("Num") or "").strip(),
            "Kreditorkonto": str(row.get("OrderAccount") or "").strip(),
            "Fakturadato": row.get("DocumentDate"),
            "Beløb": row.get("ImportedInvoiceAmount"),
            "RecIdLoc": _optional_int(row.get("RecIdLoc")),
            "HeaderReference": str(row.get("HeaderReference") or "").strip(),
            "ModifiedDateTime": row.get("ModifiedDateTime_FUJ"),
            "EndDateTime": row.get("EndDateTime"),
            "dataAreaId": row.get("dataAreaId"),
        }
        if inkluder_raw:
            item["raw"] = dict(row)
        result.append(item)
    return result


def iterer_dato_intervaller(dato_fra: date, dato_til: date, interval_dage: int = 14) -> Iterator[tuple[date, date]]:
    """Yield halvåbne datointervaller som (fra, til)."""
    from datetime import timedelta
    current = _validate_date(dato_fra, "dato_fra")
    end = _validate_date(dato_til, "dato_til")
    days = _positive_int(interval_dage, "interval_dage")
    if current >= end:
        raise ValueError("dato_fra skal være før dato_til.")
    while current < end:
        next_date = min(current + timedelta(days=days), end)
        yield current, next_date
        current = next_date


def _normalize_vendor_transaction(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "Fakturanummer": str(row.get("Invoice") or "").strip(),
        "Kreditorkonto": str(row.get("AccountNum") or "").strip(),
        "Kreditornavn": str(row.get("Name") or "").strip(),
        "Fakturadato": row.get("DocumentDate"),
        "Bogføringsdato": row.get("TransDate"),
        "Forfaldsdato": row.get("DueDate"),
        "Voucher": str(row.get("Voucher") or "").strip(),
        "Beløb": row.get("AmountCur"),
        "Valuta": str(row.get("CurrencyCode") or "").strip(),
        "RecIdLoc": _optional_int(row.get("RecIdLoc")),
        "AccountingEvent": _optional_int(row.get("AccountingEvent")),
        "OprettetDato": row.get("CreatedDateTimeLoc"),
        "ÆndretDato": row.get("ModifiedDateTimeLoc"),
        "dataAreaId": row.get("dataAreaId"),
    }


def _normalize_list(response: Any, operation: str) -> list[dict[str, Any]]:
    if response is None:
        return []
    if not isinstance(response, list):
        raise TypeError(f"API-svaret for {operation} skal være en liste.")
    return [dict(row) for row in response if isinstance(row, dict)]


def _odata_datetime(value: date) -> str:
    return datetime.combine(value, time.min, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_part(value: Any) -> str:
    return str(value or "")[:10]


def _optional_int(value: Any) -> int | None:
    if value in (None, "", 0, "0") or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _validate_date(value: Any, name: str) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError(f"{name} skal være en date-værdi.")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} skal være et positivt heltal.")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} skal være et positivt heltal.") from error
    if result <= 0:
        raise ValueError(f"{name} skal være større end 0.")
    return result


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} skal udfyldes.")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _escape(value: str) -> str:
    return value.replace("'", "''")
