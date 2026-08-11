"""Søgning efter dokumenter og notater i Prisme 365."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import PureWindowsPath
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

from q_prisme365_api.api_client import get
from q_prisme365_api.odata import (
    eq_date,
    eq_number,
    eq_text,
)


logger = logging.getLogger(__name__)


DOCUMENT_REFERENCE_ENDPOINT = "DocuRefDatasEntity_FUJ"
DOCUMENT_VALUE_ENDPOINT = "DocuValueDatasEntity_FUJ"

DEFAULT_COMPANY_ID = "had"
DEFAULT_TOP = 1000


TABLE_IDS = {
    "cpr_cvr": 27526,
    "ventende_kreditorfaktura": 6084,
}


@dataclass(frozen=True)
class Dokumentinformation:
    """Oplysninger om en fysisk dokumentfil."""

    value_rec_id: int
    original_file_name: str
    access_information_raw: str
    document_path: str | None
    raw: dict[str, Any]


def search_dokumenter(
    ref_rec_id: int | None = None,
    document_id: str | None = None,
    tabel: str | None = None,
    cpr_cvr: str | None = None,
    dokumentnavn: str | None = None,
    dokumenttype: str | None = None,
    oprettet_af: str | None = None,
    notat_tekst: str | None = None,
    oprettet_dato: date | None = None,
    hent_dokumentplacering: bool = False,
    domain_suffix: str | None = None,
    top: int = DEFAULT_TOP,
) -> list[dict[str, Any]]:
    """
    Søg efter dokumentreferencer og notater.

    Funktionen (genbrugelig kodeblok) kalder:
        DocuRefDatasEntity_FUJ

    Args:
        ref_rec_id:
            Id på posten, som dokumentet
            er tilknyttet.

        document_id:
            Dokumentets UUID.

        tabel:
            Tilladte værdier:
            cpr_cvr
            ventende_kreditorfaktura
            None

        cpr_cvr:
            CPR- eller CVR-værdi.

        dokumentnavn:
            Dokumentets navn.

        dokumenttype:
            Dokumentets TypeId.

        oprettet_af:
            Brugeren fra OriginallyCreatedBy.

        notat_tekst:
            Teksten fra Notes.

        oprettet_dato:
            Datoen fra CreatedOn.

        hent_dokumentplacering:
            True henter filnavn og placering
            for fysiske dokumenter.

        domain_suffix:
            Valgfrit domæne til UNC-stien.

            Eksempel:
                prisme-365.dk

        top:
            Maksimalt antal dokumentreferencer.

    Returns:
        En liste med dokumentreferencer.
    """

    validated_top = _validate_positive_integer(
        top,
        "top",
    )

    validated_table = _validate_table(
        tabel
    )

    filters = [
        eq_text(
            "RefCompanyId",
            DEFAULT_COMPANY_ID,
        )
    ]

    if validated_table is not None:
        table_id = TABLE_IDS[
            validated_table
        ]

        filters.append(
            eq_number(
                "RefTableId",
                table_id,
            )
        )

    if ref_rec_id is not None:
        validated_ref_rec_id = (
            _validate_positive_integer(
                ref_rec_id,
                "ref_rec_id",
            )
        )

        filters.append(
            eq_number(
                "RefRecId",
                validated_ref_rec_id,
            )
        )

    clean_document_id = _clean_optional_text(
        document_id
    )

    if clean_document_id is not None:
        filters.append(
            eq_text(
                "DocumentId",
                clean_document_id,
            )
        )

    clean_cpr_cvr = _clean_optional_text(
        cpr_cvr
    )

    if clean_cpr_cvr is not None:
        filters.append(
            eq_text(
                "LegalEntity",
                clean_cpr_cvr,
            )
        )

    clean_document_name = _clean_optional_text(
        dokumentnavn
    )

    if clean_document_name is not None:
        filters.append(
            eq_text(
                "Name",
                clean_document_name,
            )
        )

    clean_document_type = _clean_optional_text(
        dokumenttype
    )

    if clean_document_type is not None:
        filters.append(
            eq_text(
                "TypeId",
                clean_document_type,
            )
        )

    clean_created_by = _clean_optional_text(
        oprettet_af
    )

    if clean_created_by is not None:
        filters.append(
            eq_text(
                "OriginallyCreatedBy",
                clean_created_by,
            )
        )

    clean_note_text = _clean_optional_text(
        notat_tekst,
        strip_value=False,
    )

    if clean_note_text is not None:
        filters.append(
            eq_text(
                "Notes",
                clean_note_text,
            )
        )

    if oprettet_dato is not None:
        validated_created_date = _validate_date(
            oprettet_dato,
            "oprettet_dato",
        )

        filters.append(
            eq_date(
                "CreatedOn",
                validated_created_date,
            )
        )

    endpoint = build_dokument_search_endpoint(
        filters=filters,
        top=validated_top,
    )

    logger.info(
        "Søger efter dokumenter"
    )

    logger.debug(
        "Dokumentsøgning endpoint: %s",
        endpoint,
    )

    response = get(endpoint)

    rows = _normalize_list_response(
        response,
        "dokumentsøgningen",
    )

    if not hent_dokumentplacering:
        logger.info(
            "Dokumentsøgningen returnerede "
            "%s dokumenter",
            len(rows),
        )

        return rows

    enriched_rows = []

    for row in rows:
        enriched_row = dict(row)

        value_rec_id = row.get(
            "ValueRecId"
        )

        if _has_physical_document(
            value_rec_id
        ):
            information = get_dokumentinformation(
                value_rec_id=int(
                    value_rec_id
                ),
                domain_suffix=domain_suffix,
            )

            enriched_row["Dokumentnavn"] = (
                information.original_file_name
            )

            enriched_row[
                "AccessInformationRaw"
            ] = information.access_information_raw

            enriched_row["Dokumentsti"] = (
                information.document_path
            )

        enriched_rows.append(
            enriched_row
        )

    logger.info(
        "Dokumentsøgningen returnerede "
        "%s dokumenter med filoplysninger",
        len(enriched_rows),
    )

    return enriched_rows


def build_dokument_search_endpoint(
    filters: list[str],
    top: int = DEFAULT_TOP,
) -> str:
    """
    Byg endpointet til dokumentsøgning.

    Funktionen (genbrugelig kodeblok)
    foretager ikke et API-kald.
    """

    validated_top = _validate_positive_integer(
        top,
        "top",
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

    endpoint = (
        f"{DOCUMENT_REFERENCE_ENDPOINT}"
        f"?$top={validated_top}"
    )

    if clean_filters:
        filter_expression = " and ".join(
            clean_filters
        )

        endpoint = (
            endpoint
            + "&$filter="
            + filter_expression
        )

    return endpoint


def get_dokumentinformation(
    value_rec_id: int,
    domain_suffix: str | None = None,
) -> Dokumentinformation:
    """
    Hent filnavn og placering via ValueRecId.

    Funktionen (genbrugelig kodeblok) kalder:
        DocuValueDatasEntity_FUJ
    """

    validated_value_rec_id = (
        _validate_positive_integer(
            value_rec_id,
            "value_rec_id",
        )
    )

    endpoint = (
        f"{DOCUMENT_VALUE_ENDPOINT}"
        f"({validated_value_rec_id})"
    )

    logger.info(
        "Henter dokumentinformation for "
        "ValueRecId %s",
        validated_value_rec_id,
    )

    response = get(endpoint)

    rows = _normalize_single_response(
        response
    )

    if not rows:
        raise ValueError(
            "Dokumentinformation blev ikke "
            "fundet for ValueRecId "
            f"{validated_value_rec_id}."
        )

    if len(rows) != 1:
        raise ValueError(
            "Dokumentinformationen var ikke "
            "entydig for ValueRecId "
            f"{validated_value_rec_id}. "
            f"Antal rækker: {len(rows)}."
        )

    row = rows[0]

    access_information = str(
        row.get(
            "AccessInformation",
            "",
        )
        or ""
    ).strip()

    original_file_name = str(
        row.get(
            "OriginalFileName",
            "",
        )
        or ""
    ).strip()

    document_path = normalize_document_path(
        access_information=access_information,
        domain_suffix=domain_suffix,
    )

    return Dokumentinformation(
        value_rec_id=validated_value_rec_id,
        original_file_name=(
            original_file_name
        ),
        access_information_raw=(
            access_information
        ),
        document_path=document_path,
        raw=dict(row),
    )


def normalize_document_path(
    access_information: str,
    domain_suffix: str | None = None,
) -> str | None:
    """
    Konvertér en file-URI til en UNC-sti.

    Eksempel på input:
        file://SERVER/aos-storage/documents/test.pdf

    Eksempel på output:
        \\\\SERVER.prisme-365.dk\\
        aos-storage\\documents\\test.pdf

    Hvis værdien ikke kan fortolkes sikkert,
    returneres None.
    """

    value = str(
        access_information
        or ""
    ).strip()

    if not value:
        return None

    if value.startswith("\\\\"):
        return str(
            PureWindowsPath(value)
        )

    parsed = urlparse(
        value
    )

    if parsed.scheme.casefold() != "file":
        return None

    host = parsed.netloc.strip()

    if not host:
        return None

    clean_domain_suffix = _clean_optional_text(
        domain_suffix
    )

    if (
        clean_domain_suffix is not None
        and "." not in host
    ):
        clean_domain_suffix = (
            clean_domain_suffix.lstrip(".")
        )

        host = (
            f"{host}.{clean_domain_suffix}"
        )

    path_parts = []

    for part in parsed.path.split("/"):
        if not part:
            continue

        decoded_part = unquote(
            part
        )

        path_parts.append(
            decoded_part
        )

    if not path_parts:
        return f"\\\\{host}"

    windows_path = "\\".join(
        path_parts
    )

    return (
        "\\\\"
        + host
        + "\\"
        + windows_path
    )


def _normalize_list_response(
    response: Any,
    operation_name: str,
) -> list[dict[str, Any]]:
    """
    Kontrollér et API-svar, der skal være en liste.

    api_client.get returnerer OData value
    som en liste.
    """

    if response is None:
        return []

    if not isinstance(response, list):
        raise TypeError(
            "API-klientens get-funktion skal "
            f"returnere en liste for {operation_name}, "
            "men returnerede "
            f"{type(response).__name__}."
        )

    rows = []

    for row in response:
        if not isinstance(row, dict):
            logger.warning(
                "Springer en række over, fordi "
                "rækken ikke er en dictionary"
            )
            continue

        rows.append(
            dict(row)
        )

    return rows


def _normalize_single_response(
    response: Any,
) -> list[dict[str, Any]]:
    """
    Normalisér et direkte nøgleopslag.

    api_client.get kan returnere:
    en liste ved OData value
    en dictionary ved direkte nøgleopslag
    """

    if response is None:
        return []

    if isinstance(response, dict):
        return [
            dict(response)
        ]

    if isinstance(response, list):
        rows = []

        for row in response:
            if isinstance(row, dict):
                rows.append(
                    dict(row)
                )

        return rows

    raise TypeError(
        "Dokumentinformationen skal være "
        "en liste eller dictionary, men var "
        f"{type(response).__name__}."
    )


def _has_physical_document(
    value_rec_id: Any,
) -> bool:
    """Kontrollér om rækken har en fysisk fil."""

    if value_rec_id in (
        None,
        "",
        0,
        "0",
    ):
        return False

    try:
        numeric_value = int(
            value_rec_id
        )
    except (TypeError, ValueError):
        return False

    return numeric_value > 0


def _validate_table(
    table_name: str | None,
) -> str | None:
    """Kontrollér dokumenttabellens navn."""

    if table_name is None:
        return None

    clean_table_name = str(
        table_name
    ).strip().casefold()

    if not clean_table_name:
        return None

    if clean_table_name not in TABLE_IDS:
        allowed_values = ", ".join(
            TABLE_IDS.keys()
        )

        raise ValueError(
            "Ukendt dokumenttabel. "
            "Tilladte værdier er: "
            f"{allowed_values}."
        )

    return clean_table_name


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
        integer_value = int(
            value
        )
    except (TypeError, ValueError) as error:
        raise TypeError(
            f"{variable_name} skal kunne "
            "konverteres til et heltal."
        ) from error

    if integer_value <= 0:
        raise ValueError(
            f"{variable_name} skal være "
            "større end 0."
        )

    return integer_value


def _validate_date(
    value: Any,
    variable_name: str,
) -> date:
    """Kontrollér en datoværdi."""

    if not isinstance(value, date):
        raise TypeError(
            f"{variable_name} skal være "
            "en date-værdi."
        )

    return value


def _clean_optional_text(
    value: Any,
    strip_value: bool = True,
) -> str | None:
    """Normalisér en valgfri tekstværdi."""

    if value is None:
        return None

    text_value = str(
        value
    )

    if strip_value:
        text_value = text_value.strip()

    if not text_value:
        return None

    return text_value