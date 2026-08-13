"""Funktioner til fakturaer i Prisme 365."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from typing import Any

from q_prisme365_api.api_client import get
from q_prisme365_api.api_client import patch
from q_prisme365_api.api_client import post
from q_prisme365_api.functionality.dokumenter import (
    search_dokumenter,
)

from q_prisme365_api.exceptions import (
    PrismeNotFoundError,
)
from q_prisme365_api.odata import (
    eq_number,
    eq_text,
)


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------

FAKTURA_LISTE_ENDPOINT = "VendorInvoiceHeaders"

FAKTURA_DETALJER_ENDPOINT = (
    "VendInvoiceInfoTableDatasEntity_FUJ"
)

FAKTURA_HEADER_ENDPOINT = (
    "FUJ_VendorInvoiceHeaderEntity"
)

FAKTURA_KONTERINGSLINJER_ENDPOINT = (
    "FUJ_VendorInvoiceLineEntity"
)


# ------------------------------------------------------------
# STANDARDVÆRDIER
# ------------------------------------------------------------

DEFAULT_DATA_AREA_ID = "had"
DEFAULT_TOP = 10000

def search_fakturaer(
    godkender_initialer: str | None = None,
    afdeling: str | None = None,
    leverandoernummer: str | None = None,
    oprettet_dato_start: date | datetime | None = None,
    header_reference: str | None = None,
    fakturabeskrivelse: str | None = None,
    hent_detaljer: bool = True,
    hent_dokumenter: bool = False,
    hent_dokumentplacering: bool = True,
    dokument_domain_suffix: str | None = (
        "prisme-365.dk"
    ),
    top: int = DEFAULT_TOP,
) -> list[dict[str, Any]]:
    """
    Hent en liste over fakturaer.

    Funktionen følger Blue Prism-processen:
        Faktura: Hent liste over fakturaer

    Første opslag:
        VendorInvoiceHeaders

    Detaljeret opslag:
        VendInvoiceInfoTableDatasEntity_FUJ

    Dokumentopslag:
        DocuRefDatasEntity_FUJ

    Dokumentinformation:
        DocuValueDatasEntity_FUJ

    Fakturaer med status Draft frasorteres
    direkte i Prisme med D365-enum-filter.

    Når hent_dokumenter er True:

    1. Fakturadetaljerne hentes automatisk.
    2. RecIdLoc læses fra detaljerne.
    3. Dokumenter søges med:
       RefCompanyId = had
       RefTableId = 6084
       RefRecId = fakturaens RecIdLoc
    4. Notater og fysiske filer returneres.
    5. Fysiske filer kan udvides med filnavn
       og dokumentsti.

    Args:
        godkender_initialer:
            Filter på ApproverPersonnelNumber.

        afdeling:
            Afdeling på præcis 12 cifre.

        leverandoernummer:
            Filter på VendorAccount.

        oprettet_dato_start:
            Hent fakturaer med
            InvoiceReceivedDate fra og med
            den angivne dato.

        header_reference:
            Fakturaens unikke HeaderReference.

        fakturabeskrivelse:
            Filter på InvoiceDescription.

        hent_detaljer:
            True tilføjer oplysninger fra
            VendInvoiceInfoTableDatasEntity_FUJ.

        hent_dokumenter:
            True henter dokumenter og notater,
            som er tilknyttet fakturaen.

        hent_dokumentplacering:
            True henter filnavn og filplacering
            for dokumenter med ValueRecId.

        dokument_domain_suffix:
            Valgfrit domæne til dokumentets
            UNC-sti.

            Standard:
                prisme-365.dk

        top:
            Maksimalt antal fakturaer.

    Returns:
        En liste med normaliserede fakturaer.
    """

    validated_top = _validate_positive_integer(
        top,
        "top",
    )

    if not isinstance(
        hent_detaljer,
        bool,
    ):
        raise TypeError(
            "hent_detaljer skal være "
            "True eller False."
        )

    if not isinstance(
        hent_dokumenter,
        bool,
    ):
        raise TypeError(
            "hent_dokumenter skal være "
            "True eller False."
        )

    if not isinstance(
        hent_dokumentplacering,
        bool,
    ):
        raise TypeError(
            "hent_dokumentplacering skal være "
            "True eller False."
        )

    # VendorInvoiceReviewStatus er en
    # Dynamics 365-enum, ikke almindelig tekst.
    draft_filter = (
        "VendorInvoiceReviewStatus ne "
        "Microsoft.Dynamics.DataEntities."
        "VendInvoiceRequestStatus'Draft'"
    )

    filters = [
        draft_filter,
    ]

    clean_header_reference = _clean_optional_text(
        header_reference
    )

    if clean_header_reference is not None:
        filters.append(
            eq_text(
                "HeaderReference",
                clean_header_reference,
            )
        )

        filters.append(
            eq_text(
                "dataAreaId",
                DEFAULT_DATA_AREA_ID,
            )
        )

    else:
        clean_approver = _clean_optional_text(
            godkender_initialer
        )

        if clean_approver is not None:
            filters.append(
                eq_text(
                    "ApproverPersonnelNumber",
                    clean_approver,
                )
            )

        clean_description = _clean_optional_text(
            fakturabeskrivelse
        )

        if clean_description is not None:
            filters.append(
                eq_text(
                    "InvoiceDescription",
                    clean_description,
                )
            )

        clean_department = _clean_optional_text(
            afdeling
        )

        if clean_department is not None:
            validated_department = (
                _validate_afdeling(
                    clean_department
                )
            )

            dimension_display_value = (
                validated_department + "----"
            )

            filters.append(
                eq_text(
                    "DimensionDisplayValue",
                    dimension_display_value,
                )
            )

        clean_vendor_account = (
            _clean_optional_text(
                leverandoernummer
            )
        )

        if clean_vendor_account is not None:
            filters.append(
                eq_text(
                    "VendorAccount",
                    clean_vendor_account,
                )
            )

        if oprettet_dato_start is not None:
            formatted_date = (
                _format_odata_datetime(
                    oprettet_dato_start
                )
            )

            filters.append(
                "InvoiceReceivedDate ge "
                + formatted_date
            )

    endpoint = _build_endpoint(
        entity=FAKTURA_LISTE_ENDPOINT,
        filters=filters,
        top=validated_top,
    )

    logger.info(
        "Henter fakturaliste uden Draft-fakturaer"
    )

    logger.debug(
        "Fakturaliste endpoint: %s",
        endpoint,
    )

    response = get(
        endpoint
    )

    rows = _normalize_list_response(
        response,
        "fakturalisten",
    )

    # Lokal kontrol bevares som ekstra sikkerhed.
    # Draft bør allerede være fjernet af Prisme.
    filtered_rows = []

    for row in rows:
        review_status = str(
            row.get(
                "VendorInvoiceReviewStatus",
                "",
            )
            or ""
        ).strip()

        if review_status.casefold() == "draft":
            logger.warning(
                "Prisme returnerede en "
                "Draft-faktura, selv om Draft "
                "var frasorteret i "
                "OData-filteret"
            )

            continue

        filtered_rows.append(
            row
        )

    logger.info(
        "Fandt %s fakturaer uden Draft-status",
        len(filtered_rows),
    )

    results = []

    for row in filtered_rows:
        normalized_invoice = (
            _map_standard_faktura(
                row
            )
        )

        reference = normalized_invoice.get(
            "HeaderReference"
        )

        details = None

        # Dokumentopslaget kræver fakturaens
        # RecIdLoc fra detailentiteten.
        #
        # Derfor hentes detaljerne også, når
        # hent_detaljer=False, men
        # hent_dokumenter=True.
        should_load_details = (
            hent_detaljer
            or hent_dokumenter
        )

        if (
            should_load_details
            and reference
        ):
            details = get_faktura_detaljer(
                header_reference=str(
                    reference
                )
            )

        if (
            hent_detaljer
            and details is not None
        ):
            _apply_detailed_information(
                normalized_invoice,
                details,
            )

        dokumenter = []

        if hent_dokumenter:
            if details is None:
                raise ValueError(
                    "Dokumenterne kunne ikke "
                    "hentes, fordi fakturaens "
                    "detaljer ikke blev fundet. "
                    "HeaderReference: "
                    f"{reference!r}."
                )

            raw_rec_id = details.get(
                "RecIdLoc"
            )

            if raw_rec_id in (
                None,
                "",
                0,
                "0",
            ):
                raise ValueError(
                    "Dokumenterne kunne ikke "
                    "hentes, fordi fakturaens "
                    "RecIdLoc mangler. "
                    "HeaderReference: "
                    f"{reference!r}."
                )

            faktura_rec_id = (
                _validate_positive_integer(
                    raw_rec_id,
                    "fakturaens RecIdLoc",
                )
            )

            logger.info(
                "Henter dokumenter for "
                "HeaderReference %s og "
                "RecIdLoc %s",
                reference,
                faktura_rec_id,
            )

            dokumenter = search_dokumenter(
                ref_rec_id=faktura_rec_id,
                tabel=(
                    "ventende_kreditorfaktura"
                ),
                hent_dokumentplacering=(
                    hent_dokumentplacering
                ),
                domain_suffix=(
                    dokument_domain_suffix
                ),
                top=1000,
            )

        normalized_invoice[
            "Vedhæftede dokumenter"
        ] = dokumenter

        results.append(
            normalized_invoice
        )

    return results

def get_faktura_detaljer(
    header_reference: str,
) -> dict[str, Any]:
    """
    Hent detaljerede fakturaoplysninger.

    Blue Prism bruger:
        VendInvoiceInfoTableDatasEntity_FUJ

    Filter:
        TableRefId eq '<HeaderReference>'
    """

    clean_reference = _require_text(
        header_reference,
        "header_reference",
    )

    endpoint = _build_endpoint(
        entity=FAKTURA_DETALJER_ENDPOINT,
        filters=[
            eq_text(
                "TableRefId",
                clean_reference,
            )
        ],
        top=2,
    )

    logger.info(
        "Henter detaljer for HeaderReference %s",
        clean_reference,
    )

    response = get(endpoint)

    rows = _normalize_list_response(
        response,
        "detaljeret fakturaopslag",
    )

    if not rows:
        raise PrismeNotFoundError(
            "Detaljerede fakturaoplysninger "
            "blev ikke fundet.",
            method="GET",
            endpoint=endpoint,
        )

    if len(rows) != 1:
        raise ValueError(
            "Det detaljerede fakturaopslag "
            "var ikke entydigt. "
            f"HeaderReference: {clean_reference}. "
            f"Antal rækker: {len(rows)}."
        )

    return rows[0]


def get_faktura(
    rec_id_loc: int,
) -> dict[str, Any]:
    """
    Hent én faktura via RecIdLoc.

    Endpoint:
        FUJ_VendorInvoiceHeaderEntity
    """

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    endpoint = _build_endpoint(
        entity=FAKTURA_HEADER_ENDPOINT,
        filters=[
            eq_number(
                "RecIdLoc",
                validated_rec_id,
            )
        ],
        top=2,
    )

    response = get(endpoint)

    rows = _normalize_list_response(
        response,
        "fakturaopslaget",
    )

    if not rows:
        raise PrismeNotFoundError(
            "Fakturaen blev ikke fundet.",
            method="GET",
            endpoint=endpoint,
        )

    if len(rows) != 1:
        raise ValueError(
            "RecIdLoc var ikke entydigt. "
            f"RecIdLoc: {validated_rec_id}. "
            f"Antal fakturaer: {len(rows)}."
        )

    return rows[0]


def get_faktura_by_header_reference(
    header_reference: str,
    data_area_id: str = DEFAULT_DATA_AREA_ID,
) -> dict[str, Any]:
    """
    Hent én faktura via HeaderReference.

    Endpoint:
        VendorInvoiceHeaders
    """

    clean_reference = _require_text(
        header_reference,
        "header_reference",
    )

    clean_data_area_id = _require_text(
        data_area_id,
        "data_area_id",
    )

    endpoint = _build_endpoint(
        entity=FAKTURA_LISTE_ENDPOINT,
        filters=[
            eq_text(
                "HeaderReference",
                clean_reference,
            ),
            eq_text(
                "dataAreaId",
                clean_data_area_id,
            ),
        ],
        top=2,
    )

    response = get(endpoint)

    rows = _normalize_list_response(
        response,
        "fakturaopslaget",
    )

    if not rows:
        raise PrismeNotFoundError(
            "Fakturaen blev ikke fundet.",
            method="GET",
            endpoint=endpoint,
        )

    if len(rows) != 1:
        raise ValueError(
            "HeaderReference var ikke entydig. "
            f"HeaderReference: {clean_reference}. "
            f"Antal fakturaer: {len(rows)}."
        )

    return rows[0]


def get_faktura_konteringslinjer(
    header_reference: str,
    top: int = 10000,
) -> list[dict[str, Any]]:
    """
    Hent fakturaens konteringslinjer.

    Endpoint:
        FUJ_VendorInvoiceLineEntity
    """

    clean_reference = _require_text(
        header_reference,
        "header_reference",
    )

    validated_top = _validate_positive_integer(
        top,
        "top",
    )

    endpoint = _build_endpoint(
        entity=FAKTURA_KONTERINGSLINJER_ENDPOINT,
        filters=[
            eq_text(
                "HeaderReference",
                clean_reference,
            )
        ],
        top=validated_top,
    )

    response = get(endpoint)

    rows = _normalize_list_response(
        response,
        "konteringslinjeopslaget",
    )

    if _all_rows_have_line_number(rows):
        rows.sort(
            key=_line_sort_value
        )

    return rows


def get_faktura_approver(
    rec_id_loc: int,
) -> str:
    """Hent fakturaens aktuelle godkender."""

    faktura = get_faktura(
        rec_id_loc
    )

    value = faktura.get(
        "ApproverPersonnelNumber"
    )

    if value in (None, ""):
        return ""

    return str(value).strip()


def validate_faktura_amount(
    fakturabeloeb: Decimal,
    konteringslinjer: Iterable[
        dict[str, Any]
    ],
    tolerance: Decimal = Decimal("1.00"),
) -> bool:
    """
    Kontrollér om konteringslinjerne
    matcher fakturabeløbet.
    """

    invoice_amount = _to_decimal(
        fakturabeloeb
    )

    validated_tolerance = _to_decimal(
        tolerance
    )

    if validated_tolerance < Decimal("0"):
        raise ValueError(
            "tolerance må ikke være negativ."
        )

    total = Decimal("0")

    for line in konteringslinjer:
        if not isinstance(line, dict):
            raise TypeError(
                "Hver konteringslinje skal "
                "være en dictionary."
            )

        if "GrossAmount" in line:
            raw_value = line.get(
                "GrossAmount"
            )
        else:
            raw_value = line.get(
                "Bruttobeløb",
                "0",
            )

        total += _to_decimal(
            raw_value
        )

    difference = abs(
        invoice_amount - total
    )

    return difference < validated_tolerance


def _map_standard_faktura(
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    Omsæt VendorInvoiceHeaders til de felter,
    som Blue Prism returnerede.
    """

    dimension_display_value = str(
        row.get(
            "DimensionDisplayValue",
            "",
        )
        or ""
    )

    department = dimension_display_value[:12]

    is_approved_value = str(
        row.get(
            "IsApproved",
            "",
        )
        or ""
    ).casefold()

    is_approved = (
        is_approved_value == "yes"
    )

    vendor_account = str(
        row.get(
            "VendorAccount",
            "",
        )
        or ""
    ).strip()

    invoice_number = str(
        row.get(
            "InvoiceNumber",
            "",
        )
        or ""
    ).strip()

    tax_exempt_number = str(
        row.get(
            "TaxExemptNumber",
            "",
        )
        or ""
    ).strip()

    if tax_exempt_number.startswith("DK"):
        tax_exempt_number = (
            tax_exempt_number[2:]
        )

    return {
        "HeaderReference": row.get(
            "HeaderReference"
        ),
        "Fakturanr": invoice_number,
        "Importeret fakturabeløb": None,
        "Momsbeløb": None,
        "Kreditorkonto": vendor_account,
        "Afdeling": department,
        "Godkender": row.get(
            "ApproverPersonnelNumber"
        ),
        "EAN": None,
        "Leverandørnavn": row.get(
            "VendorName"
        ),
        "CVR": tax_exempt_number,
        "Dato for modtagelse af faktura": (
            row.get("InvoiceReceivedDate")
        ),
        "Dato": row.get("Date"),
        "Fakturadato": row.get(
            "InvoiceDate"
        ),
        "Forfaldsdato": row.get(
            "DueDate"
        ),
        "VendorInvoiceReviewStatus": (
            row.get(
                "VendorInvoiceReviewStatus"
            )
        ),
        "RecIdLoc": None,
        "Købers ordrenr": None,
        "IsApproved": is_approved,
        "Vedhæftede dokumenter": [],
        "Kreditorkonto og Fakturanr": (
            vendor_account
            + " - "
            + invoice_number
        ),
        "raw_header": dict(row),
    }


