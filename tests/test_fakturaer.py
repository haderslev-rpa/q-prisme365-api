"""Enkel live-test af fakturasøgning."""

import logging
from pprint import pprint

from q_prisme365_api.functionality.fakturaer import (
    search_fakturaer,
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
# TESTDATA FRA BLUE PRISM
# ------------------------------------------------------------

GODKENDER_INITIALER = None

# Eksempel:
# GODKENDER_INITIALER = "DIRUJO"

AFDELING = None #"140504120100"

# Andre Blue Prism-eksempler:
# AFDELING = "180505020000"
# AFDELING = "160301030215"

LEVERANDOERNUMMER = None

# Eksempel:
# LEVERANDOERNUMMER = "000003"

OPRETTET_DATO_START = None

HEADER_REFERENCE = "000676655"

# Blue Prism-eksempel:
# HEADER_REFERENCE = "000186974"

FAKTURABESKRIVELSE = None

# Blue Prism-eksempel:
# FAKTURABESKRIVELSE = "Robot"


HENT_DETALJER = True
HENT_DOKUMENTER = False
TOP = 100


def main():
    """Søg efter fakturaer."""

    fakturaer = search_fakturaer(
        godkender_initialer=(
            GODKENDER_INITIALER
        ),
        afdeling=AFDELING,
        leverandoernummer=(
            LEVERANDOERNUMMER
        ),
        oprettet_dato_start=(
            OPRETTET_DATO_START
        ),
        header_reference=(
            HEADER_REFERENCE
        ),
        fakturabeskrivelse=(
            FAKTURABESKRIVELSE
        ),
        hent_detaljer=HENT_DETALJER,
        hent_dokumenter=HENT_DOKUMENTER,
        top=TOP,
    )

    print()
    print(
        "Antal fakturaer:",
        len(fakturaer),
    )

    for nummer, faktura in enumerate(
        fakturaer,
        start=1,
    ):
        print()
        print(
            f"Faktura {nummer}:"
        )
        pprint(faktura)


if __name__ == "__main__":
    main()