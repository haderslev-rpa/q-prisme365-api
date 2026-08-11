"""Læsning og validering af finansielle kontostrenge i Prisme 365."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Any

from q_prisme365_api.api_client import get
from q_prisme365_api.exceptions import (
    KontostrengIkkeEntydigError,
    KontostrengIkkeFundetError,
    UgyldigKontostrengError,
)
from q_prisme365_api.odata import (
    eq_text,
    or_equals_text,
)


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------

KONTOSTRENG_ENDPOINT = (
    "DimensionAttributeValue"
    "CombinationDatasEntity_FUJ"
)

DIMENSION_ENDPOINT = "FinancialDimensionValues"

HOVEDKONTO_ENDPOINT = (
    "DimensionAttributeValueDatasEntity_FUJ"
)

DRIFTSENHED_ENDPOINT = (
    "DimAttributeOMDepartments_FUJ"
)


# ------------------------------------------------------------
# STANDARDVÆRDIER
# ------------------------------------------------------------

DEFAULT_ACCOUNT_STRUCTURE_NAME = "HAd"
DEFAULT_BATCH_SIZE = 20
DEFAULT_TOP = 10000


# ------------------------------------------------------------
# KONTOSTRENGSFORMAT
# ------------------------------------------------------------

KONTOSTRENG_PATTERN = re.compile(
    r"^(?P<afdeling>\d{12})-"
    r"(?P<hovedkonto>\d{9})-"
    r"(?P<aktivitet>\d{5})-"
    r"(?P<art>\d{2})-$"
)


# ------------------------------------------------------------
# DATAMODELLER
# ------------------------------------------------------------

@dataclass(frozen=True)
class KontostrengDele:
    """De fire dele i en kontostreng."""

    afdeling: str
    hovedkonto: str
    aktivitet: str
    art: str


@dataclass(frozen=True)
class KontostrengValidationResult:
    """Resultat af kontrol af én kontostreng."""

    kontostreng: str
    is_valid: bool
    ledger_dimension_id: int | None
    reason: str = ""


@dataclass(frozen=True)
class Driftsenhed:
    """En driftsenhed fra Prisme."""

    afdelingsnummer: str
    rec_id_loc: int
    raw: dict[str, Any]


# ------------------------------------------------------------
# PARSE KONTOSTRENG
# ------------------------------------------------------------

def parse_kontostreng(
    kontostreng: str,
) -> KontostrengDele:
    """
    Opdel en kontostreng i fire dele.

    Forventet format:
        123456789012-123456789-12345-12-
    """

    if not isinstance(
        kontostreng,
        str,
    ):
        raise TypeError(
            "kontostreng skal være tekst."
        )

    value = kontostreng.strip()

    match = KONTOSTRENG_PATTERN.fullmatch(
        value
    )

    if match is None:
        raise UgyldigKontostrengError(
            "Kontostrengen skal have formatet "
            "123456789012-123456789-12345-12-"
        )

    return KontostrengDele(
        afdeling=match.group("afdeling"),
        hovedkonto=match.group(
            "hovedkonto"
        ),
        aktivitet=match.group(
            "aktivitet"
        ),
        art=match.group("art"),
    )


# ------------------------------------------------------------
# FIND ÉT KONTOSTRENG-ID
# ------------------------------------------------------------

def find_kontostreng_id(
    kontostreng: str,
    account_structure_name: str = (
        DEFAULT_ACCOUNT_STRUCTURE_NAME
    ),
) -> int:
    """Find LedgerDimension-id for én kontostreng."""

    clean_value = _require_text(
        kontostreng,
        "kontostreng",
    )

    results = find_kontostreng_ids(
        kontostrenge=[clean_value],
        account_structure_name=(
            account_structure_name
        ),
    )

    return results[clean_value]


# ------------------------------------------------------------
# FIND FLERE KONTOSTRENG-ID'ER
# ------------------------------------------------------------

def find_kontostreng_ids(
    kontostrenge: Sequence[str],
    account_structure_name: str = (
        DEFAULT_ACCOUNT_STRUCTURE_NAME
    ),
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, int]:
    """
    Find LedgerDimension-id'er for kontostrenge.

    Kontostrenge hentes samlet i grupper.
    LedgerDimensionType filtreres lokalt,
    fordi feltet er en D365-enum.
    """

    unique_values = _unique_text_values(
        kontostrenge
    )

    if not unique_values:
        return {}

    validated_batch_size = (
        _validate_positive_integer(
            batch_size,
            "batch_size",
        )
    )

    clean_structure_name = _require_text(
        account_structure_name,
        "account_structure_name",
    )

    rows = []

    for value_group in _chunked(
        unique_values,
        validated_batch_size,
    ):
        filters = [
            eq_text(
                "AccountStructureName",
                clean_structure_name,
            ),
            or_equals_text(
                "DisplayValue",
                value_group,
            ),
        ]

        endpoint = _build_endpoint(
            entity=KONTOSTRENG_ENDPOINT,
            filters=filters,
            top=DEFAULT_TOP,
            select=[
                "RecIdLoc",
                "DisplayValue",
                "LedgerDimensionType",
                "AccountStructureName",
            ],
        )

        logger.info(
            "Henter kontostreng-id'er for "
            "%s kontostrenge",
            len(value_group),
        )

        logger.debug(
            "Kontostrengsopslag endpoint: %s",
            endpoint,
        )

        response = get(endpoint)

        group_rows = _normalize_list_response(
            response,
            "kontostrengsopslaget",
        )

        rows.extend(
            group_rows
        )

    ids_by_value = {}

    for value in unique_values:
        ids_by_value[value] = set()

    for row in rows:
        display_value = str(
            row.get(
                "DisplayValue",
                "",
            )
            or ""
        ).strip()

        if display_value not in ids_by_value:
            continue

        ledger_dimension_type = str(
            row.get(
                "LedgerDimensionType",
                "",
            )
            or ""
        ).strip().casefold()

        if not _is_account_dimension_type(
            ledger_dimension_type
        ):
            continue

        rec_id = row.get(
            "RecIdLoc"
        )

        if rec_id in (
            None,
            "",
        ):
            continue

        ids_by_value[
            display_value
        ].add(
            int(rec_id)
        )

    results = {}

    for value, found_ids in (
        ids_by_value.items()
    ):
        if not found_ids:
            raise KontostrengIkkeFundetError(
                "Kontostrengen blev ikke fundet "
                "som en Account-kombination: "
                f"{value}"
            )

        if len(found_ids) > 1:
            raise KontostrengIkkeEntydigError(
                "Kontostrengen matchede flere "
                "LedgerDimension-id'er: "
                f"{value}"
            )

        results[value] = next(
            iter(found_ids)
        )

    return results

# ------------------------------------------------------------
# HENT ÉN DRIFTSENHED
# ------------------------------------------------------------

def get_driftsenhed(
    afdelingsnummer: str,
) -> Driftsenhed:
    """Hent én driftsenhed via afdelingsnummer."""

    clean_department = _validate_department(
        afdelingsnummer
    )

    results = get_driftsenheder(
        afdelingsnumre=[
            clean_department
        ]
    )

    return results[clean_department]


# ------------------------------------------------------------
# HENT FLERE ELLER ALLE DRIFTSENHEDER
# ------------------------------------------------------------

def get_driftsenheder(
    afdelingsnumre: Sequence[str] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Driftsenhed]:
    """
    Hent udvalgte eller alle driftsenheder.

    Hvis afdelingsnumre er None, hentes alle.
    """

    validated_batch_size = (
        _validate_positive_integer(
            batch_size,
            "batch_size",
        )
    )

    rows = []

    if afdelingsnumre is None:
        endpoint = _build_endpoint(
            entity=DRIFTSENHED_ENDPOINT,
            filters=[],
            top=DEFAULT_TOP,
            select=[
                "RecIdLoc",
                "OMOperatingUnitNumber",
            ],
        )

        response = get(endpoint)

        rows = _normalize_list_response(
            response,
            "driftsenhedsopslaget",
        )

        requested_values = None
    else:
        requested_values = []

        for afdelingsnummer in (
            afdelingsnumre
        ):
            clean_department = (
                _validate_department(
                    afdelingsnummer
                )
            )

            if (
                clean_department
                not in requested_values
            ):
                requested_values.append(
                    clean_department
                )

        for value_group in _chunked(
            requested_values,
            validated_batch_size,
        ):
            endpoint = _build_endpoint(
                entity=DRIFTSENHED_ENDPOINT,
                filters=[
                    or_equals_text(
                        "OMOperatingUnitNumber",
                        value_group,
                    )
                ],
                top=DEFAULT_TOP,
                select=[
                    "RecIdLoc",
                    "OMOperatingUnitNumber",
                ],
            )

            response = get(endpoint)

            group_rows = (
                _normalize_list_response(
                    response,
                    "driftsenhedsopslaget",
                )
            )

            rows.extend(group_rows)

    grouped_rows = _group_rows(
        rows,
        "OMOperatingUnitNumber",
    )

    results = {}

    for number, matching_rows in (
        grouped_rows.items()
    ):
        found_ids = set()

        for row in matching_rows:
            rec_id = row.get("RecIdLoc")

            if rec_id not in (None, ""):
                found_ids.add(
                    int(rec_id)
                )

        if not found_ids:
            continue

        if len(found_ids) > 1:
            raise KontostrengIkkeEntydigError(
                "Driftsenheden matchede flere "
                "RecIdLoc-værdier: "
                f"{number}"
            )

        results[number] = Driftsenhed(
            afdelingsnummer=number,
            rec_id_loc=next(
                iter(found_ids)
            ),
            raw=dict(
                matching_rows[0]
            ),
        )

    if requested_values is not None:
        missing_values = []

        for value in requested_values:
            if value not in results:
                missing_values.append(
                    value
                )

        if missing_values:
            raise KontostrengIkkeFundetError(
                "Følgende driftsenheder blev "
                "ikke fundet: "
                + ", ".join(missing_values)
            )

    return results


# ------------------------------------------------------------
# VALIDÉR ÉN KONTOSTRENG
# ------------------------------------------------------------

def validate_kontostreng(
    kontostreng: str,
    dato: date,
) -> KontostrengValidationResult:
    """Validér én kontostreng."""

    clean_value = _require_text(
        kontostreng,
        "kontostreng",
    )

    results = validate_kontostrenge(
        kontostrenge=[clean_value],
        dato=dato,
    )

    return results[clean_value]


# ------------------------------------------------------------
# VALIDÉR FLERE KONTOSTRENGE
# ------------------------------------------------------------

def validate_kontostrenge(
    kontostrenge: Sequence[str],
    dato: date,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, KontostrengValidationResult]:
    """
    Validér flere kontostrenge samlet.

    Der foretages normalt:
        ét opslag til afdelinger
        ét opslag til hovedkonti
        ét opslag til aktiviteter
        ét opslag til arter
        ét opslag til kombinations-id'er

    Der kan komme flere kald, hvis værdierne
    opdeles i flere batches.
    """

    checked_date = _validate_date(
        dato,
        "dato",
    )

    validated_batch_size = (
        _validate_positive_integer(
            batch_size,
            "batch_size",
        )
    )

    unique_values = _unique_text_values(
        kontostrenge
    )

    parsed_values = {}
    results = {}

    for value in unique_values:
        try:
            parsed_values[value] = (
                parse_kontostreng(value)
            )
        except UgyldigKontostrengError as error:
            results[value] = (
                KontostrengValidationResult(
                    kontostreng=value,
                    is_valid=False,
                    ledger_dimension_id=None,
                    reason=str(error),
                )
            )

    if not parsed_values:
        return results

    departments = set()
    main_accounts = set()
    activities = set()
    categories = set()

    for parts in parsed_values.values():
        departments.add(
            parts.afdeling
        )
        main_accounts.add(
            parts.hovedkonto
        )
        activities.add(
            parts.aktivitet
        )
        categories.add(
            parts.art
        )

    department_rows = _get_dimension_rows(
        dimension_name="Afdeling",
        values=departments,
        batch_size=validated_batch_size,
    )

    main_account_rows = (
        _get_main_account_rows(
            values=main_accounts,
            batch_size=(
                validated_batch_size
            ),
        )
    )

    activity_rows = _get_dimension_rows(
        dimension_name="Aktivitet",
        values=activities,
        batch_size=validated_batch_size,
    )

    category_rows = _get_dimension_rows(
        dimension_name="Art",
        values=categories,
        batch_size=validated_batch_size,
    )

    combination_ids, combination_errors = (
        _find_kontostreng_ids_for_validation(
            values=list(parsed_values),
            batch_size=validated_batch_size,
            account_structure_name=(
                DEFAULT_ACCOUNT_STRUCTURE_NAME
            ),
        )
    )

    for value, parts in (
        parsed_values.items()
    ):
        checks = [
            (
                "Afdeling",
                parts.afdeling,
                department_rows.get(
                    parts.afdeling,
                    [],
                ),
            ),
            (
                "Hovedkonto",
                parts.hovedkonto,
                main_account_rows.get(
                    parts.hovedkonto,
                    [],
                ),
            ),
            (
                "Aktivitet",
                parts.aktivitet,
                activity_rows.get(
                    parts.aktivitet,
                    [],
                ),
            ),
            (
                "Art",
                parts.art,
                category_rows.get(
                    parts.art,
                    [],
                ),
            ),
        ]

        reason = ""

        for name, dimension_value, rows in (
            checks
        ):
            reason = _validate_dimension_rows(
                name=name,
                value=dimension_value,
                rows=rows,
                checked_date=checked_date,
            )

            if reason:
                break

        if not reason:
            reason = combination_errors.get(
                value,
                "",
            )

        ledger_dimension_id = (
            combination_ids.get(value)
        )

        results[value] = (
            KontostrengValidationResult(
                kontostreng=value,
                is_valid=(
                    not reason
                    and ledger_dimension_id
                    is not None
                ),
                ledger_dimension_id=(
                    ledger_dimension_id
                ),
                reason=reason,
            )
        )

    return results


# ------------------------------------------------------------
# HENT DIMENSIONSVÆRDIER
# ------------------------------------------------------------

def _get_dimension_rows(
    dimension_name: str,
    values: set[str],
    batch_size: int,
) -> dict[str, list[dict[str, Any]]]:
    """Hent værdier for én dimensionstype."""

    rows = []

    for value_group in _chunked(
        sorted(values),
        batch_size,
    ):
        endpoint = _build_endpoint(
            entity=DIMENSION_ENDPOINT,
            filters=[
                eq_text(
                    "FinancialDimension",
                    dimension_name,
                ),
                or_equals_text(
                    "DimensionValue",
                    value_group,
                ),
            ],
            top=DEFAULT_TOP,
            select=[
                "FinancialDimension",
                "DimensionValue",
                "ActiveFrom",
                "ActiveTo",
                "IsSuspended",
                "IsBlockedForManualEntry",
            ],
        )

        response = get(endpoint)

        group_rows = _normalize_list_response(
            response,
            f"{dimension_name}-opslaget",
        )

        rows.extend(group_rows)

    return _group_rows(
        rows,
        "DimensionValue",
    )


# ------------------------------------------------------------
# HENT HOVEDKONTI
# ------------------------------------------------------------

def _get_main_account_rows(
    values: set[str],
    batch_size: int,
) -> dict[str, list[dict[str, Any]]]:
    """Hent flere hovedkonti samlet."""

    rows = []

    for value_group in _chunked(
        sorted(values),
        batch_size,
    ):
        endpoint = _build_endpoint(
            entity=HOVEDKONTO_ENDPOINT,
            filters=[
                or_equals_text(
                    "DisplayValue",
                    value_group,
                )
            ],
            top=DEFAULT_TOP,
            select=[
                "DisplayValue",
                "ActiveFrom",
                "ActiveTo",
                "IsSuspended",
                "IsBlockedForManualEntry",
            ],
        )

        response = get(endpoint)

        group_rows = _normalize_list_response(
            response,
            "hovedkontoopslaget",
        )

        rows.extend(group_rows)

    return _group_rows(
        rows,
        "DisplayValue",
    )


# ------------------------------------------------------------
# FIND ID'ER UDEN AT STOPPE VALIDERINGEN
# ------------------------------------------------------------

def _find_kontostreng_ids_for_validation(
    values: list[str],
    batch_size: int,
    account_structure_name: str,
) -> tuple[dict[str, int], dict[str, str]]:
    """
    Find kontostreng-id'er under validering.

    Funktionen (genbrugelig kodeblok) stopper
    ikke hele valideringen, hvis én kontostreng
    mangler.

    Opslaget afgrænses til kontostrukturen HAd.
    LedgerDimensionType filtreres lokalt, fordi
    feltet er en D365-enum.
    """

    clean_structure_name = _require_text(
        account_structure_name,
        "account_structure_name",
    )

    rows = []

    for value_group in _chunked(
        values,
        batch_size,
    ):
        endpoint = _build_endpoint(
            entity=KONTOSTRENG_ENDPOINT,
            filters=[
                eq_text(
                    "AccountStructureName",
                    clean_structure_name,
                ),
                or_equals_text(
                    "DisplayValue",
                    value_group,
                ),
            ],
            top=DEFAULT_TOP,
            select=[
                "RecIdLoc",
                "DisplayValue",
                "LedgerDimensionType",
                "AccountStructureName",
            ],
        )

        logger.info(
            "Henter kombinations-id'er for "
            "%s kontostrenge i kontostruktur %s",
            len(value_group),
            clean_structure_name,
        )

        response = get(endpoint)

        group_rows = _normalize_list_response(
            response,
            "kontostrengskombinationsopslaget",
        )

        rows.extend(
            group_rows
        )

    grouped_rows = _group_rows(
        rows,
        "DisplayValue",
    )

    ids = {}
    errors = {}

    for value in values:
        found_ids = set()

        matching_rows = grouped_rows.get(
            value,
            [],
        )

        for row in matching_rows:
            row_structure_name = str(
                row.get(
                    "AccountStructureName",
                    "",
                )
                or ""
            ).strip().casefold()

            if (
                row_structure_name
                != clean_structure_name.casefold()
            ):
                continue

            ledger_dimension_type = str(
                row.get(
                    "LedgerDimensionType",
                    "",
                )
                or ""
            ).strip().casefold()

            if not _is_account_dimension_type(
                ledger_dimension_type
            ):
                continue

            rec_id = row.get(
                "RecIdLoc"
            )

            if rec_id in (
                None,
                "",
            ):
                continue

            found_ids.add(
                int(rec_id)
            )

        if not found_ids:
            errors[value] = (
                "Kontostrengskombination findes "
                "ikke som Account i kontostruktur "
                f"{clean_structure_name}"
            )
        elif len(found_ids) > 1:
            sorted_ids = sorted(
                found_ids
            )

            errors[value] = (
                "Kontostrengskombinationen er ikke "
                "entydig i kontostruktur "
                f"{clean_structure_name}. "
                f"Fundne id'er: {sorted_ids}"
            )
        else:
            ids[value] = next(
                iter(found_ids)
            )

    return ids, errors

# ------------------------------------------------------------
# VALIDÉR DIMENSIONSSTATUS
# ------------------------------------------------------------

def _validate_dimension_rows(
    name: str,
    value: str,
    rows: list[dict[str, Any]],
    checked_date: date,
) -> str:
    """Kontrollér om en dimension findes og er åben."""

    if not rows:
        return f"{name} findes ikke: {value}"

    reasons = []

    for row in rows:
        reason = _dimension_closed_reason(
            name=name,
            row=row,
            checked_date=checked_date,
        )

        if not reason:
            return ""

        reasons.append(reason)

    if reasons:
        return reasons[0]

    return f"{name} kunne ikke valideres"


def _dimension_closed_reason(
    name: str,
    row: dict[str, Any],
    checked_date: date,
) -> str:
    """Forklar hvorfor en dimension er lukket."""

    if _is_yes(
        row.get("IsSuspended")
    ):
        return f"{name} er suspenderet"

    if _is_yes(
        row.get(
            "IsBlockedForManualEntry"
        )
    ):
        return (
            f"{name} er spærret "
            "for manuel postering"
        )

    active_from = _parse_prisme_date(
        row.get("ActiveFrom")
    )

    active_to = _parse_prisme_date(
        row.get("ActiveTo")
    )

    if (
        active_from is not None
        and checked_date < active_from
    ):
        return (
            f"{name} er ikke aktiv "
            "på kontroldatoen"
        )

    has_real_end_date = (
        active_to is not None
        and active_to.year != 1900
    )

    if (
        has_real_end_date
        and checked_date > active_to
    ):
        return (
            f"{name} er lukket "
            "på kontroldatoen"
        )

    return ""


# ------------------------------------------------------------
# FÆLLES HJÆLPEFUNKTIONER
# ------------------------------------------------------------

def _build_endpoint(
    entity: str,
    filters: list[str],
    top: int,
    select: list[str] | None = None,
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

    if select:
        clean_fields = []

        for field in select:
            clean_field = str(
                field
            ).strip()

            if clean_field:
                clean_fields.append(
                    clean_field
                )

        if clean_fields:
            endpoint += (
                "&$select="
                + ",".join(clean_fields)
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


def _group_rows(
    rows: list[dict[str, Any]],
    field: str,
) -> dict[str, list[dict[str, Any]]]:
    """Gruppér API-rækker efter et felt."""

    grouped = {}

    for row in rows:
        value = str(
            row.get(
                field,
                "",
            )
            or ""
        ).strip()

        if not value:
            continue

        if value not in grouped:
            grouped[value] = []

        grouped[value].append(
            row
        )

    return grouped

def _unique_text_values(
    values: Sequence[str],
) -> list[str]:
    """Returnér unikke udfyldte tekstværdier."""

    if isinstance(values, str):
        raise TypeError(
            "Der skal sendes en liste eller tuple, "
            "ikke én enkelt tekstværdi."
        )

    results = []

    for value in values:
        clean_value = _require_text(
            value,
            "værdi",
        )

        if clean_value not in results:
            results.append(
                clean_value
            )

    return results

def _chunked(
    values: list[str],
    size: int,
) -> list[list[str]]:
    """Opdel værdier i mindre grupper."""

    groups = []
    index = 0

    while index < len(values):
        groups.append(
            values[index : index + size]
        )

        index += size

    return groups


def _validate_department(
    value: str,
) -> str:
    """Kontrollér et afdelingsnummer."""

    clean_value = _require_text(
        value,
        "afdelingsnummer",
    )

    if len(clean_value) != 12:
        raise ValueError(
            "afdelingsnummer skal være "
            "præcis 12 cifre."
        )

    if not clean_value.isdigit():
        raise ValueError(
            "afdelingsnummer må kun "
            "indeholde cifre."
        )

    return clean_value


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


def _validate_date(
    value: Any,
    variable_name: str,
) -> date:
    """Kontrollér en dato."""

    if isinstance(value, datetime):
        return value.date()

    if not isinstance(value, date):
        raise TypeError(
            f"{variable_name} skal være "
            "en date-værdi."
        )

    return value


def _require_text(
    value: Any,
    variable_name: str,
) -> str:
    """Kontrollér obligatorisk tekst."""

    if value is None:
        raise ValueError(
            f"{variable_name} skal udfyldes."
        )

    text_value = str(
        value
    ).strip()

    if not text_value:
        raise ValueError(
            f"{variable_name} må ikke være tom."
        )

    return text_value


def _is_yes(
    value: Any,
) -> bool:
    """Fortolk en Yes-værdi fra Prisme."""

    normalized_value = str(
        value
        or ""
    ).strip().casefold()

    return normalized_value in {
        "yes",
        "ja",
        "true",
        "1",
    }


def _parse_prisme_date(
    value: Any,
) -> date | None:
    """Fortolk almindelige datoformater fra Prisme."""

    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if text.startswith("1900"):
        return date(1900, 1, 1)

    iso_text = text.replace(
        "Z",
        "+00:00",
    )

    try:
        return datetime.fromisoformat(
            iso_text
        ).date()
    except ValueError:
        pass

    try:
        return date.fromisoformat(
            text[:10]
        )
    except ValueError:
        pass

    for date_format in (
        "%d-%m-%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(
                text[:10],
                date_format,
            ).date()
        except ValueError:
            continue

    return None

def _is_account_dimension_type(
    value: str,
) -> bool:
    """
    Kontrollér LedgerDimensionType lokalt.

    Prisme kan returnere værdien som:
        Account

    eller som et længere enum-navn,
    der slutter med Account.
    """

    normalized_value = str(
        value
        or ""
    ).strip().casefold()

    if not normalized_value:
        return False

    if normalized_value == "account":
        return True

    if normalized_value.endswith(
        ".account"
    ):
        return True

    if normalized_value.endswith(
        "'account'"
    ):
        return True

    return False