def _apply_detailed_information(
    invoice: dict[str, Any],
    details: dict[str, Any],
) -> None:
    """Tilføj oplysninger fra detailentiteten."""

    invoice["EAN"] = details.get(
        "OIOBuyerReferenceID"
    )

    invoice["Købers ordrenr"] = details.get(
        "OrderReferenceId"
    )

    invoice["RecIdLoc"] = details.get(
        "RecIdLoc"
    )

    invoice[
        "Importeret fakturabeløb"
    ] = details.get(
        "ImportedInvoiceAmount"
    )

    invoice["Momsbeløb"] = details.get(
        "ImportedTaxAmount"
    )

    invoice["raw_details"] = dict(
        details
    )


def _build_endpoint(
    entity: str,
    filters: list[str],
    top: int,
) -> str:
    """Byg et OData-endpoint."""

    endpoint = (
        f"{entity}?$top={top}"
    )

    clean_filters = []

    for filter_value in filters:
        clean_filter = str(
            filter_value
        ).strip()

        if clean_filter:
            clean_filters.append(
                clean_filter
            )

    if clean_filters:
        endpoint += (
            "&$filter="
            + " and ".join(clean_filters)
        )

    return endpoint


def _normalize_list_response(
    response: Any,
    operation_name: str,
) -> list[dict[str, Any]]:
    """Normalisér API-resultatet til en liste."""

    if response is None:
        return []

    if isinstance(response, dict):
        return [dict(response)]

    if not isinstance(response, list):
        raise TypeError(
            "API-klientens get-funktion skal "
            f"returnere en liste for {operation_name}, "
            "men returnerede "
            f"{type(response).__name__}."
        )

    rows = []

    for row in response:
        if isinstance(row, dict):
            rows.append(
                dict(row)
            )

    return rows


