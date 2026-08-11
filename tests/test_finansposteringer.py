"""Manuel live-test af finansposteringer.py."""

import logging
from datetime import date
from pprint import pprint

from q_prisme365_api.functionality.finansposteringer import (
    search_finansposteringer,
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
# TESTVÆRDIER
# ------------------------------------------------------------

DATO_FRA = date(2026, 8, 1)
DATO_TIL = date(2026, 8, 10)

KONTOSTRENG = "903031000000-952599999-92399-80-"
BESKRIVELSE = None
YDELSESMODTAGER = None

POSTERINGSTYPER = (
    "PurchExpense",
    "LedgerJournal",
    "CustRevenue",
)

FILTER_POSTING_TYPES_LOCALLY = True
TOP = 20


def main():
    """Kør live-test af finansposteringer."""

    print()
    print("=" * 70)
    print("LIVE-TEST AF FINANSPOSTERINGER")
    print("=" * 70)

    rows = search_finansposteringer(
        dato_fra=DATO_FRA,
        dato_til=DATO_TIL,
        kontostreng=KONTOSTRENG,
        beskrivelse=BESKRIVELSE,
        ydelsesmodtager=YDELSESMODTAGER,
        posteringstyper=POSTERINGSTYPER,
        filter_posting_types_locally=(
            FILTER_POSTING_TYPES_LOCALLY
        ),
        top=TOP,
    )

    print()
    print(
        "Antal finansposteringer:",
        len(rows),
    )

    for row_number, row in enumerate(
        rows,
        start=1,
    ):
        print()
        print(
            f"Finanspostering {row_number}:"
        )
        pprint(row)

    posting_types = sorted(
        {
            str(
                row.get(
                    "PostingType",
                    "",
                )
            )
            for row in rows
            if row.get("PostingType")
        }
    )

    print()
    print("Fundne PostingType-værdier:")
    pprint(posting_types)


if __name__ == "__main__":
    main()
