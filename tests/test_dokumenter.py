"""Live-test af dokumenter på en faktura."""

from pprint import pprint

from q_prisme365_api.api_client import (
    initialiser_prisme,
)
from q_prisme365_api.functionality.dokumenter import (
    get_dokumentinformation,
    search_dokumenter,
)


# ------------------------------------------------------------
# CREDENTIAL
# ------------------------------------------------------------

CREDENTIAL_NAME = "API_PRISME365_1"


# ------------------------------------------------------------
# TESTFAKTURA
# ------------------------------------------------------------

# RecIdLoc fra raw_details på faktura 000684546.
FAKTURA_REC_ID_LOC = 5637561949


# ------------------------------------------------------------
# DOKUMENTINDSTILLINGER
# ------------------------------------------------------------

# True henter også filnavn og filplacering
# via dokumentets ValueRecId.
HENT_DOKUMENTPLACERING = True

DOMAIN_SUFFIX = "prisme-365.dk"

TOP = 100


def main() -> None:
    """Hent fakturaens dokumenter."""

    initialiser_prisme(
        credential_name=CREDENTIAL_NAME
    )

    print()
    print("=" * 70)
    print("DOKUMENTER PÅ FAKTURA")
    print("=" * 70)
    print()
    print(
        "Fakturaens RecIdLoc:",
        FAKTURA_REC_ID_LOC,
    )

    dokumenter = search_dokumenter(
        ref_rec_id=FAKTURA_REC_ID_LOC,
        tabel="ventende_kreditorfaktura",
        hent_dokumentplacering=(
            HENT_DOKUMENTPLACERING
        ),
        domain_suffix=DOMAIN_SUFFIX,
        top=TOP,
    )

    print()
    print(
        "Antal dokumenter:",
        len(dokumenter),
    )

    if not dokumenter:
        print()
        print(
            "Der blev ikke fundet dokumenter "
            "på fakturaens RecIdLoc."
        )
        return

    for nummer, dokument in enumerate(
        dokumenter,
        start=1,
    ):
        print()
        print("-" * 70)
        print(
            f"Dokument {nummer}"
        )
        print("-" * 70)
        pprint(
            dokument,
            sort_dicts=False,
        )

        value_rec_id = dokument.get(
            "ValueRecId"
        )

        if value_rec_id in (
            None,
            "",
            0,
            "0",
        ):
            print()
            print(
                "Dokumentet har ingen fysisk "
                "fil, fordi ValueRecId mangler."
            )
            continue

        print()
        print(
            "ValueRecId:",
            value_rec_id,
        )

        # Dette direkte opslag er lidt
        # overflødigt, når
        # HENT_DOKUMENTPLACERING=True.
        #
        # Det bruges her bevidst til at teste,
        # at DocuValueDatasEntity_FUJ også
        # virker korrekt.
        dokumentinformation = (
            get_dokumentinformation(
                value_rec_id=int(
                    value_rec_id
                ),
                domain_suffix=DOMAIN_SUFFIX,
            )
        )

        print()
        print(
            "Direkte dokumentinformation:"
        )
        pprint(
            dokumentinformation,
            sort_dicts=False,
        )


if __name__ == "__main__":
    main()