def _validate_afdeling(
    value: str,
) -> str:
    """Kontrollér et afdelingsnummer."""

    clean_value = _require_text(
        value,
        "afdeling",
    )

    if len(clean_value) != 12:
        raise ValueError(
            "afdeling skal være præcis "
            "12 cifre."
        )

    if not clean_value.isdigit():
        raise ValueError(
            "afdeling må kun indeholde cifre."
        )

    return clean_value


def _format_odata_datetime(
    value: date | datetime,
) -> str:
    """Formatér dato til OData DateTimeOffset."""

    if isinstance(value, datetime):
        date_value = value.date()
    elif isinstance(value, date):
        date_value = value
    else:
        raise TypeError(
            "oprettet_dato_start skal være "
            "en date- eller datetime-værdi."
        )

    return (
        date_value.isoformat()
        + "T00:00:00Z"
    )


def _validate_positive_integer(
    value: Any,
    variable_name: str,
) -> int:
    """Kontrollér et positivt heltal."""

    if isinstance(value, bool):
        raise TypeError(
            f"{variable_name} skal være "
            "et positivt heltal."
        )

    try:
        integer_value = int(value)
    except (TypeError, ValueError) as error:
        raise TypeError(
            f"{variable_name} skal være "
            "et positivt heltal."
        ) from error

    if integer_value <= 0:
        raise ValueError(
            f"{variable_name} skal være "
            "større end 0."
        )

    return integer_value


