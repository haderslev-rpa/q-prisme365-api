"""Søgning efter dokumenter og notater i Prisme 365."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import PureWindowsPath
from typing import Any, Iterable
from urllib.parse import unquote, urlparse
from uuid import UUID

from q_prisme365_api.api_client import get
from q_prisme365_api.odata import eq_date, eq_number, eq_text

__all__ = [
    "Dokumentinformation",
    "search_dokumenter",
    "hent_dokumentreferencer",
    "get_dokumentinformation",
    "normalize_document_path",
]
logger = logging.getLogger(__name__)
DOCUMENT_REFERENCE_ENDPOINT = "DocuRefDatasEntity_FUJ"
DOCUMENT_VALUE_ENDPOINT = "DocuValueDatasEntity_FUJ"
DEFAULT_COMPANY_ID = "had"
DEFAULT_TOP = 1000
TABLE_IDS = {"cpr_cvr": 27526, "ventende_kreditorfaktura": 6084}
DOCUMENT_LOCATION_FETCHED = "hentet"
DOCUMENT_LOCATION_NOT_FETCHED = "ikke_hentet"
DOCUMENT_LOCATION_NOT_RELEVANT = "ikke_relevant"
DOCUMENT_LOCATION_MISSING = "mangler"

@dataclass(frozen=True)
class Dokumentinformation:
    """Oplysninger om en fysisk dokumentfil."""
    value_rec_id: int
    original_file_name: str
    access_information_raw: str
    document_path: str | None
    file_id: str
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
    inkluder_raw: bool = False,
    top: int = DEFAULT_TOP,
    *,
    ref_table_id: int | None = None,
    dokumenttyper: Iterable[str] | None = None,
    data_area_id: str = DEFAULT_COMPANY_ID,
) -> list[dict[str, Any]]:
    """Søg og returnér normaliserede dokumenter.

    Eksisterende argumenter og output er bevaret. Nye keyword-only argumenter:
    ref_table_id kan angive numerisk tabel-id direkte, dokumenttyper kan filtrere
    på flere TypeId-værdier, og data_area_id kan vælge selskab.
    """
    validated_top = _validate_positive_integer(top, "top")
    if not isinstance(hent_dokumentplacering, bool) or not isinstance(inkluder_raw, bool):
        raise TypeError("Bool-parametre skal være True eller False.")
    validated_table = _validate_table(tabel)
    filters = [eq_text("RefCompanyId", _required_text(data_area_id, "data_area_id"))]
    if ref_table_id is not None:
        selected_table_id = _validate_positive_integer(ref_table_id, "ref_table_id")
        if validated_table is not None and TABLE_IDS[validated_table] != selected_table_id:
            raise ValueError("tabel og ref_table_id peger på forskellige tabeller.")
        filters.append(eq_number("RefTableId", selected_table_id))
    elif validated_table is not None:
        filters.append(eq_number("RefTableId", TABLE_IDS[validated_table]))
    if ref_rec_id is not None:
        filters.append(eq_number("RefRecId", _validate_positive_integer(ref_rec_id, "ref_rec_id")))
    clean_document_id = _clean_optional_text(document_id)
    if clean_document_id is not None:
        try:
            guid = str(UUID(clean_document_id))
        except ValueError as error:
            raise ValueError("document_id skal være et gyldigt GUID.") from error
        filters.append(f"DocumentId eq {guid}")
    for field, value in (("LegalEntity", cpr_cvr), ("Name", dokumentnavn),
                         ("OriginallyCreatedBy", oprettet_af)):
        clean = _clean_optional_text(value)
        if clean is not None:
            filters.append(eq_text(field, clean))
    clean_type = _clean_optional_text(dokumenttype)
    allowed_types = _normalize_types(dokumenttyper)
    if clean_type is not None and allowed_types is not None and clean_type.casefold() not in allowed_types:
        return []
    if clean_type is not None:
        filters.append(eq_text("TypeId", clean_type))
    clean_note = _clean_optional_text(notat_tekst, strip_value=False)
    if clean_note is not None:
        filters.append(eq_text("Notes", clean_note))
    if oprettet_dato is not None:
        filters.append(eq_date("CreatedOn", _validate_date(oprettet_dato, "oprettet_dato")))
    response = get(build_dokument_search_endpoint(filters, validated_top))
    rows = _normalize_list_response(response, "dokumentsøgningen")
    if allowed_types is not None:
        rows = [r for r in rows if str(r.get("TypeId") or "").casefold() in allowed_types]
    return [_normalize_document_reference(r, hent_dokumentplacering, domain_suffix, inkluder_raw) for r in rows]


def hent_dokumentreferencer(
    ref_table_id: int,
    oprettet_fra: date | None = None,
    oprettet_til: date | None = None,
    dokumenttyper: Iterable[str] | None = ("OIOUBL",),
    data_area_id: str = DEFAULT_COMPANY_ID,
    top: int = 100000,
    inkluder_raw: bool = False,
) -> list[dict[str, Any]]:
    """Hent dokumentreferencer i bulk uden filopslag.

    Output er samme normaliserede struktur som search_dokumenter, men
    Dokumentsti er None og status er ikke_hentet for fysiske filer.
    Datointervallet er halvåbent på CreatedOn.
    """
    filters = [
        eq_text("RefCompanyId", _required_text(data_area_id, "data_area_id")),
        eq_number("RefTableId", _validate_positive_integer(ref_table_id, "ref_table_id")),
    ]
    if (oprettet_fra is None) != (oprettet_til is None):
        raise ValueError("Begge oprettelsesdatoer skal angives.")
    if oprettet_fra is not None and oprettet_til is not None:
        start = _validate_date(oprettet_fra, "oprettet_fra")
        end = _validate_date(oprettet_til, "oprettet_til")
        if start >= end:
            raise ValueError("oprettet_fra skal være før oprettet_til.")
        filters.extend([f"CreatedOn ge {_odata_datetime(start)}", f"CreatedOn lt {_odata_datetime(end)}"])
    response = get(build_dokument_search_endpoint(filters, _validate_positive_integer(top, "top")))
    rows = _normalize_list_response(response, "bulk-dokumentopslaget")
    allowed = _normalize_types(dokumenttyper)
    if allowed is not None:
        rows = [r for r in rows if str(r.get("TypeId") or "").casefold() in allowed]
    return [_normalize_document_reference(r, False, None, inkluder_raw) for r in rows]


def build_dokument_search_endpoint(filters: list[str], top: int = DEFAULT_TOP) -> str:
    validated_top = _validate_positive_integer(top, "top")
    if not isinstance(filters, list):
        raise TypeError("filters skal være en liste.")
    clean = [str(v).strip() for v in filters if str(v).strip()]
    endpoint = f"{DOCUMENT_REFERENCE_ENDPOINT}?$top={validated_top}"
    return endpoint + ("&$filter=" + " and ".join(clean) if clean else "")


def get_dokumentinformation(value_rec_id: int, domain_suffix: str | None = None) -> Dokumentinformation:
    validated = _validate_positive_integer(value_rec_id, "value_rec_id")
    rows = _normalize_single_response(get(f"{DOCUMENT_VALUE_ENDPOINT}({validated})"))
    if len(rows) != 1:
        raise ValueError(f"Dokumentinformationen var ikke entydig for ValueRecId {validated}.")
    row = rows[0]
    access = str(row.get("AccessInformation") or "").strip()
    return Dokumentinformation(
        value_rec_id=validated,
        original_file_name=str(row.get("OriginalFileName") or "").strip(),
        access_information_raw=access,
        document_path=normalize_document_path(access, domain_suffix),
        file_id=str(row.get("FileId") or "").strip(),
        raw=dict(row),
    )


def _normalize_document_reference(reference_row: dict[str, Any], hent_dokumentplacering: bool,
                                  domain_suffix: str | None, inkluder_raw: bool) -> dict[str, Any]:
    value_id = _optional_positive_integer(reference_row.get("ValueRecId"), "ValueRecId")
    type_id = str(reference_row.get("TypeId") or "").strip()
    name = str(reference_row.get("Name") or "").strip()
    path = None; access = ""; file_id = ""; value_raw = None
    if value_id is None:
        status = DOCUMENT_LOCATION_NOT_RELEVANT
    elif not hent_dokumentplacering:
        status = DOCUMENT_LOCATION_NOT_FETCHED
    else:
        info = get_dokumentinformation(value_id, domain_suffix)
        name = info.original_file_name or name
        path, access, file_id, value_raw = info.document_path, info.access_information_raw, info.file_id, dict(info.raw)
        status = DOCUMENT_LOCATION_FETCHED if path else DOCUMENT_LOCATION_MISSING
    original_by = str(reference_row.get("OriginallyCreatedBy") or "").strip()
    created_by = original_by or str(reference_row.get("CreatedByLoc") or "").strip()
    result = {
        "DocumentId": str(reference_row.get("DocumentId") or "").strip(),
        "DokumentReferenceRecId": _optional_positive_integer(reference_row.get("RecIdLoc"), "RecIdLoc"),
        "ReferenceRecId": _optional_positive_integer(reference_row.get("RefRecId"), "RefRecId"),
        "ValueRecId": value_id, "FilId": file_id,
        "RefTableId": _optional_positive_integer(reference_row.get("RefTableId"), "RefTableId"),
        "TypeId": type_id, "Dokumentnavn": name, "Dokumentsti": path,
        "AccessInformationRaw": access, "ErFysiskFil": value_id is not None,
        "ErNotat": type_id.casefold() == "notat", "DokumentplaceringStatus": status,
        "Notat": str(reference_row.get("Notes") or "").strip(),
        "OprettetDato": reference_row.get("CreatedOn"), "OprettetAf": created_by,
        "OriginallyCreatedBy": original_by, "ModifiedDateTimeLoc": reference_row.get("ModifiedDateTimeLoc"),
        "ModifiedByLoc": str(reference_row.get("ModifiedByLoc") or "").strip(),
        "LegalEntity": str(reference_row.get("LegalEntity") or "").strip(),
    }
    if inkluder_raw:
        result["raw"] = {"reference": dict(reference_row), "value": value_raw}
    return result


def normalize_document_path(access_information: str, domain_suffix: str | None = None) -> str | None:
    value = str(access_information or "").strip()
    if not value: return None
    if value.startswith("\\\\"): return str(PureWindowsPath(value))
    parsed = urlparse(value)
    if parsed.scheme.casefold() != "file" or not parsed.netloc.strip(): return None
    host = parsed.netloc.strip(); suffix = _clean_optional_text(domain_suffix)
    if suffix is not None and "." not in host: host = f"{host}.{suffix.lstrip('.')}"
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    return "\\\\" + host + ("\\" + "\\".join(parts) if parts else "")


def _normalize_types(values: Iterable[str] | None) -> set[str] | None:
    if values is None: return None
    if isinstance(values, str): values = (values,)
    result = {str(v).strip().casefold() for v in values if str(v).strip()}
    return result

def _normalize_list_response(response: Any, operation_name: str) -> list[dict[str, Any]]:
    if response is None: return []
    if not isinstance(response, list): raise TypeError(f"API-svaret for {operation_name} skal være en liste.")
    return [dict(r) for r in response if isinstance(r, dict)]
def _normalize_single_response(response: Any) -> list[dict[str, Any]]:
    if response is None: return []
    if isinstance(response, dict): return [dict(response)]
    if isinstance(response, list): return [dict(r) for r in response if isinstance(r, dict)]
    raise TypeError("Dokumentinformationen skal være en liste eller dictionary.")
def _optional_positive_integer(value: Any, variable_name: str) -> int | None:
    if value in (None, "", 0, "0"): return None
    return _validate_positive_integer(value, variable_name)
def _validate_table(table_name: str | None) -> str | None:
    if table_name is None: return None
    clean = str(table_name).strip().casefold()
    if not clean: return None
    if clean not in TABLE_IDS: raise ValueError("Ukendt dokumenttabel. Tilladte værdier er: " + ", ".join(TABLE_IDS))
    return clean
def _validate_positive_integer(value: Any, variable_name: str) -> int:
    if isinstance(value, bool): raise TypeError(f"{variable_name} skal være et positivt heltal.")
    try: result = int(value)
    except (TypeError, ValueError) as error: raise TypeError(f"{variable_name} skal kunne konverteres til et heltal.") from error
    if result <= 0: raise ValueError(f"{variable_name} skal være større end 0.")
    return result
def _validate_date(value: Any, variable_name: str) -> date:
    if not isinstance(value, date) or isinstance(value, datetime): raise TypeError(f"{variable_name} skal være en date-værdi.")
    return value
def _clean_optional_text(value: Any, strip_value: bool = True) -> str | None:
    if value is None: return None
    text = str(value); text = text.strip() if strip_value else text
    return text or None
def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text: raise ValueError(f"{name} skal udfyldes.")
    return text
def _odata_datetime(value: date) -> str:
    return datetime.combine(value, time.min, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
