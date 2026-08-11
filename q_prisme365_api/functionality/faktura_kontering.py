"""Samlet og sikker kontering af fakturaer i Prisme 365."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from q_prisme365_api.api_client import delete, get, patch, post
from q_prisme365_api.exceptions import PrismeApiError
from q_prisme365_api.functionality.fakturaer import (
    get_faktura_konteringslinjer,
)
from q_prisme365_api.functionality.kontostrenge import (
    find_kontostreng_ids,
    validate_kontostrenge,
)


__all__ = [
    "konter_faktura",
    "FakturaKonteringsplan",
]


logger = logging.getLogger(__name__)


CREATE_LINE_ENDPOINT = "VendorInvoiceLines"
LINE_ENDPOINT = "FUJ_VendorInvoiceLineEntity"

DEFAULT_TOP = 10000
DEFAULT_UNIT = "STK"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 3.0
DEFAULT_CONTROL_ATTEMPTS = 10
DEFAULT_CONTROL_DELAY_SECONDS = 2.0

# Hvis flere kandidatlinjer i træk fejler,
# behandles fejlen som et generelt problem.
MAX_CONSECUTIVE_REJECTED_LINES = 3

TRANSIENT_STATUS_CODES = {
    None,
    408,
    409,
    423,
    429,
    500,
    502,
    503,
    504,
}


@dataclass(frozen=True)
class FakturaKonteringslinje:
    """Én normaliseret ønsket linje."""

    kontostreng: str
    bruttobeloeb: Decimal
    ydelsesmodtager: str
    enhed: str
    faktura_afdeling: str
    posteringstekst: str
    kreditorkonto: str
    ledger_dimension: int


@dataclass(frozen=True)
class Konteringshandling:
    """Én forventet handling."""

    handling: str
    process_line_number: int | None
    rec_id_loc: int | None
    beskrivelse: str


@dataclass(frozen=True)
class FakturaKonteringsplan:
    """Plan uden ændringer i Prisme."""

    header_reference: str
    strategi: str
    eksisterende_linjer: tuple[dict[str, Any], ...]
    oenskede_linjer: tuple[FakturaKonteringslinje, ...]
    handlinger: tuple[Konteringshandling, ...]
    ledger_dimension_ids: dict[str, int]
    eksisterende_totalbeloeb: Decimal
    oensket_totalbeloeb: Decimal
    cpr_numre_valideret: bool


class UnusableInvoiceLineError(RuntimeError):
    """En bestemt Prisme-linje kan ikke PATCH'es."""


def konter_faktura(
    header_reference: str,
    konteringslinjer: list[dict[str, Any]],
    cpr_numre_valideret: bool,
    udfoer: bool = True,
    kontroldato: date | datetime | None = None,
) -> FakturaKonteringsplan | dict[str, Any]:
    """
    Planlæg eller udfør hele fakturakonteringen.

    Dette er den eneste funktion, som
    processerne skal kalde.

    Args:
        header_reference:
            Fakturaens HeaderReference.

        konteringslinjer:
            Fakturaens ønskede sluttilstand.

            Obligatoriske felter pr. linje:
                kontostreng
                bruttobeloeb
                faktura_afdeling
                kreditorkonto

            Valgfrie felter:
                ydelsesmodtager
                enhed
                posteringstekst

        cpr_numre_valideret:
            Skal være True, hvis mindst én
            ydelsesmodtager er udfyldt.

            True bekræfter, at alle CPR-numre
            er valideret via Datafordeleren.

        udfoer:
            True udfører konteringen.
            False returnerer kun planen.
            Standard er True.

        kontroldato:
            Dato til kontostrengsvalidering.

    Returns:
        Plan ved udfoer=False.
        Resultat ved udfoer=True.
    """

    if not isinstance(udfoer, bool):
        raise TypeError(
            "udfoer skal være True eller False."
        )

    plan = _build_plan(
        header_reference=header_reference,
        konteringslinjer=konteringslinjer,
        cpr_numre_valideret=cpr_numre_valideret,
        kontroldato=kontroldato,
    )

    if not udfoer:
        return plan

    return _execute_plan(plan)


