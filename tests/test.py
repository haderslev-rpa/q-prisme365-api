"""Manuel debugfil til Prisme 365 API."""

import logging
from pprint import pprint

from q_prisme365_api.functionality.advis import get_advis
from q_prisme365_api.functionality.advis_update import update_advis
from q_prisme365_api.functionality.ean import get_ean


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s: "
        "%(message)s"
    ),
)


def test_ean():
    """Test et sikkert GET-kald til EAN."""

    print()
    print("Tester EAN-opslag")

    data = get_ean(
        ean=None,
        raw=True,
    )

    pprint(data)


def test_advis():
    """Test et sikkert GET-kald til adviser."""

    print()
    print("Tester advis-opslag")

    data = get_advis(
        identification_number=None,
        advice_text=None,
        handled=None,
        extra_filters=None,
        top=5,
        raw=True,
    )

    pprint(data)


def test_update_advis():
    """
    Test opdatering af ét advis.

    Funktionen er ikke aktiveret automatisk,
    fordi funktionen ændrer data i Prisme.
    """

    recid = 0

    if recid <= 0:
        raise ValueError(
            "Indsæt et gyldigt RecIdLoc, "
            "før update-testen køres."
        )

    result = update_advis(
        recid=recid,
        handled=True,
    )

    print(
        "Opdatering gennemført:",
        result,
    )


def main():
    """Vælg hvilken manuel test der skal køres."""

    # Aktivér kun den test, du ønsker.
    test_advis()

    # test_ean()

    # Ændrer data. Aktivér kun bevidst.
    # test_update_advis()


if __name__ == "__main__":
    main()