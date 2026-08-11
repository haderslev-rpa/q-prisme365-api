"""Rigtig test af kandidatbaseret fakturakontering."""

import logging
from decimal import Decimal

from q_prisme365_api.functionality.faktura_kontering import (
    konter_faktura,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s: "
        "%(message)s"
    ),
)


# ------------------------------------------------------------
# SIKKERHED
# ------------------------------------------------------------

UDFOER_SYNKRONISERING = True

SIKKERHEDSTEKST = "KONTER 50 LINJER PÅ 000682112"

FORVENTET_SIKKERHEDSTEKST = (
    "KONTER 50 LINJER PÅ 000682112"
)


# ------------------------------------------------------------
# TESTFAKTURA
# ------------------------------------------------------------

HEADER_REFERENCE = "000682112"

# Ret denne værdi, hvis antallet har ændret sig.
FORVENTET_ANTAL_EKSISTERENDE = 577

ANTAL_OENSKEDE_LINJER = 50


# ------------------------------------------------------------
# KONTERING
# ------------------------------------------------------------

OENSKET_TOTALBELOEB = Decimal(
    "50768.60"
)

STANDARD_BELOEB = Decimal(
    "1000.00"
)

KONTOSTRENG = (
    "100201010000-645511002-10021-40-"
)

FAKTURA_AFDELING = "180123000000"
KREDITORKONTO = "000065"
ENHED = "STK"
YDELSESMODTAGER = "3112999999"

CPR_NUMRE_VALIDERET = True


def main():
    """Planlæg og eventuelt udfør testen."""

    lines = build_lines()

    plan = konter_faktura(
        header_reference=HEADER_REFERENCE,
        konteringslinjer=lines,
        cpr_numre_valideret=(
            CPR_NUMRE_VALIDERET
        ),
        udfoer=False,
    )

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print("Strategi:", plan.strategi)
    print(
        "Eksisterende linjer:",
        len(plan.eksisterende_linjer),
    )
    print(
        "Ønskede linjer:",
        len(plan.oenskede_linjer),
    )
    print(
        "Planlagte handlinger:",
        len(plan.handlinger),
    )
    print(
        "Ønsket totalbeløb:",
        plan.oensket_totalbeloeb,
    )

    validate_plan(plan)

    if not UDFOER_SYNKRONISERING:
        print()
        print("Ingen ændringer blev udført.")
        return

    if (
        SIKKERHEDSTEKST
        != FORVENTET_SIKKERHEDSTEKST
    ):
        raise ValueError(
            "Forkert sikkerhedstekst. "
            f"Skriv: "
            f"{FORVENTET_SIKKERHEDSTEKST!r}"
        )

    result = konter_faktura(
        header_reference=HEADER_REFERENCE,
        konteringslinjer=lines,
        cpr_numre_valideret=(
            CPR_NUMRE_VALIDERET
        ),
    )

    validate_result(result)

    print()
    print("=" * 70)
    print("SYNKRONISERING GENNEMFØRT")
    print("=" * 70)
    print(
        "Antal før:",
        result["existing_count_before"],
    )
    print(
        "Antal efter:",
        result["final_count"],
    )
    print(
        "Opdaterede:",
        len(result["updated_rec_ids"]),
    )
    print(
        "Allerede korrekte:",
        len(result["skipped_rec_ids"]),
    )
    print(
        "Afviste kandidatlinjer:",
        len(result["rejected_rec_ids"]),
    )
    print(
        "Afviste RecIdLoc:",
        result["rejected_rec_ids"],
    )
    print(
        "Oprettede:",
        len(result["created_rec_ids"]),
    )
    print(
        "Slettede:",
        len(result["deleted_rec_ids"]),
    )
    print(
        "Slutbeløb:",
        result["total_gross_amount"],
    )


def build_lines():
    """Byg 50 ønskede linjer."""

    last_amount = (
        OENSKET_TOTALBELOEB
        - (
            STANDARD_BELOEB
            * (
                ANTAL_OENSKEDE_LINJER
                - 1
            )
        )
    )

    if last_amount <= Decimal("0"):
        raise ValueError(
            "Sidste beløb er ikke positivt."
        )

    lines = []

    for number in range(
        1,
        ANTAL_OENSKEDE_LINJER + 1,
    ):
        amount = (
            STANDARD_BELOEB
            if number
            < ANTAL_OENSKEDE_LINJER
            else last_amount
        )

        lines.append(
            {
                "kontostreng": KONTOSTRENG,
                "bruttobeloeb": amount,
                "ydelsesmodtager": (
                    YDELSESMODTAGER
                ),
                "enhed": ENHED,
                "faktura_afdeling": (
                    FAKTURA_AFDELING
                ),
                "posteringstekst": (
                    "Python kontering "
                    f"linje {number:02d}"
                ),
                "kreditorkonto": (
                    KREDITORKONTO
                ),
            }
        )

    total = sum(
        (
            line["bruttobeloeb"]
            for line in lines
        ),
        Decimal("0"),
    )

    if total != OENSKET_TOTALBELOEB:
        raise ValueError(
            f"Forkert inputtotal: {total}."
        )

    return lines


def validate_plan(plan):
    """Kontrollér planen."""

    if len(
        plan.eksisterende_linjer
    ) != FORVENTET_ANTAL_EKSISTERENDE:
        raise ValueError(
            "Antallet af eksisterende linjer "
            "har ændret sig. "
            f"Forventet: "
            f"{FORVENTET_ANTAL_EKSISTERENDE}. "
            f"Fundet: "
            f"{len(plan.eksisterende_linjer)}."
        )

    if len(
        plan.oenskede_linjer
    ) != ANTAL_OENSKEDE_LINJER:
        raise ValueError(
            "Forkert antal ønskede linjer."
        )

    if (
        plan.oensket_totalbeloeb
        != OENSKET_TOTALBELOEB
    ):
        raise ValueError(
            "Forkert ønsket totalbeløb."
        )

    if plan.strategi != "reuse_and_delete":
        raise ValueError(
            "Forventede strategien "
            "reuse_and_delete, men fandt "
            f"{plan.strategi!r}."
        )


def validate_result(result):
    """Kontrollér slutresultatet."""

    if result.get("success") is not True:
        raise RuntimeError(
            "Resultatet mangler success=True."
        )

    if (
        result.get("final_count")
        != ANTAL_OENSKEDE_LINJER
    ):
        raise RuntimeError(
            "Forkert antal slutlinjer."
        )

    if (
        result.get(
            "total_gross_amount"
        )
        != OENSKET_TOTALBELOEB
    ):
        raise RuntimeError(
            "Forkert samlet slutbeløb."
        )

    assigned = result.get(
        "assigned_rec_ids",
        [],
    )

    if len(assigned) != ANTAL_OENSKEDE_LINJER:
        raise RuntimeError(
            "Forkert antal tildelte linjer."
        )

    if len(set(assigned)) != len(assigned):
        raise RuntimeError(
            "Et RecIdLoc blev tildelt mere "
            "end én ønsket linje."
        )


if __name__ == "__main__":
    main()