def _build_plan(
    header_reference: str,
    konteringslinjer: list[dict[str, Any]],
    cpr_numre_valideret: bool,
    kontroldato: date | datetime | None,
) -> FakturaKonteringsplan:
    """Validér input og byg planen."""

    reference = _require_text(
        header_reference,
        "header_reference",
    )

    normalized = _normalize_lines(
        konteringslinjer,
        cpr_numre_valideret,
    )

    control_date = _normalize_control_date(
        kontroldato
    )

    unique_accounts = list(
        dict.fromkeys(
            line["kontostreng"]
            for line in normalized
        )
    )

    validation_results = validate_kontostrenge(
        kontostrenge=unique_accounts,
        dato=control_date,
    )

    invalid_accounts = []

    for account in unique_accounts:
        result = validation_results[account]

        if not result.is_valid:
            invalid_accounts.append(
                f"{account}: {result.reason}"
            )

    if invalid_accounts:
        raise ValueError(
            "Ugyldige kontostrenge:\n"
            + "\n".join(invalid_accounts)
        )

    dimension_ids = find_kontostreng_ids(
        kontostrenge=unique_accounts
    )

    desired_lines = tuple(
        FakturaKonteringslinje(
            kontostreng=line["kontostreng"],
            bruttobeloeb=line["bruttobeloeb"],
            ydelsesmodtager=(
                line["ydelsesmodtager"]
            ),
            enhed=line["enhed"],
            faktura_afdeling=(
                line["faktura_afdeling"]
            ),
            posteringstekst=(
                line["posteringstekst"]
            ),
            kreditorkonto=(
                line["kreditorkonto"]
            ),
            ledger_dimension=(
                dimension_ids[
                    line["kontostreng"]
                ]
            ),
        )
        for line in normalized
    )

    existing_lines = (
        get_faktura_konteringslinjer(
            header_reference=reference,
            top=DEFAULT_TOP,
        )
    )

    _validate_existing_lines(
        existing_lines,
        reference,
    )

    existing_lines.sort(
        key=_existing_line_sort_key
    )

    existing_count = len(existing_lines)
    desired_count = len(desired_lines)
    reusable_count = min(
        existing_count,
        desired_count,
    )

    operations = []

    for index in range(reusable_count):
        operations.append(
            Konteringshandling(
                handling="try_existing",
                process_line_number=index + 1,
                rec_id_loc=_get_line_rec_id(
                    existing_lines[index]
                ),
                beskrivelse=(
                    "Forsøg eksisterende linje"
                ),
            )
        )

    if desired_count > existing_count:
        for index in range(
            existing_count,
            desired_count,
        ):
            operations.append(
                Konteringshandling(
                    handling="create_if_needed",
                    process_line_number=(
                        index + 1
                    ),
                    rec_id_loc=None,
                    beskrivelse=(
                        "Opret hvis ingen "
                        "brugbar linje findes"
                    ),
                )
            )

    if existing_count > desired_count:
        for index in range(
            desired_count,
            existing_count,
        ):
            operations.append(
                Konteringshandling(
                    handling="delete_if_unused",
                    process_line_number=None,
                    rec_id_loc=_get_line_rec_id(
                        existing_lines[index]
                    ),
                    beskrivelse=(
                        "Slet hvis linjen "
                        "ikke blev anvendt"
                    ),
                )
            )

    if existing_count == desired_count:
        strategy = "reuse_all"
    elif existing_count > desired_count:
        strategy = "reuse_and_delete"
    elif existing_count == 0:
        strategy = "create_all"
    else:
        strategy = "reuse_and_create"

    return FakturaKonteringsplan(
        header_reference=reference,
        strategi=strategy,
        eksisterende_linjer=tuple(
            dict(line)
            for line in existing_lines
        ),
        oenskede_linjer=desired_lines,
        handlinger=tuple(operations),
        ledger_dimension_ids=dict(
            dimension_ids
        ),
        eksisterende_totalbeloeb=(
            _sum_api_lines(existing_lines)
        ),
        oensket_totalbeloeb=sum(
            (
                line.bruttobeloeb
                for line in desired_lines
            ),
            Decimal("0"),
        ),
        cpr_numre_valideret=(
            cpr_numre_valideret
        ),
    )


