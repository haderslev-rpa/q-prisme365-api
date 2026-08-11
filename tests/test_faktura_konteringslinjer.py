"""Live-test af fakturaens konteringslinjer."""

import logging
from decimal import Decimal
from decimal import InvalidOperation
from pprint import pprint

from q_prisme365_api.functionality.fakturaer import (
    get_faktura_konteringslinjer,
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
# TESTDATA
# ------------------------------------------------------------

HEADER_REFERENCE = "000682112"

# Fakturaen har cirka 390 linjer.
TOP = 10000

# Begræns udskriften, så terminalen ikke
# viser samtlige konteringslinjer.
VIS_ANTAL_FOERSTE_LINJER = 1
VIS_ANTAL_SIDSTE_LINJER = 1


def main():
    """Hent og vis et sammendrag af linjerne."""

    print()
    print("=" * 70)
    print("LIVE-TEST AF FAKTURAENS KONTERINGSLINJER")
    print("=" * 70)
    print()
    print("HeaderReference:", HEADER_REFERENCE)
    print("Top:", TOP)
    print()

    konteringslinjer = (
        get_faktura_konteringslinjer(
            header_reference=HEADER_REFERENCE,
            top=TOP,
        )
    )

    antal_linjer = len(
        konteringslinjer
    )

    print(
        "Antal konteringslinjer:",
        antal_linjer,
    )

    if not konteringslinjer:
        print()
        print(
            "Der blev ikke fundet nogen "
            "konteringslinjer."
        )
        return

    rec_ids = hent_unikke_rec_ids(
        konteringslinjer
    )

    total_beloeb = beregn_total_beloeb(
        konteringslinjer
    )

    invoice_line_numbers = (
        hent_invoice_line_numbers(
            konteringslinjer
        )
    )

    print()
    print("=" * 70)
    print("SAMMENDRAG")
    print("=" * 70)
    print()

    print(
        "Antal unikke RecIdLoc:",
        len(rec_ids),
    )

    print(
        "Samlet GrossAmount:",
        total_beloeb,
    )

    if invoice_line_numbers:
        print(
            "Laveste InvoiceLineNumber:",
            min(invoice_line_numbers),
        )

        print(
            "Højeste InvoiceLineNumber:",
            max(invoice_line_numbers),
        )

    antal_dubletter = (
        antal_linjer
        - len(rec_ids)
    )

    print(
        "Antal dublerede RecIdLoc:",
        antal_dubletter,
    )

    vis_udvalgte_linjer(
        konteringslinjer
    )


def hent_unikke_rec_ids(
    konteringslinjer,
):
    """Hent alle unikke RecIdLoc-værdier."""

    rec_ids = set()

    for linjenummer, linje in enumerate(
        konteringslinjer,
        start=1,
    ):
        rec_id = linje.get(
            "RecIdLoc"
        )

        if rec_id in (
            None,
            "",
            0,
            "0",
        ):
            print(
                "Advarsel: Konteringslinje "
                f"{linjenummer} mangler "
                "RecIdLoc."
            )
            continue

        try:
            rec_id = int(
                rec_id
            )
        except (TypeError, ValueError):
            print(
                "Advarsel: Konteringslinje "
                f"{linjenummer} har ugyldigt "
                f"RecIdLoc: {rec_id!r}."
            )
            continue

        rec_ids.add(
            rec_id
        )

    return rec_ids


def beregn_total_beloeb(
    konteringslinjer,
):
    """Beregn summen af GrossAmount."""

    total_beloeb = Decimal("0")

    for linjenummer, linje in enumerate(
        konteringslinjer,
        start=1,
    ):
        raw_amount = linje.get(
            "GrossAmount",
            0,
        )

        if raw_amount in (
            None,
            "",
        ):
            raw_amount = 0

        try:
            amount = konverter_til_decimal(
                raw_amount
            )
        except ValueError as error:
            raise ValueError(
                "GrossAmount er ugyldigt på "
                f"konteringslinje {linjenummer}. "
                f"Værdi: {raw_amount!r}."
            ) from error

        total_beloeb += amount

    return total_beloeb


def konverter_til_decimal(
    value,
):
    """Konvertér dansk eller internationalt beløb."""

    if isinstance(
        value,
        Decimal,
    ):
        return value

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Bool kan ikke bruges som beløb."
        )

    text_value = str(
        value
    ).strip()

    text_value = text_value.replace(
        " ",
        "",
    )

    if not text_value:
        return Decimal("0")

    indeholder_komma = (
        "," in text_value
    )

    indeholder_punktum = (
        "." in text_value
    )

    if (
        indeholder_komma
        and indeholder_punktum
    ):
        sidste_komma = text_value.rfind(
            ","
        )

        sidste_punktum = text_value.rfind(
            "."
        )

        if sidste_komma > sidste_punktum:
            text_value = text_value.replace(
                ".",
                "",
            )

            text_value = text_value.replace(
                ",",
                ".",
            )
        else:
            text_value = text_value.replace(
                ",",
                "",
            )

    elif indeholder_komma:
        text_value = text_value.replace(
            ",",
            ".",
        )

    try:
        return Decimal(
            text_value
        )
    except InvalidOperation as error:
        raise ValueError(
            f"Ugyldigt beløb: {value!r}."
        ) from error


def hent_invoice_line_numbers(
    konteringslinjer,
):
    """Hent gyldige InvoiceLineNumber-værdier."""

    line_numbers = []

    for linje in konteringslinjer:
        raw_line_number = linje.get(
            "InvoiceLineNumber"
        )

        if raw_line_number in (
            None,
            "",
        ):
            continue

        try:
            line_number = Decimal(
                str(raw_line_number)
            )
        except InvalidOperation:
            continue

        line_numbers.append(
            line_number
        )

    return line_numbers


def vis_udvalgte_linjer(
    konteringslinjer,
):
    """Vis kun de første og sidste linjer."""

    print()
    print("=" * 70)
    print("UDVALGTE KONTERINGSLINJER")
    print("=" * 70)

    antal_linjer = len(
        konteringslinjer
    )

    antal_foerste = min(
        VIS_ANTAL_FOERSTE_LINJER,
        antal_linjer,
    )

    for index in range(
        antal_foerste
    ):
        print()
        print("-" * 70)
        print(
            "Første konteringslinje "
            f"{index + 1}"
        )
        print("-" * 70)

        pprint(
            konteringslinjer[index]
        )

    start_sidste = max(
        antal_foerste,
        antal_linjer
        - VIS_ANTAL_SIDSTE_LINJER,
    )

    for index in range(
        start_sidste,
        antal_linjer,
    ):
        print()
        print("-" * 70)
        print(
            "Sidste konteringslinje "
            f"{index + 1}"
        )
        print("-" * 70)

        pprint(
            konteringslinjer[index]
        )


if __name__ == "__main__":
    main()