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



__all__ = [
    "Dokumentinformation",
    "search_dokumenter",
    "get_dokumentinformation",
    "normalize_document_path",
]


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------

DOCUMENT_REFERENCE_ENDPOINT = (
    "DocuRefDatasEntity_FUJ"
)

DOCUMENT_VALUE_ENDPOINT = (
    "DocuValueDatasEntity_FUJ"
)


# ------------------------------------------------------------
# STANDARDVÆRDIER
# ------------------------------------------------------------

DEFAULT_COMPANY_ID = "had"

DEFAULT_TOP = 1000


# ------------------------------------------------------------
# PRISME-TABELLER
# ------------------------------------------------------------

TABLE_IDS = {
    "cpr_cvr": 27526,
    "ventende_kreditorfaktura": 6084,
}


# ------------------------------------------------------------
# DOKUMENTPLACERINGSSTATUS
# ------------------------------------------------------------

DOCUMENT_LOCATION_FETCHED = "hentet"

DOCUMENT_LOCATION_NOT_FETCHED = (
    "ikke_hentet"
)

DOCUMENT_LOCATION_NOT_RELEVANT = (
    "ikke_relevant"
)

DOCUMENT_LOCATION_MISSING = "mangler"


# ------------------------------------------------------------
# DATAMODEL
# ------------------------------------------------------------

@dataclass(frozen=True)
class Dokumentinformation:
    """Oplysninger om en fysisk dokumentfil."""

    value_rec_id: int
    original_file_name: str
    access_information_raw: str
    document_path: str | None
    file_id: str
    raw: dict[str, Any]