def _execute_plan(
    plan: FakturaKonteringsplan,
) -> dict[str, Any]:
    """
    Udfør planen med kandidatbaseret matchning.

    En ønsket linje prøves på eksisterende
    kandidatlinjer, indtil en brugbar linje
    findes. Manglende linjer oprettes.
    """

    existing_lines = list(
        plan.eksisterende_linjer
    )

    desired_lines = list(
        plan.oenskede_linjer
    )

    assigned_ids: list[int] = []
    updated_ids: list[int] = []
    skipped_ids: list[int] = []
    rejected_ids: list[int] = []
    created_ids: list[int] = []
    deleted_ids: list[int] = []

    candidate_index = 0
    consecutive_rejections = 0

    try:
        for process_index, desired_line in enumerate(
            desired_lines,
            start=1,
        ):
            assigned = False

            while candidate_index < len(
                existing_lines
            ):
                candidate = existing_lines[
                    candidate_index
                ]

                candidate_index += 1

                rec_id = _get_line_rec_id(
                    candidate
                )

                invoice_line_number = (
                    candidate.get(
                        "InvoiceLineNumber"
                    )
                )

                try:
                    result = (
                        _update_line_with_retry(
                            rec_id_loc=rec_id,
                            desired_line=(
                                desired_line
                            ),
                            cpr_numre_valideret=(
                                plan
                                .cpr_numre_valideret
                            ),
                            process_line_number=(
                                process_index
                            ),
                            invoice_line_number=(
                                invoice_line_number
                            ),
                        )
                    )

                except UnusableInvoiceLineError as error:
                    rejected_ids.append(
                        rec_id
                    )

                    consecutive_rejections += 1

                    logger.warning(
                        "Afviser kandidatlinje. "
                        "Proceslinje=%s, "
                        "InvoiceLineNumber=%r, "
                        "RecIdLoc=%s. Fejl=%s",
                        process_index,
                        invoice_line_number,
                        rec_id,
                        error,
                    )

                    if (
                        consecutive_rejections
                        >= MAX_CONSECUTIVE_REJECTED_LINES
                    ):
                        raise RuntimeError(
                            "Konteringen stoppede, "
                            "fordi "
                            f"{consecutive_rejections} "
                            "kandidatlinjer i træk "
                            "ikke kunne opdateres. "
                            "Det kan være en generel "
                            "Prisme-fejl. "
                            "Seneste proceslinje: "
                            f"{process_index}. "
                            "InvoiceLineNumber: "
                            f"{invoice_line_number!r}. "
                            f"RecIdLoc: {rec_id}."
                        ) from error

                    continue

                consecutive_rejections = 0

                assigned_ids.append(
                    rec_id
                )

                if result == "skipped":
                    skipped_ids.append(
                        rec_id
                    )
                else:
                    updated_ids.append(
                        rec_id
                    )

                assigned = True
                break

            if assigned:
                continue

            known_ids = {
                _get_line_rec_id(line)
                for line in (
                    get_faktura_konteringslinjer(
                        header_reference=(
                            plan.header_reference
                        ),
                        top=DEFAULT_TOP,
                    )
                )
            }

            new_line = _create_line_safely(
                header_reference=(
                    plan.header_reference
                ),
                desired_line=desired_line,
                known_ids=known_ids,
            )

            new_rec_id = _get_line_rec_id(
                new_line
            )

            invoice_line_number = (
                new_line.get(
                    "InvoiceLineNumber"
                )
            )

            created_ids.append(
                new_rec_id
            )

            result = _update_line_with_retry(
                rec_id_loc=new_rec_id,
                desired_line=desired_line,
                cpr_numre_valideret=(
                    plan.cpr_numre_valideret
                ),
                process_line_number=(
                    process_index
                ),
                invoice_line_number=(
                    invoice_line_number
                ),
            )

            assigned_ids.append(
                new_rec_id
            )

            if result == "skipped":
                skipped_ids.append(
                    new_rec_id
                )
            else:
                updated_ids.append(
                    new_rec_id
                )

    except Exception:
        # Kun nyoprettede linjer rulles tilbage.
        # Eksisterende linjer slettes aldrig her.
        _rollback_created_lines(
            created_ids
        )

        raise

    _verify_assigned_lines(
        header_reference=(
            plan.header_reference
        ),
        assigned_ids=assigned_ids,
        desired_lines=desired_lines,
    )

    all_current_lines = (
        get_faktura_konteringslinjer(
            header_reference=(
                plan.header_reference
            ),
            top=DEFAULT_TOP,
        )
    )

    assigned_id_set = set(
        assigned_ids
    )

    lines_to_delete = [
        line
        for line in all_current_lines
        if _get_line_rec_id(line)
        not in assigned_id_set
    ]

    lines_to_delete.sort(
        key=_existing_line_sort_key
    )

    for delete_number, line in enumerate(
        lines_to_delete,
        start=1,
    ):
        rec_id = _get_line_rec_id(
            line
        )

        invoice_line_number = line.get(
            "InvoiceLineNumber"
        )

        _delete_line_with_retry(
            rec_id_loc=rec_id,
            invoice_line_number=(
                invoice_line_number
            ),
            delete_number=delete_number,
        )

        deleted_ids.append(
            rec_id
        )

    final_lines = _wait_for_line_count(
        header_reference=(
            plan.header_reference
        ),
        expected_count=len(
            desired_lines
        ),
    )

    _verify_assigned_lines(
        header_reference=(
            plan.header_reference
        ),
        assigned_ids=assigned_ids,
        desired_lines=desired_lines,
        supplied_lines=final_lines,
    )

    final_total = _sum_api_lines(
        final_lines
    )

    if final_total != plan.oensket_totalbeloeb:
        raise RuntimeError(
            "Slutbeløbet matcher ikke planen. "
            f"Forventet: "
            f"{plan.oensket_totalbeloeb}. "
            f"Fundet: {final_total}."
        )

    result = {
        "success": True,
        "strategy": plan.strategi,
        "header_reference": (
            plan.header_reference
        ),
        "existing_count_before": len(
            existing_lines
        ),
        "desired_count": len(
            desired_lines
        ),
        "final_count": len(
            final_lines
        ),
        "total_gross_amount": final_total,
        "assigned_rec_ids": assigned_ids,
        "created_rec_ids": created_ids,
        "updated_rec_ids": updated_ids,
        "skipped_rec_ids": skipped_ids,
        "rejected_rec_ids": rejected_ids,
        "deleted_rec_ids": deleted_ids,
        "final_lines": final_lines,
    }

    _print_result_summary(
        result
    )

    return result

