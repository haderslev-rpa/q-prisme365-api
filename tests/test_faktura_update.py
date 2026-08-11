"""Manuel live-test af fakturaopdatering."""

import logging
from datetime import date
from pprint import pprint

from q_prisme365_api.functionality.fakturaer import (
    build_faktura_beskrivelse_body,
    build_faktura_beskrivelse_endpoint,
    build_faktura_bogfoeringsdato_body,
    build_faktura_bogfoeringsdato_endpoint,
    update_faktura_beskrivelse,
    update_faktura_bogfoeringsdato,
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

ALLOW_UPDATE = True


# ------------------------------------------------------------
# VÆLG TEST
# ------------------------------------------------------------

TEST_BESKRIVELSE = True
TEST_BOGFOERINGSDATO = False


# ------------------------------------------------------------
# TESTDATA TIL BESKRIVELSE
# ------------------------------------------------------------

REC_ID_LOC = "5637560833"

# Blue Prism-eksempel:
# REC_ID_LOC = 5637162690

FAKTURABESKRIVELSE = (
    "Test af API - Robot"
)


# ------------------------------------------------------------
# TESTDATA TIL BOGFØRINGSDATO
# ------------------------------------------------------------

HEADER_REFERENCE = "000681929"

# Blue Prism-eksempel:
# HEADER_REFERENCE = "000118227"

BOGFOERINGSDATO = date(
    2026,
    8,
    8,
)

DATA_AREA_ID = "had"


def main():
    """Kør den valgte fakturaopdatering."""

    if TEST_BESKRIVELSE:
        test_beskrivelse()

    if TEST_BOGFOERINGSDATO:
        test_bogfoeringsdato()


def test_beskrivelse():
    """Vis eller udfør beskrivelsesopdatering."""

    if REC_ID_LOC is None:
        print()
        print(
            "Udfyld REC_ID_LOC for at bygge "
            "beskrivelsesopdateringen."
        )
        return

    endpoint = (
        build_faktura_beskrivelse_endpoint(
            REC_ID_LOC
        )
    )

    body = build_faktura_beskrivelse_body(
        rec_id_loc=REC_ID_LOC,
        fakturabeskrivelse=(
            FAKTURABESKRIVELSE
        ),
    )

    print()
    print("=" * 70)
    print("OPDATER FAKTURABESKRIVELSE")
    print("=" * 70)
    print()
    print("Endpoint:")
    print(endpoint)
    print()
    print("Body:")
    pprint(body)

    if not ALLOW_UPDATE:
        print()
        print(
            "PATCH blev ikke udført, fordi "
            "ALLOW_UPDATE er False."
        )
        return

    result = update_faktura_beskrivelse(
        rec_id_loc=REC_ID_LOC,
        fakturabeskrivelse=(
            FAKTURABESKRIVELSE
        ),
        verificer=True,
    )

    print()
    print("Resultat:")
    pprint(result)


def test_bogfoeringsdato():
    """Vis eller udfør datoopdatering."""

    if HEADER_REFERENCE is None:
        print()
        print(
            "Udfyld HEADER_REFERENCE for at "
            "bygge datoopdateringen."
        )
        return

    endpoint = (
        build_faktura_bogfoeringsdato_endpoint(
            header_reference=(
                HEADER_REFERENCE
            ),
            data_area_id=DATA_AREA_ID,
        )
    )

    body = build_faktura_bogfoeringsdato_body(
        header_reference=(
            HEADER_REFERENCE
        ),
        bogfoeringsdato=BOGFOERINGSDATO,
    )

    print()
    print("=" * 70)
    print("OPDATER BOGFØRINGSDATO")
    print("=" * 70)
    print()
    print("Endpoint:")
    print(endpoint)
    print()
    print("Body:")
    pprint(body)

    if not ALLOW_UPDATE:
        print()
        print(
            "PATCH blev ikke udført, fordi "
            "ALLOW_UPDATE er False."
        )
        return

    result = update_faktura_bogfoeringsdato(
        header_reference=(
            HEADER_REFERENCE
        ),
        bogfoeringsdato=BOGFOERINGSDATO,
        data_area_id=DATA_AREA_ID,
        verificer=True,
    )

    print()
    print("Resultat:")
    pprint(result)


if __name__ == "__main__":
    main()