# ------------------------------------------------------------
# SØG DOKUMENTER
# ------------------------------------------------------------

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
    inkluder_raw: bool = False,
    top: int = DEFAULT_TOP,
) -> list[dict[str, Any]]:
    """
    Søg og returnér normaliserede dokumenter.

    Funktionen henter dokumentreferencer fra:

        DocuRefDatasEntity_FUJ

    Når hent_dokumentplacering=True og
    dokumentet har et positivt ValueRecId,
    hentes filoplysninger også fra:

        DocuValueDatasEntity_FUJ

    Alle dokumenter returneres med samme
    offentlige struktur:

        DocumentId
        DokumentReferenceRecId
        ReferenceRecId
        ValueRecId
        FilId
        RefTableId
        TypeId
        Dokumentnavn
        Dokumentsti
        AccessInformationRaw
        ErFysiskFil
        ErNotat
        DokumentplaceringStatus
        Notat
        OprettetDato
        OprettetAf
        OriginallyCreatedBy
        ModifiedDateTimeLoc
        ModifiedByLoc
        LegalEntity

    Dokumentsti er den eneste offentlige
    nøgle til dokumentets færdige UNC-sti.

    DokumentplaceringStatus kan være:

        hentet:
            Dokumentet er en fysisk fil,
            og Dokumentsti blev hentet.

        ikke_hentet:
            Dokumentet er en fysisk fil,
            men hent_dokumentplacering=False.

        ikke_relevant:
            Elementet har ingen fysisk fil,
            eksempelvis et notat.

        mangler:
            Elementet har et ValueRecId,
            men Prisme returnerede ikke en
            anvendelig dokumentsti.

    Når inkluder_raw=True, tilføjes feltet:

        raw

    raw indeholder:

        reference:
            Den rå dokumentreference fra
            DocuRefDatasEntity_FUJ.

        value:
            Den rå filinformation fra
            DocuValueDatasEntity_FUJ.

            Værdien er None, hvis der ikke er
            en fysisk fil, eller hvis
            dokumentplaceringen ikke blev
            hentet.

    Understøttede tabeller:

        ventende_kreditorfaktura:
            RefTableId 6084.

        cpr_cvr:
            RefTableId 27526.

    Typiske kald:

        Ventende kreditorfaktura:

            search_dokumenter(
                ref_rec_id=faktura_rec_id,
                tabel="ventende_kreditorfaktura",
                hent_dokumentplacering=True,
                domain_suffix="prisme-365.dk",
            )

        CPR/CVR:

            search_dokumenter(
                tabel="cpr_cvr",
                cpr_cvr="29189757",
                hent_dokumentplacering=True,
                domain_suffix="prisme-365.dk",
            )

    Args:
        ref_rec_id:
            Id på posten, dokumentet er
            knyttet til.

            For ventende kreditorfaktura er
            dette fakturaens RecIdLoc.

        document_id:
            Dokumentets UUID fra DocumentId.

        tabel:
            Tilladte værdier:

                cpr_cvr
                ventende_kreditorfaktura
                None

        cpr_cvr:
            CPR- eller CVR-værdi fra
            LegalEntity.

        dokumentnavn:
            Dokumentets navn fra Name.

        dokumenttype:
            Dokumenttypen fra TypeId.

            Eksempler:

                OIOUBL
                Notat

        oprettet_af:
            Brugeren fra OriginallyCreatedBy.

        notat_tekst:
            Den præcise tekst fra Notes.

        oprettet_dato:
            Datoen fra CreatedOn.

        hent_dokumentplacering:
            True henter filnavn og filplacering
            for fysiske dokumenter.

            False returnerer stadig dokumentet,
            men Dokumentsti bliver None.

        domain_suffix:
            Valgfrit domæne, der tilføjes til
            servernavnet i UNC-stien.

            Eksempel:

                prisme-365.dk

        inkluder_raw:
            False er standard og returnerer
            kun de normaliserede felter.

            True tilføjer de rå Prisme-data
            under feltet raw.

        top:
            Maksimalt antal dokumenter.

    Returns:
        En liste med normaliserede dokumenter.
    """

    validated_top = _validate_positive_integer(
        top,
        "top",
    )

    if not isinstance(
        hent_dokumentplacering,
        bool,
    ):
        raise TypeError(
            "hent_dokumentplacering skal være "
            "True eller False."
        )

    if not isinstance(
        inkluder_raw,
        bool,
    ):
        raise TypeError(
            "inkluder_raw skal være "
            "True eller False."
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
        validated_created_date = (
            _validate_date(
                oprettet_dato,
                "oprettet_dato",
            )
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

    response = get(
        endpoint
    )

    reference_rows = _normalize_list_response(
        response=response,
        operation_name="dokumentsøgningen",
    )

    normalized_documents: list[
        dict[str, Any]
    ] = []

    for reference_row in reference_rows:
        normalized_document = (
            _normalize_document_reference(
                reference_row=reference_row,
                hent_dokumentplacering=(
                    hent_dokumentplacering
                ),
                domain_suffix=domain_suffix,
                inkluder_raw=inkluder_raw,
            )
        )

        normalized_documents.append(
            normalized_document
        )

    logger.info(
        "Dokumentsøgningen returnerede "
        "%s dokumenter",
        len(normalized_documents),
    )

    return normalized_documents

# ------------------------------------------------------------
# BYG DOKUMENTSØGNING
# ------------------------------------------------------------

def build_dokument_search_endpoint(
    filters: list[str],
    top: int = DEFAULT_TOP,
) -> str:
    """
    Byg endpointet til dokumentsøgning.

    Funktionen foretager ikke et API-kald.
    """

    validated_top = _validate_positive_integer(
        top,
        "top",
    )

    if not isinstance(
        filters,
        list,
    ):
        raise TypeError(
            "filters skal være en liste."
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


# ------------------------------------------------------------
# HENT FYSISK DOKUMENTINFORMATION
# ------------------------------------------------------------

def get_dokumentinformation(
    value_rec_id: int,
    domain_suffix: str | None = None,
) -> Dokumentinformation:
    """
    Hent filoplysninger via ValueRecId.

    Funktionen kalder:

        DocuValueDatasEntity_FUJ

    document_path indeholder den færdige
    UNC-sti eller None.

    Args:
        value_rec_id:
            Id på dokumentets filværdi.

        domain_suffix:
            Valgfrit domæne til UNC-stien.

    Returns:
        En Dokumentinformation-datamodel.
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

    response = get(
        endpoint
    )

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

    file_id = str(
        row.get(
            "FileId",
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
        file_id=file_id,
        raw=dict(
            row
        ),
    )


# ------------------------------------------------------------
# NORMALISÉR DOKUMENTREFERENCE
# ------------------------------------------------------------

def _normalize_document_reference(
    reference_row: dict[str, Any],
    hent_dokumentplacering: bool,
    domain_suffix: str | None,
    inkluder_raw: bool,
) -> dict[str, Any]:
    """
    Normalisér én Prisme-dokumentreference.

    Funktionen returnerer altid de samme
    dokumentfelter.

    Feltet raw tilføjes kun, når
    inkluder_raw=True.
    """

    if not isinstance(
        reference_row,
        dict,
    ):
        raise TypeError(
            "reference_row skal være en "
            "dictionary."
        )

    if not isinstance(
        inkluder_raw,
        bool,
    ):
        raise TypeError(
            "inkluder_raw skal være "
            "True eller False."
        )

    document_reference_id = (
        _optional_positive_integer(
            reference_row.get(
                "RecIdLoc"
            ),
            "dokumentets RecIdLoc",
        )
    )

    reference_id = _optional_positive_integer(
        reference_row.get(
            "RefRecId"
        ),
        "RefRecId",
    )

    ref_table_id = _optional_positive_integer(
        reference_row.get(
            "RefTableId"
        ),
        "RefTableId",
    )

    raw_value_rec_id = reference_row.get(
        "ValueRecId"
    )

    has_physical_file = _has_physical_document(
        raw_value_rec_id
    )

    if has_physical_file:
        value_rec_id = int(
            raw_value_rec_id
        )
    else:
        value_rec_id = None

    document_id = str(
        reference_row.get(
            "DocumentId",
            "",
        )
        or ""
    ).strip()

    type_id = str(
        reference_row.get(
            "TypeId",
            "",
        )
        or ""
    ).strip()

    reference_name = str(
        reference_row.get(
            "Name",
            "",
        )
        or ""
    ).strip()

    note_text = str(
        reference_row.get(
            "Notes",
            "",
        )
        or ""
    ).strip()

    created_date = reference_row.get(
        "CreatedOn"
    )

    originally_created_by = str(
        reference_row.get(
            "OriginallyCreatedBy",
            "",
        )
        or ""
    ).strip()

    created_by_loc = str(
        reference_row.get(
            "CreatedByLoc",
            "",
        )
        or ""
    ).strip()

    if originally_created_by:
        created_by = originally_created_by
    else:
        created_by = created_by_loc

    modified_date_time = reference_row.get(
        "ModifiedDateTimeLoc"
    )

    modified_by = str(
        reference_row.get(
            "ModifiedByLoc",
            "",
        )
        or ""
    ).strip()

    legal_entity = str(
        reference_row.get(
            "LegalEntity",
            "",
        )
        or ""
    ).strip()

    is_note = (
        type_id.casefold()
        == "notat"
    )

    document_name = reference_name
    document_path = None
    access_information_raw = ""
    file_id = ""
    value_raw = None

    if not has_physical_file:
        location_status = (
            DOCUMENT_LOCATION_NOT_RELEVANT
        )

    elif not hent_dokumentplacering:
        location_status = (
            DOCUMENT_LOCATION_NOT_FETCHED
        )

    else:
        information = get_dokumentinformation(
            value_rec_id=value_rec_id,
            domain_suffix=domain_suffix,
        )

        value_raw = dict(
            information.raw
        )

        if information.original_file_name:
            document_name = (
                information.original_file_name
            )

        document_path = (
            information.document_path
        )

        access_information_raw = (
            information.access_information_raw
        )

        file_id = information.file_id

        if document_path:
            location_status = (
                DOCUMENT_LOCATION_FETCHED
            )
        else:
            location_status = (
                DOCUMENT_LOCATION_MISSING
            )

    normalized_document = {
        "DocumentId": document_id,
        "DokumentReferenceRecId": (
            document_reference_id
        ),
        "ReferenceRecId": reference_id,
        "ValueRecId": value_rec_id,
        "FilId": file_id,
        "RefTableId": ref_table_id,
        "TypeId": type_id,
        "Dokumentnavn": document_name,
        "Dokumentsti": document_path,
        "AccessInformationRaw": (
            access_information_raw
        ),
        "ErFysiskFil": has_physical_file,
        "ErNotat": is_note,
        "DokumentplaceringStatus": (
            location_status
        ),
        "Notat": note_text,
        "OprettetDato": created_date,
        "OprettetAf": created_by,
        "OriginallyCreatedBy": (
            originally_created_by
        ),
        "ModifiedDateTimeLoc": (
            modified_date_time
        ),
        "ModifiedByLoc": modified_by,
        "LegalEntity": legal_entity,
    }

    if inkluder_raw:
        normalized_document["raw"] = {
            "reference": dict(
                reference_row
            ),
            "value": value_raw,
        }

    return normalized_document

# ------------------------------------------------------------
# NORMALISÉR DOKUMENTSTI
# ------------------------------------------------------------

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

    if value.startswith(
        "\\\\"
    ):
        return str(
            PureWindowsPath(
                value
            )
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
            clean_domain_suffix.lstrip(
                "."
            )
        )

        host = (
            f"{host}.{clean_domain_suffix}"
        )

    path_parts = []

    for part in parsed.path.split(
        "/"
    ):
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


# ------------------------------------------------------------
# NORMALISÉR API-SVAR
# ------------------------------------------------------------

def _normalize_list_response(
    response: Any,
    operation_name: str,
) -> list[dict[str, Any]]:
    """
    Kontrollér et API-svar, der skal være
    en liste.

    api_client.get returnerer OData value
    som en liste.
    """

    if response is None:
        return []

    if not isinstance(
        response,
        list,
    ):
        raise TypeError(
            "API-klientens get-funktion skal "
            f"returnere en liste for "
            f"{operation_name}, men returnerede "
            f"{type(response).__name__}."
        )

    rows = []

    for row in response:
        if not isinstance(
            row,
            dict,
        ):
            logger.warning(
                "Springer en dokumentrække "
                "over, fordi rækken ikke er "
                "en dictionary"
            )

            continue

        rows.append(
            dict(
                row
            )
        )

    return rows


def _normalize_single_response(
    response: Any,
) -> list[dict[str, Any]]:
    """
    Normalisér et direkte nøgleopslag.

    api_client.get kan returnere:

        En dictionary ved direkte opslag.
        En liste ved et OData-listesvar.
        None, hvis intet blev returneret.
    """

    if response is None:
        return []

    if isinstance(
        response,
        dict,
    ):
        return [
            dict(
                response
            )
        ]

    if isinstance(
        response,
        list,
    ):
        rows = []

        for row in response:
            if isinstance(
                row,
                dict,
            ):
                rows.append(
                    dict(
                        row
                    )
                )

        return rows

    raise TypeError(
        "Dokumentinformationen skal være "
        "en liste eller dictionary, men var "
        f"{type(response).__name__}."
    )


# ------------------------------------------------------------
# DOKUMENTTYPE OG ID
# ------------------------------------------------------------

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
    except (
        TypeError,
        ValueError,
    ):
        return False

    return numeric_value > 0


def _optional_positive_integer(
    value: Any,
    variable_name: str,
) -> int | None:
    """Normalisér et valgfrit positivt id."""

    if value in (
        None,
        "",
        0,
        "0",
    ):
        return None

    return _validate_positive_integer(
        value,
        variable_name,
    )


# ------------------------------------------------------------
# INPUTKONTROL
# ------------------------------------------------------------

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

    if isinstance(
        value,
        bool,
    ):
        raise TypeError(
            f"{variable_name} skal være "
            "et positivt heltal."
        )

    try:
        integer_value = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as error:
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

    if not isinstance(
        value,
        date,
    ):
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