def _print_result_summary(
    result: dict[str, Any],
) -> None:
    """Udskriv et kort konteringsresultat."""

    print()
    print("=" * 70)
    print("KONTERING GENNEMFØRT")
    print("=" * 70)
    print(
        "Strategi:",
        result["strategy"],
    )
    print(
        "Antal linjer før:",
        result["existing_count_before"],
    )
    print(
        "Antal linjer efter:",
        result["final_count"],
    )
    print(
        "Samlet bruttobeløb:",
        result["total_gross_amount"],
    )
    print(
        "Opdaterede linjer:",
        len(
            result["updated_rec_ids"]
        ),
    )
    print(
        "Allerede korrekte linjer:",
        len(
            result["skipped_rec_ids"]
        ),
    )
    print(
        "Afviste kandidatlinjer:",
        len(
            result["rejected_rec_ids"]
        ),
    )
    print(
        "Oprettede linjer:",
        len(
            result["created_rec_ids"]
        ),
    )
    print(
        "Slettede linjer:",
        len(
            result["deleted_rec_ids"]
        ),
    )

    rejected_ids = result.get(
        "rejected_rec_ids",
        [],
    )

    if rejected_ids:
        print(
            "Afviste RecIdLoc-værdier:",
            rejected_ids,
        )

    print("=" * 70)
    print()


def _update_line_with_retry(
    rec_id_loc: int,
    desired_line: FakturaKonteringslinje,
    cpr_numre_valideret: bool,
    process_line_number: int,
    invoice_line_number: Any,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    delay_seconds: float = (
        DEFAULT_RETRY_DELAY_SECONDS
    ),
) -> str:
    """
    Kontrollér og PATCH én kandidatlinje.

    Returnerer:
        skipped:
            Linjen var allerede korrekt.

        updated:
            Linjen blev opdateret.

    Rejser:
        UnusableInvoiceLineError:
            Linjen kan ikke PATCH'es.
    """

    rec_id = _validate_positive_integer(
        rec_id_loc,
        "rec_id_loc",
    )

    if (
        desired_line.ydelsesmodtager
        and cpr_numre_valideret is not True
    ):
        raise ValueError(
            "CPR-kontrol er ikke bekræftet."
        )

    endpoint = _build_line_endpoint(
        rec_id
    )

    body = _build_update_body(
        rec_id,
        desired_line,
    )

    last_error = None

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        actual_before = _get_line(
            rec_id
        )

        if actual_before is None:
            raise UnusableInvoiceLineError(
                "Linjen findes ikke før PATCH. "
                f"Proceslinje: "
                f"{process_line_number}. "
                "InvoiceLineNumber: "
                f"{invoice_line_number!r}. "
                f"RecIdLoc: {rec_id}."
            )

        mismatches_before = (
            _get_line_mismatches(
                actual_before,
                desired_line,
            )
        )

        if not mismatches_before:
            return "skipped"

        try:
            result = patch(
                endpoint,
                body,
            )

            if result is not True:
                raise RuntimeError(
                    "PATCH returnerede: "
                    f"{result!r}"
                )

        except PrismeApiError as error:
            last_error = error

            if _wait_for_line_values(
                rec_id,
                desired_line,
            ):
                return "updated"

            status_code = _get_error_status(
                error
            )

            if status_code not in (
                TRANSIENT_STATUS_CODES
            ):
                raise RuntimeError(
                    "Prisme afviste PATCH "
                    "permanent. "
                    f"Proceslinje: "
                    f"{process_line_number}. "
                    "InvoiceLineNumber: "
                    f"{invoice_line_number!r}. "
                    f"RecIdLoc: {rec_id}. "
                    f"HTTP-status: "
                    f"{status_code!r}. "
                    "Forskelle: "
                    + "; ".join(
                        mismatches_before
                    )
                    + ". API-fejl: "
                    + repr(error)
                ) from error

        except RuntimeError as error:
            last_error = error

            if _wait_for_line_values(
                rec_id,
                desired_line,
            ):
                return "updated"

        else:
            if _wait_for_line_values(
                rec_id,
                desired_line,
            ):
                return "updated"

            last_error = RuntimeError(
                "PATCH gav succes, men "
                "værdierne matchede ikke."
            )

        if attempt < max_attempts:
            time.sleep(
                delay_seconds
            )

    final_line = _get_line(
        rec_id
    )

    if final_line is None:
        final_mismatches = [
            "Linjen kan ikke hentes"
        ]
    else:
        final_mismatches = (
            _get_line_mismatches(
                final_line,
                desired_line,
            )
        )

    raise UnusableInvoiceLineError(
        "Kandidatlinjen kunne ikke "
        "opdateres. "
        f"Proceslinje: "
        f"{process_line_number}. "
        "InvoiceLineNumber: "
        f"{invoice_line_number!r}. "
        f"RecIdLoc: {rec_id}. "
        f"Forsøg: {max_attempts}. "
        "Resterende forskelle: "
        + "; ".join(final_mismatches)
        + ". Sidste fejl: "
        + repr(last_error)
    ) from last_error


