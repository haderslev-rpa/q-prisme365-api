"""Enkel live-test af fakturagodkendelse."""

import logging
from decimal import Decimal

from q_prisme365_api.functionality.fakturaer import (
    approve_faktura,
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

# False betyder, at testen ikke ændrer fakturaen.
# True betyder, at testen forsøger at godkende.
UDFOER_GODKENDELSE = True


# ------------------------------------------------------------
# TESTDATA
# ------------------------------------------------------------

# Fakturaens RecIdLoc.
# Brug ikke konteringslinjens RecIdLoc.
REC_ID_LOC = 5637558435

# Eksempel:
# REC_ID_LOC = 5638526916


# Fakturaens samlede beløb.
# Brug eksempelvis ImportedInvoiceAmount.
FAKTURABELOEB = Decimal("460.00")


# Processens beregnede sum af GrossAmount
# fra samtlige konteringslinjer.
KONTERINGSLINJER_TOTALBELOEB = Decimal(
    "460.00"
)


# Valgfri Godkender 1.
#
# Hvis værdien udfyldes, flytter funktionen
# først fakturaen til denne bruger.
#
# Bruger-id'et skal starte med dirx.
#
# Brug None, hvis fakturaen allerede ligger
# hos den korrekte dirx-bruger.
GODKENDER_1 = "dirxkfp"

# Eksempel:
# GODKENDER_1 = "dirxkfp"


# Valgfrie oplysninger ved flytning.
GODKENDER_2 = ""
KONTERINGSPERSON = ""
AFDELING = ""

# Eksempel:
# AFDELING = "100201010000"


# ------------------------------------------------------------
# LIVE-TEST
# ------------------------------------------------------------

def main():
    """Godkend én faktura."""

    print()
    print("=" * 70)
    print("LIVE-TEST AF FAKTURAGODKENDELSE")
    print("=" * 70)
    print()
    print("RecIdLoc:", REC_ID_LOC)
    print("Fakturabeløb:", FAKTURABELOEB)
    print(
        "Konteringslinjernes totalbeløb:",
        KONTERINGSLINJER_TOTALBELOEB,
    )
    print("Godkender 1:", GODKENDER_1)
    print("Afdeling:", AFDELING)
    print()

    if REC_ID_LOC is None:
        raise ValueError(
            "Udfyld REC_ID_LOC med fakturaens "
            "RecIdLoc."
        )

    difference = abs(
        FAKTURABELOEB
        - KONTERINGSLINJER_TOTALBELOEB
    )

    print("Difference:", difference)

    if difference >= Decimal("1.00"):
        raise ValueError(
            "Testen stoppede, fordi differencen "
            "mellem fakturabeløbet og "
            "konteringslinjernes totalbeløb "
            "ikke er mindre end 1 krone."
        )

    print(
        "Beløbskontrol i testfilen: OK"
    )

    if GODKENDER_1:
        if not GODKENDER_1.casefold().startswith(
            "dirx"
        ):
            raise ValueError(
                "GODKENDER_1 skal starte med dirx. "
                f"Angivet værdi: {GODKENDER_1!r}."
            )

        print(
            "Godkender 1-kontrol i testfilen: OK"
        )
        print(
            "Fakturaen bliver først flyttet til:",
            GODKENDER_1,
        )
    else:
        print(
            "Ingen Godkender 1 er angivet."
        )
        print(
            "Funktionen kontrollerer den aktuelle "
            "godkender i Prisme."
        )

    if not UDFOER_GODKENDELSE:
        print()
        print(
            "Godkendelsen blev IKKE udført."
        )
        print(
            "Sæt UDFOER_GODKENDELSE = True, "
            "når testen må ændre fakturaen."
        )
        return

    print()
    print(
        "Kalder approve_faktura nu..."
    )

    result = approve_faktura(
        rec_id_loc=REC_ID_LOC,
        fakturabeloeb=FAKTURABELOEB,
        konteringslinjer_totalbeloeb=(
            KONTERINGSLINJER_TOTALBELOEB
        ),
        godkender_1=GODKENDER_1,
        godkender_2=GODKENDER_2,
        konteringsperson=KONTERINGSPERSON,
        afdeling=AFDELING,
    )

    print()
    print(
        "Godkendelse gennemført:",
        result,
    )


if __name__ == "__main__":
    main()