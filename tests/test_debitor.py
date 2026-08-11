"""Manuel live-test af debitor.py."""

import logging
from pprint import pprint

from q_prisme365_api.functionality.debitor import (
    get_debitor,
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

DEBITORNUMMER = None
CPR_CVR = 29189757
NAVN = None
TOP = 10
RAW = True


def main():
    """Kør live-test af debitoropslag."""

    print()
    print("=" * 70)
    print("LIVE-TEST AF DEBITOR")
    print("=" * 70)

    data = get_debitor(
        debitornummer=DEBITORNUMMER,
        cpr_cvr=CPR_CVR,
        navn=NAVN,
        top=TOP,
        raw=RAW,
    )

    print()
    print_result(data)


def print_result(data):
    """Udskriv resultatet overskueligt."""

    if isinstance(data, list):
        print(
            "Antal debitorer:",
            len(data),
        )

        for row_number, row in enumerate(
            data,
            start=1,
        ):
            print()
            print(
                f"Debitor {row_number}:"
            )
            pprint(row)

        return

    print(
        "Råt resultat:"
    )
    pprint(data)


if __name__ == "__main__":
    main()