def _delete_line_with_retry(
    rec_id_loc: int,
    invoice_line_number: Any,
    delete_number: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> None:
    """DELETE én linje med kontrol."""

    rec_id = _validate_positive_integer(
        rec_id_loc,
        "rec_id_loc",
    )

    endpoint = _build_line_endpoint(
        rec_id
    )

    last_error = None

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        if _get_line(rec_id) is None:
            return

        try:
            result = delete(
                endpoint
            )

            if result is not True:
                raise RuntimeError(
                    "DELETE returnerede: "
                    f"{result!r}"
                )

        except PrismeApiError as error:
            last_error = error

            if _wait_for_deleted_line(
                rec_id
            ):
                return

            status_code = _get_error_status(
                error
            )

            if status_code == 404:
                return

            if status_code not in (
                TRANSIENT_STATUS_CODES
            ):
                raise RuntimeError(
                    "Prisme afviste DELETE. "
                    f"Sletningsnummer: "
                    f"{delete_number}. "
                    "InvoiceLineNumber: "
                    f"{invoice_line_number!r}. "
                    f"RecIdLoc: {rec_id}. "
                    f"HTTP-status: "
                    f"{status_code!r}. "
                    f"API-fejl: {error!r}."
                ) from error

        except RuntimeError as error:
            last_error = error

        if _wait_for_deleted_line(
            rec_id
        ):
            return

        if attempt < max_attempts:
            time.sleep(
                DEFAULT_RETRY_DELAY_SECONDS
            )

    raise RuntimeError(
        "Linjen kunne ikke slettes. "
        f"Sletningsnummer: {delete_number}. "
        "InvoiceLineNumber: "
        f"{invoice_line_number!r}. "
        f"RecIdLoc: {rec_id}. "
        f"Sidste fejl: {last_error!r}."
    ) from last_error


def _create_line_safely(
    header_reference: str,
    desired_line: FakturaKonteringslinje,
    known_ids: set[int],
) -> dict[str, Any]:
    """Opret præcis én blank linje."""

    body = _build_create_body(
        header_reference,
        desired_line,
    )

    try:
        post(
            CREATE_LINE_ENDPOINT,
            body,
        )

    except PrismeApiError as error:
        status_code = _get_error_status(
            error
        )

        if status_code not in (
            TRANSIENT_STATUS_CODES
        ):
            raise

    for attempt in range(
        1,
        DEFAULT_CONTROL_ATTEMPTS + 1,
    ):
        current_lines = (
            get_faktura_konteringslinjer(
                header_reference=(
                    header_reference
                ),
                top=DEFAULT_TOP,
            )
        )

        new_lines = [
            line
            for line in current_lines
            if _get_line_rec_id(line)
            not in known_ids
        ]

        if len(new_lines) == 1:
            return new_lines[0]

        if len(new_lines) > 1:
            raise RuntimeError(
                "Flere nye linjer blev fundet "
                "efter ét POST-kald."
            )

        if (
            attempt
            < DEFAULT_CONTROL_ATTEMPTS
        ):
            time.sleep(
                DEFAULT_CONTROL_DELAY_SECONDS
            )

    raise RuntimeError(
        "Den nye linje kunne ikke findes."
    )


def _build_update_body(
    rec_id: int,
    desired_line: FakturaKonteringslinje,
) -> dict[str, Any]:
    """Byg PATCH-body."""

    return {
        "RecIdLoc": rec_id,
        "LedgerDimension": (
            desired_line.ledger_dimension
        ),
        "GrossAmount": (
            _decimal_to_json_number(
                desired_line.bruttobeloeb
            )
        ),
        "Description": (
            desired_line.posteringstekst
        ),
        "Beneficiary": (
            desired_line.ydelsesmodtager
        ),
    }


def _build_create_body(
    header_reference: str,
    desired_line: FakturaKonteringslinje,
) -> dict[str, Any]:
    """Byg POST-body til blank linje."""

    department = _validate_department(
        desired_line.faktura_afdeling
    )

    vendor = _require_text(
        desired_line.kreditorkonto,
        "kreditorkonto",
    )

    return {
        "dataAreaId": "had",
        "HeaderReference": header_reference,
        "InvoiceLineNumber": 0,
        "Tax1099SClosingDate": (
            "1900-01-01T12:00:00Z"
        ),
        "PriceUnit": 1,
        "DimensionDisplayValue": (
            department + "----"
        ),
        "VendorAccount": vendor,
        "InvoiceAccount": vendor,
        "UnitPrice": 0,
        "LineDescription": "",
        "ItemNumber": "",
        "ItemName": "",
        "ProcurementCategoryHierarchyName": (
            "Indkøbskategorihieraki"
        ),
        "Ordering": "None",
        "Unit": desired_line.enhed,
        "NetAmount": 0,
        "LineType": "Standard",
        "VendorInvoiceLineReviewStatus": (
            "Draft"
        ),
        "ItemSalesTax": "Im-moms",
        "SalesTaxGroup": "DK-moms",
        "Amount": 0,
        "DeliveryName": (
            "Haderslev Kommune"
        ),
        "DimensionNumber": "AllBlank",
        "ReceiveNow": 1,
        "OverrideSalesTax": "No",
        "ProcurementCategoryName": (
            "Standard vare"
        ),
        "Currency": "DKK",
        "CloseForReceipt": "No",
        "ChangeQuantityManually": "No",
    }


def _rollback_created_lines(
    created_ids: list[int],
) -> None:
    """Forsøg at fjerne nye linjer."""

    for rec_id in created_ids:
        if _get_line(rec_id) is None:
            continue

        try:
            delete(
                _build_line_endpoint(rec_id)
            )
        except Exception:
            logger.exception(
                "Rollback fejlede for %s",
                rec_id,
            )


def _verify_assigned_lines(
    header_reference: str,
    assigned_ids: list[int],
    desired_lines: list[
        FakturaKonteringslinje
    ],
    supplied_lines: list[
        dict[str, Any]
    ] | None = None,
) -> None:
    """Verificér alle tildelte linjer."""

    lines = supplied_lines

    if lines is None:
        lines = get_faktura_konteringslinjer(
            header_reference=(
                header_reference
            ),
            top=DEFAULT_TOP,
        )

    if len(assigned_ids) != len(
        desired_lines
    ):
        raise RuntimeError(
            "Antallet af tildelte linjer "
            "matcher ikke inputtet."
        )

    for index, desired_line in enumerate(
        desired_lines
    ):
        rec_id = assigned_ids[index]

        actual = _find_line_by_rec_id(
            lines,
            rec_id,
        )

        try:
            _verify_line_matches(
                actual,
                desired_line,
            )
        except RuntimeError as error:
            raise RuntimeError(
                "Verificering fejlede ved "
                f"proceslinje {index + 1}. "
                "InvoiceLineNumber: "
                f"{actual.get('InvoiceLineNumber')!r}. "
                f"RecIdLoc: {rec_id}. "
                f"Fejl: {error}"
            ) from error


def _get_line_mismatches(
    actual: dict[str, Any],
    desired: FakturaKonteringslinje,
) -> list:
    """Find konkrete dataforskelle."""

    differences = []

    actual_dimension = int(
        actual.get(
            "LedgerDimension",
            0,
        )
        or 0
    )

    if (
        actual_dimension
        != desired.ledger_dimension
    ):
        differences.append(
            "LedgerDimension: "
            f"forventet "
            f"{desired.ledger_dimension!r}, "
            f"fundet {actual_dimension!r}"
        )

    actual_amount = _to_decimal(
        actual.get(
            "GrossAmount",
            0,
        )
        or 0
    )

    if actual_amount != desired.bruttobeloeb:
        differences.append(
            "GrossAmount: "
            f"forventet "
            f"{desired.bruttobeloeb!r}, "
            f"fundet {actual_amount!r}"
        )

    actual_description = str(
        actual.get(
            "Description",
            "",
        )
        or ""
    ).strip()

    if (
        actual_description
        != desired.posteringstekst
    ):
        differences.append(
            "Description: "
            f"forventet "
            f"{desired.posteringstekst!r}, "
            f"fundet {actual_description!r}"
        )

    actual_beneficiary = (
        _normalize_compare_text(
            actual.get(
                "Beneficiary",
                "",
            )
        )
    )

    desired_beneficiary = (
        _normalize_compare_text(
            desired.ydelsesmodtager
        )
    )

    if (
        actual_beneficiary
        != desired_beneficiary
    ):
        differences.append(
            "Beneficiary: "
            f"forventet "
            f"{desired_beneficiary!r}, "
            f"fundet {actual_beneficiary!r}"
        )

    return differences


def _verify_line_matches(
    actual: dict[str, Any],
    desired: FakturaKonteringslinje,
) -> None:
    """Verificér én linje."""

    differences = _get_line_mismatches(
        actual,
        desired,
    )

    if differences:
        raise RuntimeError(
            "; ".join(differences)
        )


def _wait_for_line_values(
    rec_id: int,
    desired: FakturaKonteringslinje,
) -> bool:
    """Vent på PATCH-resultatet."""

    for attempt in range(1, 4):
        actual = _get_line(rec_id)

        if (
            actual is not None
            and not _get_line_mismatches(
                actual,
                desired,
            )
        ):
            return True

        if attempt < 3:
            time.sleep(1.0)

    return False


def _wait_for_deleted_line(
    rec_id: int,
) -> bool:
    """Vent på DELETE-resultatet."""

    for attempt in range(1, 4):
        if _get_line(rec_id) is None:
            return True

        if attempt < 3:
            time.sleep(1.0)

    return False


def _get_line(
    rec_id: int,
) -> dict[str, Any] | None:
    """Hent én konkret linje."""

    try:
        response = get(
            _build_line_endpoint(rec_id)
        )
    except PrismeApiError as error:
        if _get_error_status(error) == 404:
            return None
        raise

    if response is None:
        return None

    if isinstance(response, dict):
        return dict(response)

    if (
        isinstance(response, list)
        and len(response) == 1
    ):
        return dict(response[0])

    if (
        isinstance(response, list)
        and not response
    ):
        return None

    raise RuntimeError(
        "Uventet svar ved linjeopslag."
    )


def _build_line_endpoint(
    rec_id: int,
) -> str:
    """Byg endpoint til én linje."""

    return (
        f"{LINE_ENDPOINT}"
        f"({_validate_positive_integer(rec_id, 'rec_id')})"
    )


def _normalize_lines(
    lines: list[dict[str, Any]],
    cpr_confirmed: bool,
) -> list[dict[str, Any]]:
    """Normalisér procesinputtet."""

    if not isinstance(lines, list):
        raise TypeError(
            "konteringslinjer skal være "
            "en liste."
        )

    if not lines:
        raise ValueError(
            "Der skal være mindst én linje."
        )

    if not isinstance(cpr_confirmed, bool):
        raise TypeError(
            "cpr_numre_valideret skal være "
            "True eller False."
        )

    result = []

    for number, line in enumerate(
        lines,
        start=1,
    ):
        if not isinstance(line, dict):
            raise TypeError(
                f"Linje {number} skal være "
                "en dictionary."
            )

        try:
            normalized = {
                "kontostreng": _require_text(
                    _first_value(
                        line,
                        "kontostreng",
                        "Kontostreng",
                    ),
                    "kontostreng",
                ),
                "bruttobeloeb": _to_decimal(
                    _first_value(
                        line,
                        "bruttobeloeb",
                        "Bruttobeløb",
                        "GrossAmount",
                    )
                ),
                "ydelsesmodtager": (
                    _normalize_beneficiary(
                        _first_value(
                            line,
                            "ydelsesmodtager",
                            "Ydelsesmodtager",
                            "Beneficiary",
                            default="",
                        )
                    )
                ),
                "enhed": _optional_text(
                    _first_value(
                        line,
                        "enhed",
                        "Enhed",
                        "Unit",
                        default=DEFAULT_UNIT,
                    ),
                    DEFAULT_UNIT,
                ),
                "faktura_afdeling": (
                    _validate_department(
                        _first_value(
                            line,
                            "faktura_afdeling",
                            (
                                "Afdeling fakturaen "
                                "er tilknyttet"
                            ),
                        )
                    )
                ),
                "posteringstekst": (
                    _optional_text(
                        _first_value(
                            line,
                            "posteringstekst",
                            "Posteringstekst",
                            "Description",
                            default="",
                        ),
                        "",
                    )
                ),
                "kreditorkonto": _require_text(
                    _first_value(
                        line,
                        "kreditorkonto",
                        "Kreditorkonto",
                        "VendorAccount",
                    ),
                    "kreditorkonto",
                ),
            }
        except Exception as error:
            raise ValueError(
                f"Linje {number} er ugyldig: "
                f"{error}"
            ) from error

        result.append(normalized)

    if (
        any(
            line["ydelsesmodtager"]
            for line in result
        )
        and cpr_confirmed is not True
    ):
        raise ValueError(
            "Alle CPR-numre skal være "
            "valideret via Datafordeleren."
        )

    return result


def _validate_existing_lines(
    lines: list[dict[str, Any]],
    reference: str,
) -> None:
    """Kontrollér eksisterende linjer."""

    seen = set()

    for number, line in enumerate(
        lines,
        start=1,
    ):
        if str(
            line.get(
                "HeaderReference",
                "",
            )
            or ""
        ).strip() != reference:
            raise ValueError(
                f"Linje {number} har forkert "
                "HeaderReference."
            )

        rec_id = _get_line_rec_id(line)

        if rec_id in seen:
            raise ValueError(
                f"Dubleret RecIdLoc: {rec_id}."
            )

        seen.add(rec_id)


def _wait_for_line_count(
    header_reference: str,
    expected_count: int,
) -> list[dict[str, Any]]:
    """Vent på forventet antal linjer."""

    last_lines = []

    for attempt in range(
        1,
        DEFAULT_CONTROL_ATTEMPTS + 1,
    ):
        last_lines = (
            get_faktura_konteringslinjer(
                header_reference=(
                    header_reference
                ),
                top=DEFAULT_TOP,
            )
        )

        if len(last_lines) == expected_count:
            return last_lines

        if (
            attempt
            < DEFAULT_CONTROL_ATTEMPTS
        ):
            time.sleep(
                DEFAULT_CONTROL_DELAY_SECONDS
            )

    raise RuntimeError(
        "Forkert slutantal. "
        f"Forventet: {expected_count}. "
        f"Fundet: {len(last_lines)}."
    )


def _find_line_by_rec_id(
    lines: list[dict[str, Any]],
    rec_id: int,
) -> dict[str, Any]:
    """Find én linje via RecIdLoc."""

    matches = [
        line
        for line in lines
        if int(
            line.get(
                "RecIdLoc",
                0,
            )
            or 0
        ) == rec_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"RecIdLoc {rec_id} blev fundet "
            f"{len(matches)} gange."
        )

    return matches[0]


def _existing_line_sort_key(
    line: dict[str, Any],
) -> tuple[Decimal, int]:
    """Byg stabil sorteringsnøgle."""

    return (
        _to_decimal(
            line.get(
                "InvoiceLineNumber",
                0,
            )
            or 0
        ),
        _get_line_rec_id(line),
    )


def _get_line_rec_id(
    line: dict[str, Any],
) -> int:
    """Hent linjens RecIdLoc."""

    return _validate_positive_integer(
        line.get("RecIdLoc"),
        "RecIdLoc",
    )


def _sum_api_lines(
    lines: list[dict[str, Any]]
    | tuple[dict[str, Any], ...],
) -> Decimal:
    """Beregn samlet GrossAmount."""

    return sum(
        (
            _to_decimal(
                line.get(
                    "GrossAmount",
                    0,
                )
                or 0
            )
            for line in lines
        ),
        Decimal("0"),
    )


def _normalize_control_date(
    value: date | datetime | None,
) -> date:
    """Normalisér kontroldato."""

    if value is None:
        return date.today()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise TypeError(
        "kontroldato har forkert type."
    )


def _normalize_beneficiary(
    value: Any,
) -> str:
    """Normalisér CPR-input."""

    result = _normalize_compare_text(value)

    if not result:
        return ""

    if (
        not result.isdigit()
        or len(result) != 10
    ):
        raise ValueError(
            "ydelsesmodtager skal have "
            "præcis 10 cifre."
        )

    return result


def _normalize_compare_text(
    value: Any,
) -> str:
    """Normalisér tekst til sammenligning."""

    if value is None:
        return ""

    return str(value).strip().replace(
        "-",
        "",
    ).replace(
        " ",
        "",
    )


def _validate_department(
    value: Any,
) -> str:
    """Kontrollér afdeling."""

    result = _require_text(
        value,
        "faktura_afdeling",
    )

    if (
        len(result) != 12
        or not result.isdigit()
    ):
        raise ValueError(
            "faktura_afdeling skal have "
            "præcis 12 cifre."
        )

    return result


def _first_value(
    data: dict[str, Any],
    *names: str,
    default: Any = None,
) -> Any:
    """Hent første eksisterende felt."""

    for name in names:
        if name in data:
            return data[name]

    return default


def _require_text(
    value: Any,
    name: str,
) -> str:
    """Kontrollér obligatorisk tekst."""

    text = str(
        value
        if value is not None
        else ""
    ).strip()

    if not text:
        raise ValueError(
            f"{name} skal udfyldes."
        )

    return text


def _optional_text(
    value: Any,
    default: str,
) -> str:
    """Normalisér valgfri tekst."""

    text = str(
        value
        if value is not None
        else ""
    ).strip()

    return text or default


def _validate_positive_integer(
    value: Any,
    name: str,
) -> int:
    """Kontrollér positivt heltal."""

    if isinstance(value, bool):
        raise TypeError(
            f"{name} er ugyldigt."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise TypeError(
            f"{name} er ugyldigt."
        ) from error

    if result <= 0:
        raise ValueError(
            f"{name} skal være større end 0."
        )

    return result


def _to_decimal(
    value: Any,
) -> Decimal:
    """Konvertér beløb til Decimal."""

    if isinstance(value, Decimal):
        return value

    if isinstance(value, bool):
        raise InvalidOperation(
            "Bool er ikke et beløb."
        )

    text = str(
        value
        if value is not None
        else ""
    ).strip().replace(
        " ",
        "",
    )

    if not text:
        raise InvalidOperation(
            "Beløbet mangler."
        )

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(
                ".",
                "",
            ).replace(
                ",",
                ".",
            )
        else:
            text = text.replace(
                ",",
                "",
            )
    elif "," in text:
        text = text.replace(
            ",",
            ".",
        )

    return Decimal(text)


def _decimal_to_json_number(
    value: Decimal,
) -> int | float:
    """Konvertér Decimal til JSON-tal."""

    if value == value.to_integral_value():
        return int(value)

    return float(value)


def _get_error_status(
    error: BaseException,
) -> int | None:
    """Hent HTTP-status hvis muligt."""

    for name in (
        "status_code",
        "status",
        "http_status",
    ):
        value = getattr(
            error,
            name,
            None,
        )

        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass

    response = getattr(
        error,
        "response",
        None,
    )

    value = getattr(
        response,
        "status_code",
        None,
    )

    try:
        if value is not None:
            return int(value)
    except (TypeError, ValueError):
        pass

    return None