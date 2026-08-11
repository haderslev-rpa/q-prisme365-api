"""Søgning efter bogførte finansposteringer i Prisme 365."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from decimal import InvalidOperation
from typing import Any

from q_prisme365_api.api_client import get
from q_prisme365_api.odata import (
    eq_text,
    ge_date,
    le_date,
    or_equals_text,
)


logger = logging.getLogger(__name__)


FINANSPOSTERINGER_ENDPOINT = (
    "GeneralJournalAccountEntrys_FUJ"
)

DEFAULT_POSTING_TYPES = (
    "PurchExpense",
    "LedgerJournal",
    "CustRevenue",
)

DEFAULT_TOP = 5000


def search_finansposteringer(
    dato_fra: date,
    dato_til: date,
    kontostreng: str | None = None,
    beskrivelse: str | None = None,
    ydelsesmodtager: str | None = None,
    posteringstyper: Sequence[str] | None = (
        DEFAULT_POSTING_TYPES
    ),
    filter_posting_types_locally: bool = True,
    top: int = DEFAULT_TOP,
) -> list[dict[str, Any]]:
    """
    Søg efter finansposteringer i Prisme 365.

    Funktionen svarer til Blue Prism-actionen:
        Finans: Posteringer: Søg

    Funktionen kalder:
        GeneralJournalAccountEntrys_FUJ

    Args:
        dato_fra:
            Første bogføringsdato.
            Datoen er inklusive.

        dato_til:
            Sidste bogføringsdato.
            Datoen er inklusive.

        kontostreng:
            Valgfri fuld kontostreng.

            Eksempel:
            100401030100-645521999-10110-29-

        beskrivelse:
            Valgfri tekst fra feltet Text.

            Søgningen bruger præcis lighed.
            En værdi som "test" finder derfor
            kun poster, hvor Text er præcis
            lig med "test".

        ydelsesmodtager:
            Valgfri værdi fra Beneficiary.

        posteringstyper:
            De PostingType-værdier, som skal
            returneres.

            Standard:
            PurchExpense
            LedgerJournal
            CustRevenue

            Brug None for at returnere alle
            posteringstyper.

        filter_posting_types_locally:
            True betyder, at PostingType først
            filtreres efter API-kaldet.

            Dette svarer til Blue Prism-flowet
            og er standard.

            False betyder, at PostingType
            tilføjes til OData-filteret.

        top:
            Maksimalt antal rækker, som Prisme
            anmodes om.

    Returns:
        En liste med finansposteringer.

        TransactionCurrencyAmount konverteres
        til Decimal, når feltet er udfyldt.

    Raises:
        TypeError:
            Hvis datoerne ikke er date-værdier,
            top er ugyldigt, eller inputtypen
            er forkert.

        ValueError:
            Hvis dato_fra er efter dato_til,
            eller top ikke er positivt.

        PrismeApiError:
            Hvis Prisme returnerer en API-fejl.
    """

    validated_date_from = _validate_date(
        dato_fra,
        "dato_fra",
    )

    validated_date_to = _validate_date(
        dato_til,
        "dato_til",
    )

    if validated_date_from > validated_date_to:
        raise ValueError(
            "dato_fra må ikke være efter dato_til."
        )

    validated_top = _validate_top(top)

    validated_posting_types = (
        _validate_posting_types(
            posteringstyper
        )
    )

    endpoint = build_finansposteringer_endpoint(
        dato_fra=validated_date_from,
        dato_til=validated_date_to,
        kontostreng=kontostreng,
        beskrivelse=beskrivelse,
        ydelsesmodtager=ydelsesmodtager,
        posteringstyper=(
            validated_posting_types
        ),
        filter_posting_types_locally=(
            filter_posting_types_locally
        ),
        top=validated_top,
    )

    logger.info(
        "Henter finansposteringer fra %s",
        FINANSPOSTERINGER_ENDPOINT,
    )

    logger.debug(
        "Finansposteringer endpoint: %s",
        endpoint,
    )

    response = get(endpoint)

    if response is None:
        logger.info(
            "Finanssøgningen returnerede "
            "ingen data"
        )

        return []

    if not isinstance(response, list):
        raise TypeError(
            "API-klientens get-funktion skal "
            "returnere en liste for "
            "finansposteringer, men returnerede "
            f"{type(response).__name__}."
        )

    rows = response

    if (
        validated_posting_types is not None
        and filter_posting_types_locally
    ):
        rows = _filter_posting_types(
            rows,
            validated_posting_types,
        )

    mapped_rows = []

    for row in rows:
        if not isinstance(row, dict):
            logger.warning(
                "Springer en finanspostering over, "
                "fordi rækken ikke er en dictionary"
            )
            continue

        mapped_row = _map_finanspostering(
            row
        )

        mapped_rows.append(
            mapped_row
        )

    logger.info(
        "Finanssøgningen returnerede "
        "%s posteringer efter filtrering",
        len(mapped_rows),
    )

    return mapped_rows


def build_finansposteringer_endpoint(
    dato_fra: date,
    dato_til: date,
    kontostreng: str | None = None,
    beskrivelse: str | None = None,
    ydelsesmodtager: str | None = None,
    posteringstyper: Sequence[str] | None = (
        DEFAULT_POSTING_TYPES
    ),
    filter_posting_types_locally: bool = True,
    top: int = DEFAULT_TOP,
) -> str:
    """
    Byg endpointet til finansposteringer.

    Funktionen foretager ikke et API-kald.
    Funktionen bygger kun den relative adresse.

    Args:
        dato_fra:
            Første bogføringsdato.

        dato_til:
            Sidste bogføringsdato.

        kontostreng:
            Valgfri fuld kontostreng.

        beskrivelse:
            Valgfri beskrivelse.

        ydelsesmodtager:
            Valgfri ydelsesmodtager.

        posteringstyper:
            Valgfrie PostingType-værdier.

        filter_posting_types_locally:
            Hvis True tilføjes typerne ikke
            til API-filteret.

        top:
            Maksimalt antal rækker.

    Returns:
        Relativt endpoint til api_client.get.
    """

    validated_date_from = _validate_date(
        dato_fra,
        "dato_fra",
    )

    validated_date_to = _validate_date(
        dato_til,
        "dato_til",
    )

    if validated_date_from > validated_date_to:
        raise ValueError(
            "dato_fra må ikke være efter dato_til."
        )

    validated_top = _validate_top(top)

    validated_posting_types = (
        _validate_posting_types(
            posteringstyper
        )
    )

    filters = [
        eq_text(
            "LedgerName",
            "HAD",
        ),
        ge_date(
            "AccountingDate",
            validated_date_from,
        ),
        le_date(
            "AccountingDate",
            validated_date_to,
        ),
    ]

    clean_account = _clean_optional_text(
        kontostreng
    )

    if clean_account is not None:
        filters.append(
            eq_text(
                "LedgerAccount",
                clean_account,
            )
        )

    clean_description = _clean_optional_text(
        beskrivelse
    )

    if clean_description is not None:
        filters.append(
            eq_text(
                "Text",
                clean_description,
            )
        )

    clean_beneficiary = _clean_optional_text(
        ydelsesmodtager
    )

    if clean_beneficiary is not None:
        filters.append(
            eq_text(
                "Beneficiary",
                clean_beneficiary,
            )
        )

    use_server_posting_type_filter = (
        validated_posting_types is not None
        and not filter_posting_types_locally
    )

    if use_server_posting_type_filter:
        posting_type_filter = (
            or_equals_text(
                "PostingType",
                validated_posting_types,
            )
        )

        if posting_type_filter:
            filters.append(
                posting_type_filter
            )

    filter_expression = " and ".join(
        filters
    )

    endpoint = (
        f"{FINANSPOSTERINGER_ENDPOINT}"
        f"?$top={validated_top}"
        f"&$filter={filter_expression}"
    )

    return endpoint


def _filter_posting_types(
    rows: list[dict[str, Any]],
    posteringstyper: Sequence[str],
) -> list[dict[str, Any]]:
    """
    Filtrér posteringstyper lokalt.

    Sammenligningen skelner ikke mellem
    store og små bogstaver.
    """

    allowed_types = set()

    for posting_type in posteringstyper:
        normalized_type = str(
            posting_type
        ).strip().casefold()

        if normalized_type:
            allowed_types.add(
                normalized_type
            )

    filtered_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        row_posting_type = str(
            row.get(
                "PostingType",
                "",
            )
            or ""
        ).strip().casefold()

        if row_posting_type in allowed_types:
            filtered_rows.append(
                row
            )

    return filtered_rows


def _map_finanspostering(
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalisér én finanspostering.

    Den oprindelige dictionary kopieres,
    så API-resultatet ikke ændres direkte.
    """

    mapped_row = dict(row)

    amount = row.get(
        "TransactionCurrencyAmount"
    )

    if amount in (None, ""):
        return mapped_row

    try:
        decimal_amount = _to_decimal(
            amount
        )
    except InvalidOperation as error:
        raise ValueError(
            "Ugyldigt "
            "TransactionCurrencyAmount: "
            f"{amount}"
        ) from error

    mapped_row[
        "TransactionCurrencyAmount"
    ] = decimal_amount

    return mapped_row