def _require_text(
    value: Any,
    variable_name: str,
) -> str:
    """Kontrollér obligatorisk tekst."""

    if value is None:
        raise ValueError(
            f"{variable_name} skal udfyldes."
        )

    text_value = str(value).strip()

    if not text_value:
        raise ValueError(
            f"{variable_name} må ikke være tom."
        )

    return text_value


def _clean_optional_text(
    value: Any,
) -> str | None:
    """Normalisér valgfri tekst."""

    if value is None:
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    return text_value


def _all_rows_have_line_number(
    rows: list[dict[str, Any]],
) -> bool:
    """Kontrollér om alle linjer har nummer."""

    if not rows:
        return False

    for row in rows:
        if row.get(
            "InvoiceLineNumber"
        ) is None:
            return False

    return True


def _line_sort_value(
    row: dict[str, Any],
) -> Decimal:
    """Byg numerisk sorteringsværdi."""

    return _to_decimal(
        row.get(
            "InvoiceLineNumber",
            "0",
        )
    )


def _to_decimal(
    value: Any,
) -> Decimal:
    """Konvertér beløb til Decimal."""

    if isinstance(value, Decimal):
        return value

    if isinstance(value, bool):
        raise InvalidOperation(
            "Bool kan ikke bruges som beløb."
        )

    text = str(
        value
        if value is not None
        else "0"
    ).strip()

    if not text:
        text = "0"

    text = text.replace(
        " ",
        "",
    )

    if "," in text and "." not in text:
        text = text.replace(
            ",",
            ".",
        )

    return Decimal(text)

# ------------------------------------------------------------
# OPDATER FAKTURABESKRIVELSE
# ------------------------------------------------------------

