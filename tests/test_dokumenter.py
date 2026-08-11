"""Manuel live-test af dokumenter.py."""

import logging
from datetime import date
from pprint import pprint

from q_prisme365_api.functionality.dokumenter import (
    get_dokumentinformation,
    search_dokumenter,
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
# VÆLG TEST
# ------------------------------------------------------------

TEST_SEARCH = True
TEST_DOCUMENT_INFORMATION = False


# ------------------------------------------------------------
# TESTVÆRDIER TIL DOKUMENTSØGNING
# ------------------------------------------------------------

# RefRecId er id'et på den post,
# som dokumentet er tilknyttet.
REF_REC_ID = None

# Eksempel fra Blue Prism:
# Fakturaens RecIdLoc anvendt som RefRecId.
# REF_REC_ID = 5637145442


# DocumentId er dokumentets UUID.
DOCUMENT_ID = None

# Eksempler fra Blue Prism:
# DOCUMENT_ID = "43de3c64-15b0-4bf7-a826-d2df7bc52d9c"
# DOCUMENT_ID = "7a5b622e-4ee0-4029-bc3b-4e26f68e965b"


# Tilladte værdier:
# None
# "cpr_cvr"
# "ventende_kreditorfaktura"
TABEL = "cpr_cvr"

CPR_CVR = "29189757"

# Alternativ uden CPR/CVR-filter:
# CPR_CVR = None


DOKUMENTNAVN = (
    "VS Vedr. opkald fra borger med spørgsmål "
    "om byggesagsgebyr"
)

# Alternativ uden dokumentnavnsfilter:
# DOKUMENTNAVN = None


# Eksempler kan være "Fil" eller "Notat",
# afhængigt af værdierne i TypeId.
DOKUMENTTYPE = None

# Eksempler:
# DOKUMENTTYPE = "Fil"
# DOKUMENTTYPE = "Notat"


OPRETTET_AF = None

# Eksempel:
# OPRETTET_AF = "BRUGERKODE"


NOTAT_TEKST = None

# Eksempel på præcis notattekst:
# NOTAT_TEKST = "Teksten fra notatet"


OPRETTET_DATO = None

# Dato skal angives som en date-værdi
# og ikke som almindelig tekst.
# Eksempel:
# OPRETTET_DATO = date(2025, 2, 21)


# False henter kun dokumentreferencer.
# True henter også filinformation via ValueRecId.
HENT_DOKUMENTPLACERING = False


# Tilføjes til servernavnet ved konvertering
# fra file-URI til UNC-sti.
DOMAIN_SUFFIX = "prisme-365.dk"


# Maksimalt antal dokumentreferencer.
TOP = 10


# ------------------------------------------------------------
# TESTVÆRDI TIL DIREKTE DOKUMENTINFORMATION
# ------------------------------------------------------------

VALUE_REC_ID = None

# Eksempel fra Blue Prism:
# ValueRecId fra DocuRefDatasEntity_FUJ.
# VALUE_REC_ID = 5637485659

# Andre værdier nævnt i Blue Prism-noterne:
# VALUE_REC_ID = 5637144576
# VALUE_REC_ID = 5637146076
# VALUE_REC_ID = 5637145326

def main():
    """Kør de valgte dokumenttests."""

    print()
    print("=" * 70)
    print("LIVE-TEST AF DOKUMENTER")
    print("=" * 70)

    if TEST_SEARCH:
        test_search()

    if TEST_DOCUMENT_INFORMATION:
        test_document_information()

    if (
        not TEST_SEARCH
        and not TEST_DOCUMENT_INFORMATION
    ):
        print(
            "Ingen test valgt."
        )


def test_search():
    """Søg efter dokumentreferencer."""

    created_date = validate_optional_date(
        OPRETTET_DATO
    )

    data = search_dokumenter(
        ref_rec_id=REF_REC_ID,
        document_id=DOCUMENT_ID,
        tabel=TABEL,
        cpr_cvr=CPR_CVR,
        dokumentnavn=DOKUMENTNAVN,
        dokumenttype=DOKUMENTTYPE,
        oprettet_af=OPRETTET_AF,
        notat_tekst=NOTAT_TEKST,
        oprettet_dato=created_date,
        hent_dokumentplacering=(
            HENT_DOKUMENTPLACERING
        ),
        domain_suffix=DOMAIN_SUFFIX,
        top=TOP,
    )

    print()
    print("DOKUMENTSØGNING")
    print_result(data)


def test_document_information():
    """Hent filoplysninger via ValueRecId."""

    value_rec_id = require_positive_integer(
        VALUE_REC_ID,
        "VALUE_REC_ID",
    )

    data = get_dokumentinformation(
        value_rec_id=value_rec_id,
        domain_suffix=DOMAIN_SUFFIX,
    )

    print()
    print("DOKUMENTINFORMATION")
    pprint(data)


def validate_optional_date(value):
    """Konvertér en valgfri dato."""

    if value is None:
        return None

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(
            str(value)
        )
    except ValueError as error:
        raise ValueError(
            "OPRETTET_DATO skal skrives som "
            "YYYY-MM-DD."
        ) from error


def require_positive_integer(
    value,
    variable_name,
):
    """Kontrollér et positivt id."""

    if value is None:
        raise ValueError(
            f"Udfyld {variable_name} øverst "
            "i testfilen."
        )

    if isinstance(value, bool):
        raise TypeError(
            f"{variable_name} skal være et heltal."
        )

    try:
        integer_value = int(value)
    except (TypeError, ValueError) as error:
        raise TypeError(
            f"{variable_name} skal være et heltal."
        ) from error

    if integer_value <= 0:
        raise ValueError(
            f"{variable_name} skal være større end 0."
        )

    return integer_value


def print_result(data):
    """Udskriv resultatet overskueligt."""

    if isinstance(data, list):
        print(
            "Antal dokumenter:",
            len(data),
        )

        for row_number, row in enumerate(
            data,
            start=1,
        ):
            print()
            print(
                f"Dokument {row_number}:"
            )
            pprint(row)

        return

    print(
        "Råt resultat:"
    )
    pprint(data)


if __name__ == "__main__":
    main()