def _to_decimal(
    value: Any,
) -> Decimal:
    """
    Konvertér et beløb til Decimal.

    Funktionen understøtter:
    100.50
    100,50
    1.234,56
    1,234.56
    """

    if isinstance(value, Decimal):
        return value

    if isinstance(value, bool):
        raise InvalidOperation(
            "Bool kan ikke bruges som beløb."
        )

    text = str(value).strip()

    if not text:
        raise InvalidOperation(
            "Beløbet er tomt."
        )

    text = text.replace(
        " ",
        "",
    )

    contains_comma = "," in text
    contains_dot = "." in text

    if contains_comma and contains_dot:
        last_comma = text.rfind(",")
        last_dot = text.rfind(".")

        if last_comma > last_dot:
            text = text.replace(
                ".",
                "",
            )
            text = text.replace(
                ",",
                ".",
            )
        else:
            text = text.replace(
                ",",
                "",
            )
    elif contains_comma:
        text = text.replace(
            ",",
            ".",
        )

    return Decimal(text)


def _validate_date(
    value: date,
    variable_name: str,
) -> date:
    """Kontrollér en obligatorisk dato."""

    if not isinstance(value, date):
        raise TypeError(
            f"{variable_name} skal være "
            "en date-værdi."
        )

    return value


def _validate_top(
    top: int,
) -> int:
    """Kontrollér maksimalt antal rækker."""

    if isinstance(top, bool):
        raise TypeError(
            "top skal være et positivt heltal."
        )

    try:
        top_value = int(top)
    except (TypeError, ValueError) as error:
        raise TypeError(
            "top skal være et positivt heltal."
        ) from error

    if top_value <= 0:
        raise ValueError(
            "top skal være større end 0."
        )

    return top_value


def _validate_posting_types(
    posteringstyper: Sequence[str] | None,
) -> tuple[str, ...] | None:
    """
    Kontrollér og normalisér posteringstyper.

    None betyder, at alle typer accepteres.
    """

    if posteringstyper is None:
        return None

    if isinstance(
        posteringstyper,
        str,
    ):
        raise TypeError(
            "posteringstyper skal være en "
            "liste eller tuple med tekstværdier, "
            "ikke én enkelt tekstværdi."
        )

    cleaned_types = []

    for posting_type in posteringstyper:
        clean_type = _clean_optional_text(
            posting_type
        )

        if clean_type is None:
            continue

        if clean_type not in cleaned_types:
            cleaned_types.append(
                clean_type
            )

    return tuple(
        cleaned_types
    )


def _clean_optional_text(
    value: Any,
) -> str | None:
    """Normalisér en valgfri tekstværdi."""

    if value is None:
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    return text_value