"""Manuel live-test af advis_update.py."""

import logging
from pprint import pprint

from q_prisme365_api.functionality.advis_update import (
    build_advis_body,
    build_advis_endpoint,
    update_advis,
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

ALLOW_UPDATE = False


# ------------------------------------------------------------
# TESTVÆRDIER
# ------------------------------------------------------------

ADVIS_REC_ID = None
HANDLED = True


def validate_rec_id(value):
    """Kontrollér RecIdLoc."""

    if value is None:
        raise ValueError(
            "Udfyld ADVIS_REC_ID øverst i filen."
        )

    if isinstance(value, bool):
        raise TypeError(
            "ADVIS_REC_ID må ikke være en bool-værdi."
        )

    try:
        rec_id = int(value)
    except (TypeError, ValueError) as error:
        raise TypeError(
            "ADVIS_REC_ID skal være et heltal."
        ) from error

    if rec_id <= 0:
        raise ValueError(
            "ADVIS_REC_ID skal være større end 0."
        )

    return rec_id


def main():
    """Kør en live-opdatering af ét advis."""

    print()
    print("=" * 70)
    print("LIVE-TEST AF ADVIS UPDATE")
    print("=" * 70)

    if not ALLOW_UPDATE:
        print(
            "Ingen opdatering udført."
        )
        print(
            "Sæt ALLOW_UPDATE = True og udfyld "
            "ADVIS_REC_ID for at aktivere testen."
        )
        return

    rec_id = validate_rec_id(
        ADVIS_REC_ID
    )

    endpoint = build_advis_endpoint(
        rec_id
    )

    body = build_advis_body(
        rec_id,
        HANDLED,
    )

    print()
    print("Endpoint:")
    print(endpoint)

    print()
    print("PATCH-indhold:")
    pprint(body)

    print()
    print("Udfører opdatering...")

    result = update_advis(
        recid=rec_id,
        handled=HANDLED,
    )

    print()
    print("Resultat:")
    pprint(result)


if __name__ == "__main__":
    main()