def update_faktura_beskrivelse(
    rec_id_loc: int,
    fakturabeskrivelse: str,
    verificer: bool = True,
) -> bool:
    """
    Opdatér fakturaens InvoiceDescription.

    Funktionen følger Blue Prism-handlingen:
        Faktura: Rediger og eller Godkend

    Endpoint:
        FUJ_VendorInvoiceHeaderEntity(<RecIdLoc>)

    Body:
        RecIdLoc
        InvoiceDescription

    Args:
        rec_id_loc:
            Fakturaens unikke RecIdLoc.

        fakturabeskrivelse:
            Den nye fakturabeskrivelse.

        verificer:
            Hvis True hentes fakturaen igen
            efter PATCH-kaldet, og den gemte
            beskrivelse kontrolleres.

    Returns:
        True når opdateringen lykkes.

    Raises:
        ValueError:
            Hvis input er ugyldigt, eller den
            gemte værdi ikke matcher.

        PrismeApiError:
            Hvis Prisme afviser PATCH-kaldet.
    """

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    description = _require_text(
        fakturabeskrivelse,
        "fakturabeskrivelse",
    )

    endpoint = (
        build_faktura_beskrivelse_endpoint(
            validated_rec_id
        )
    )

    body = build_faktura_beskrivelse_body(
        rec_id_loc=validated_rec_id,
        fakturabeskrivelse=description,
    )

    logger.info(
        "Opdaterer fakturabeskrivelse for "
        "RecIdLoc %s",
        validated_rec_id,
    )

    result = patch(
        endpoint,
        body,
    )

    if result is not True:
        raise RuntimeError(
            "PATCH-kaldet returnerede ikke True."
        )

    if not verificer:
        return True

    faktura = get_faktura(
        rec_id_loc=validated_rec_id
    )

    saved_description = str(
        faktura.get(
            "InvoiceDescription",
            "",
        )
        or ""
    )

    if saved_description != description:
        raise ValueError(
            "Fakturabeskrivelsen blev ikke "
            "verificeret efter opdateringen. "
            f"Forventet: {description!r}. "
            f"Fundet: {saved_description!r}."
        )

    logger.info(
        "Fakturabeskrivelsen blev verificeret "
        "for RecIdLoc %s",
        validated_rec_id,
    )

    return True


def build_faktura_beskrivelse_endpoint(
    rec_id_loc: int,
) -> str:
    """Byg endpoint til fakturabeskrivelsen."""

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    return (
        f"{FAKTURA_HEADER_ENDPOINT}"
        f"({validated_rec_id})"
    )


def build_faktura_beskrivelse_body(
    rec_id_loc: int,
    fakturabeskrivelse: str,
) -> dict[str, Any]:
    """Byg PATCH-body til fakturabeskrivelse."""

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    description = _require_text(
        fakturabeskrivelse,
        "fakturabeskrivelse",
    )

    return {
        "RecIdLoc": validated_rec_id,
        "InvoiceDescription": description,
    }


# ------------------------------------------------------------
# OPDATER BOGFØRINGSDATO
# ------------------------------------------------------------

def update_faktura_bogfoeringsdato(
    header_reference: str,
    bogfoeringsdato: date | datetime | str,
    data_area_id: str = DEFAULT_DATA_AREA_ID,
    verificer: bool = True,
) -> bool:
    """
    Opdatér fakturaens bogføringsdato.

    Funktionen følger Blue Prism-handlingen:
        Faktura: Rediger og eller Godkend

    Endpoint:
        VendorInvoiceHeaders(
            HeaderReference='<reference>',
            dataAreaId='had'
        )

    Body:
        HeaderReference
        Date

    Args:
        header_reference:
            Fakturaens interne reference.

        bogfoeringsdato:
            Ny bogføringsdato.

            Tilladte Python-værdier:
                date
                datetime
                tekst som DD-MM-YYYY
                tekst som YYYY-MM-DD

        data_area_id:
            Selskabskode. Standard er had.

        verificer:
            Hvis True hentes fakturaen igen,
            og datoen kontrolleres.

    Returns:
        True når opdateringen lykkes.
    """

    reference = _require_text(
        header_reference,
        "header_reference",
    )

    company = _require_text(
        data_area_id,
        "data_area_id",
    )

    validated_date = (
        _parse_bogfoeringsdato(
            bogfoeringsdato
        )
    )

    endpoint = (
        build_faktura_bogfoeringsdato_endpoint(
            header_reference=reference,
            data_area_id=company,
        )
    )

    body = build_faktura_bogfoeringsdato_body(
        header_reference=reference,
        bogfoeringsdato=validated_date,
    )

    logger.info(
        "Opdaterer bogføringsdato for "
        "HeaderReference %s til %s",
        reference,
        validated_date.isoformat(),
    )

    result = patch(
        endpoint,
        body,
    )

    if result is not True:
        raise RuntimeError(
            "PATCH-kaldet returnerede ikke True."
        )

    if not verificer:
        return True

    faktura = get_faktura_by_header_reference(
        header_reference=reference,
        data_area_id=company,
    )

    saved_date = _parse_optional_api_date(
        faktura.get("Date")
    )

    if saved_date != validated_date:
        raise ValueError(
            "Bogføringsdatoen blev ikke "
            "verificeret efter opdateringen. "
            "Forventet: "
            f"{validated_date.isoformat()}. "
            "Fundet: "
            f"{faktura.get('Date')!r}."
        )

    logger.info(
        "Bogføringsdatoen blev verificeret "
        "for HeaderReference %s",
        reference,
    )

    return True


def build_faktura_bogfoeringsdato_endpoint(
    header_reference: str,
    data_area_id: str = DEFAULT_DATA_AREA_ID,
) -> str:
    """Byg endpoint til bogføringsdato."""

    reference = _require_text(
        header_reference,
        "header_reference",
    )

    company = _require_text(
        data_area_id,
        "data_area_id",
    )

    escaped_reference = (
        _escape_odata_key_text(
            reference
        )
    )

    escaped_company = (
        _escape_odata_key_text(
            company
        )
    )

    return (
        f"{FAKTURA_LISTE_ENDPOINT}"
        f"(HeaderReference="
        f"'{escaped_reference}',"
        f"dataAreaId='{escaped_company}')"
    )


def build_faktura_bogfoeringsdato_body(
    header_reference: str,
    bogfoeringsdato: date | datetime | str,
) -> dict[str, Any]:
    """Byg PATCH-body til bogføringsdato."""

    reference = _require_text(
        header_reference,
        "header_reference",
    )

    validated_date = (
        _parse_bogfoeringsdato(
            bogfoeringsdato
        )
    )

    return {
        "HeaderReference": reference,
        "Date": _format_json_date(
            validated_date
        ),
    }


# ------------------------------------------------------------
# HJÆLPEFUNKTIONER TIL TRIN 3
# ------------------------------------------------------------

def _parse_bogfoeringsdato(
    value: date | datetime | str,
) -> date:
    """Fortolk bogføringsdato fra procesinput."""

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise TypeError(
            "bogfoeringsdato skal være en "
            "date-, datetime- eller tekstværdi."
        )

    text_value = value.strip()

    if not text_value:
        raise ValueError(
            "bogfoeringsdato skal udfyldes."
        )

    date_formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    )

    for date_format in date_formats:
        try:
            parsed_value = datetime.strptime(
                text_value,
                date_format,
            )

            return parsed_value.date()
        except ValueError:
            continue

    try:
        parsed_datetime = (
            datetime.fromisoformat(
                text_value.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

        return parsed_datetime.date()
    except ValueError as error:
        raise ValueError(
            "bogfoeringsdato skal eksempelvis "
            "skrives som 01-06-2024 eller "
            "2024-06-01."
        ) from error


def _format_json_date(
    value: date,
) -> str:
    """
    Formatér dato til D365 JSON-dato.

    Klokken 12 anvendes, fordi datoer fra
    de aktuelle Prisme-entiteter returneres
    i dette format.
    """

    return (
        value.isoformat()
        + "T12:00:00Z"
    )


def _parse_optional_api_date(
    value: Any,
) -> date | None:
    """Fortolk en dato fra Prismes svar."""

    if value in (
        None,
        "",
    ):
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text_value = str(
        value
    ).strip()

    try:
        parsed_value = datetime.fromisoformat(
            text_value.replace(
                "Z",
                "+00:00",
            )
        )

        return parsed_value.date()
    except ValueError:
        pass

    try:
        return date.fromisoformat(
            text_value[:10]
        )
    except ValueError:
        return None


def _escape_odata_key_text(
    value: str,
) -> str:
    """Escape tekst i en OData-nøgle."""

    return str(value).replace(
        "'",
        "''",
    )

# ------------------------------------------------------------
# WORKFLOWSTATUS
# ------------------------------------------------------------

def get_faktura_workflow_status(
    rec_id_loc: int,
) -> dict[str, Any]:
    """
    Hent relevante workflowoplysninger.

    Funktionen bruger fakturahovedet fra:
        FUJ_VendorInvoiceHeaderEntity

    Args:
        rec_id_loc:
            Fakturaens unikke RecIdLoc.

    Returns:
        En dictionary med de vigtigste
        workflowfelter og det rå API-svar.
    """

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    faktura = get_faktura(
        rec_id_loc=validated_rec_id
    )

    return {
        "RecIdLoc": validated_rec_id,
        "ApproverPersonnelNumber": (
            faktura.get(
                "ApproverPersonnelNumber"
            )
        ),
        "Approved": faktura.get(
            "Approved"
        ),
        "RequestStatus": faktura.get(
            "RequestStatus"
        ),
        "VendorInvoiceReviewStatus": (
            faktura.get(
                "VendorInvoiceReviewStatus"
            )
        ),
        "InvoiceDescription": faktura.get(
            "InvoiceDescription"
        ),
        "raw": faktura,
    }


# ------------------------------------------------------------
# FLYT ELLER DELEGÉR FAKTURA
# ------------------------------------------------------------

def delegate_faktura(
    rec_id_loc: int,
    til_bruger: str,
    godkender_2: str = "",
    konteringsperson: str = "",
    afdeling: str = "",
    kommentar: str = (
        "API flytning af faktura"
    ),
    verificer: bool = True,
) -> bool:
    """
    Flyt fakturaens workflow til en bruger.

    Funktionen følger Blue Prism-handlingen:
        delegateWFVendorInvoice

    Endpoint:
        FUJ_VendorInvoiceHeaderEntity(
            RecIdLoc=<id>
        )/Microsoft.Dynamics.DataEntities.
        delegateWFVendorInvoice

    Args:
        rec_id_loc:
            Fakturaens unikke RecIdLoc.

        til_bruger:
            D365-bruger-id på den nye
            godkender.

        godkender_2:
            Valgfri anden godkender.
            Feltet sendes altid.

        konteringsperson:
            Valgfri konteringsperson.
            Feltet sendes altid.

        afdeling:
            Valgfri ny afdeling.
            Feltet sendes altid.

        kommentar:
            Kommentar til flytningen.

        verificer:
            Hvis True hentes fakturaen igen,
            og ApproverPersonnelNumber
            kontrolleres.

    Returns:
        True når flytningen lykkes.
    """

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    clean_user = _require_text(
        til_bruger,
        "til_bruger",
    )

    endpoint = build_delegate_faktura_endpoint(
        rec_id_loc=validated_rec_id
    )

    body = build_delegate_faktura_body(
        rec_id_loc=validated_rec_id,
        til_bruger=clean_user,
        godkender_2=godkender_2,
        konteringsperson=konteringsperson,
        afdeling=afdeling,
        kommentar=kommentar,
    )

    logger.info(
        "Flytter faktura %s til bruger %s",
        validated_rec_id,
        clean_user,
    )

    result = post(
        endpoint,
        body,
    )

    _validate_workflow_response(
        result=result,
        operation_name="flytning af faktura",
        accepted_messages=[
            "Success",
            "Dokumentet er godkendt.",
        ],
    )

    if not verificer:
        return True

    faktura = get_faktura(
        rec_id_loc=validated_rec_id
    )

    actual_approver = str(
        faktura.get(
            "ApproverPersonnelNumber",
            "",
        )
        or ""
    ).strip()

    if (
        actual_approver.casefold()
        != clean_user.casefold()
    ):
        raise ValueError(
            "Fakturaens godkender blev ikke "
            "verificeret efter flytningen. "
            f"Forventet: {clean_user!r}. "
            f"Fundet: {actual_approver!r}."
        )

    logger.info(
        "Flytningen af faktura %s blev "
        "verificeret",
        validated_rec_id,
    )

    return True


def build_delegate_faktura_endpoint(
    rec_id_loc: int,
) -> str:
    """Byg endpoint til workflowflytning."""

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    return (
        f"{FAKTURA_HEADER_ENDPOINT}"
        f"(RecIdLoc={validated_rec_id})"
        "/Microsoft.Dynamics.DataEntities."
        "delegateWFVendorInvoice"
    )


def build_delegate_faktura_body(
    rec_id_loc: int,
    til_bruger: str,
    godkender_2: str = "",
    konteringsperson: str = "",
    afdeling: str = "",
    kommentar: str = (
        "API flytning af faktura"
    ),
) -> dict[str, Any]:
    """Byg body til workflowflytning."""

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    clean_user = _require_text(
        til_bruger,
        "til_bruger",
    )

    clean_approver_2 = _optional_text_or_empty(
        godkender_2
    )

    clean_accounting_person = (
        _optional_text_or_empty(
            konteringsperson
        )
    )

    clean_department = _optional_text_or_empty(
        afdeling
    )

    if clean_department:
        if (
            len(clean_department) != 12
            or not clean_department.isdigit()
        ):
            raise ValueError(
                "afdeling skal være blank eller "
                "bestå af præcis 12 cifre."
            )

    clean_comment = _optional_text_or_empty(
        kommentar
    )

    return {
        "_recid": validated_rec_id,
        "_toUserId": clean_user,
        "_approver2": clean_approver_2,
        "_invoiceAccounting": (
            clean_accounting_person
        ),
        "_department": clean_department,
        "_comment": clean_comment,
    }


# ------------------------------------------------------------
# GODKEND FAKTURA
# ------------------------------------------------------------

def approve_faktura(
    rec_id_loc: int,
    fakturabeloeb: Decimal,
    konteringslinjer_totalbeloeb: Decimal,
    godkender_1: str | None = None,
    godkender_2: str = "",
    konteringsperson: str = "",
    afdeling: str = "",
    tolerance: Decimal = Decimal("1.00"),
) -> bool:
    """
    Kontrollér og godkend én faktura.

    Processen skal beregne det samlede
    bruttobeløb fra konteringslinjerne,
    før funktionen kaldes.

    Hvis godkender_1 udfyldes, flyttes
    fakturaen først til denne bruger.

    Godkendelsen gennemføres kun, når:

    1. Beløbsforskellen er mindre end tolerance.
    2. En angivet godkender_1 starter med dirx.
    3. Fakturaens aktuelle godkender starter
       med dirx umiddelbart før godkendelsen.

    Godkendelseskommentaren kan ikke angives
    af processen. Funktionen bygger altid:

        Godkendt af robot: <godkender>

    Args:
        rec_id_loc:
            Fakturaens unikke RecIdLoc.

        fakturabeloeb:
            Fakturaens samlede beløb.

            Processen kan eksempelvis bruge
            ImportedInvoiceAmount.

        konteringslinjer_totalbeloeb:
            Summen af GrossAmount fra alle
            konteringslinjer.

            Processen skal beregne værdien,
            før funktionen kaldes.

        godkender_1:
            Valgfri D365-bruger, som fakturaen
            skal flyttes til før godkendelse.

            Hvis værdien udfyldes, skal
            bruger-id'et starte med dirx.

            Hvis værdien er None eller tom,
            flyttes fakturaen ikke.

        godkender_2:
            Valgfri anden godkender, som sendes
            ved flytning.

        konteringsperson:
            Valgfri konteringsperson, som sendes
            ved flytning.

        afdeling:
            Valgfri afdeling på 12 cifre, som
            sendes ved flytning.

        tolerance:
            Maksimal tilladt difference.

            Standard er 1.00.
            En difference på præcis 1.00 afvises.

    Returns:
        True når Prisme bekræfter godkendelsen.
    """

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    try:
        invoice_amount = _to_decimal(
            fakturabeloeb
        )
    except InvalidOperation as error:
        raise ValueError(
            "fakturabeloeb er ugyldigt: "
            f"{fakturabeloeb!r}."
        ) from error

    try:
        accounting_amount = _to_decimal(
            konteringslinjer_totalbeloeb
        )
    except InvalidOperation as error:
        raise ValueError(
            "konteringslinjer_totalbeloeb "
            "er ugyldigt: "
            f"{konteringslinjer_totalbeloeb!r}."
        ) from error

    try:
        validated_tolerance = _to_decimal(
            tolerance
        )
    except InvalidOperation as error:
        raise ValueError(
            "tolerance er ugyldig: "
            f"{tolerance!r}."
        ) from error

    if validated_tolerance <= Decimal("0"):
        raise ValueError(
            "tolerance skal være større end 0."
        )

    difference = abs(
        invoice_amount - accounting_amount
    )

    if difference >= validated_tolerance:
        raise ValueError(
            "Fakturaen kan ikke godkendes, "
            "fordi fakturabeløbet ikke matcher "
            "konteringslinjernes totalbeløb. "
            f"Fakturabeløb: {invoice_amount}. "
            "Konteringslinjernes totalbeløb: "
            f"{accounting_amount}. "
            f"Difference: {difference}. "
            "Differencen skal være mindre end "
            f"{validated_tolerance}."
        )

    clean_approver_1 = _optional_text_or_empty(
        godkender_1
    )

    if clean_approver_1:
        if not clean_approver_1.casefold().startswith(
            "dirx"
        ):
            raise ValueError(
                "Fakturaen kan ikke flyttes og "
                "godkendes, fordi godkender_1 "
                "ikke starter med dirx. "
                "Angivet godkender_1: "
                f"{clean_approver_1!r}."
            )

        flyttekommentar = (
            "Flyttet af robot før godkendelse"
        )

        logger.info(
            "Flytter faktura %s til %s "
            "før godkendelse",
            validated_rec_id,
            clean_approver_1,
        )

        delegate_faktura(
            rec_id_loc=validated_rec_id,
            til_bruger=clean_approver_1,
            godkender_2=godkender_2,
            konteringsperson=konteringsperson,
            afdeling=afdeling,
            kommentar=flyttekommentar,
            verificer=True,
        )

    faktura = get_faktura(
        rec_id_loc=validated_rec_id
    )

    current_approver = str(
        faktura.get(
            "ApproverPersonnelNumber",
            "",
        )
        or ""
    ).strip()

    if not current_approver:
        raise ValueError(
            "Fakturaen kan ikke godkendes, "
            "fordi ApproverPersonnelNumber "
            "er tom."
        )

    if not current_approver.casefold().startswith(
        "dirx"
    ):
        raise ValueError(
            "Fakturaen kan ikke godkendes, "
            "fordi den aktuelle godkender "
            "ikke starter med dirx. "
            "Aktuel godkender: "
            f"{current_approver!r}."
        )

    godkendelseskommentar = (
        "Godkendt af robot: "
        + current_approver
    )

    endpoint = build_approve_faktura_endpoint(
        rec_id_loc=validated_rec_id
    )

    body = build_approve_faktura_body(
        rec_id_loc=validated_rec_id,
        kommentar=godkendelseskommentar,
    )

    logger.info(
        "Godkender faktura %s. "
        "Godkender: %s. "
        "Fakturabeløb: %s. "
        "Konteringslinjernes totalbeløb: %s. "
        "Difference: %s",
        validated_rec_id,
        current_approver,
        invoice_amount,
        accounting_amount,
        difference,
    )

    result = post(
        endpoint,
        body,
    )

    _validate_workflow_response(
        result=result,
        operation_name=(
            "godkendelse af faktura"
        ),
        accepted_messages=[
            "Success",
            "Dokumentet er godkendt.",
            (
                "Dokumentet er allerede "
                "godkendt."
            ),
        ],
    )

    logger.info(
        "Prisme bekræftede godkendelsen "
        "af faktura %s",
        validated_rec_id,
    )

    return True


def build_approve_faktura_endpoint(
    rec_id_loc: int,
) -> str:
    """Byg endpoint til fakturagodkendelse."""

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    return (
        f"{FAKTURA_HEADER_ENDPOINT}"
        f"(RecIdLoc={validated_rec_id})"
        "/Microsoft.Dynamics.DataEntities."
        "autoApproveWFVendorInvoice"
    )


def build_approve_faktura_body(
    rec_id_loc: int,
    kommentar: str = (
        "Godkendt af robot via API"
    ),
) -> dict[str, Any]:
    """Byg body til fakturagodkendelse."""

    validated_rec_id = (
        _validate_positive_integer(
            rec_id_loc,
            "rec_id_loc",
        )
    )

    clean_comment = _optional_text_or_empty(
        kommentar
    )

    return {
        "_recid": validated_rec_id,
        "_comment": clean_comment,
    }


# ------------------------------------------------------------
# FÆLLES WORKFLOW-HJÆLP
# ------------------------------------------------------------

def _validate_workflow_response(
    result: Any,
    operation_name: str,
    accepted_messages: list[str],
) -> None:
    """
    Kontrollér svaret fra en workflowhandling.

    api_client.post kan returnere:
        True
        tekst
        dictionary
        liste
    """

    if result is True:
        return

    response_value = _extract_workflow_value(
        result
    )

    normalized_response = str(
        response_value
        if response_value is not None
        else ""
    ).strip().casefold()

    normalized_messages = []

    for message in accepted_messages:
        normalized_messages.append(
            str(message).strip().casefold()
        )

    if normalized_response in normalized_messages:
        return

    raise RuntimeError(
        "Prisme bekræftede ikke "
        f"{operation_name}. "
        f"Svar: {result!r}"
    )


def _extract_workflow_value(
    result: Any,
) -> Any:
    """Udtræk værdien fra workflowsvaret."""

    if isinstance(result, dict):
        if "value" in result:
            return result["value"]

        return result

    if isinstance(result, list):
        if len(result) == 1:
            first_value = result[0]

            if isinstance(first_value, dict):
                if "value" in first_value:
                    return first_value["value"]

            return first_value

        return result

    return result


def _optional_text_or_empty(
    value: Any,
) -> str:
    """Normalisér valgfri tekst."""

    if value is None:
        return ""

    return str(value).strip()