"""Vis præcist output fra search_dokumenter."""

from pprint import pprint

from q_prisme365_api.api_client import (
    initialiser_prisme,
)
from q_prisme365_api.functionality.dokumenter import (
    search_dokumenter,
)


# ------------------------------------------------------------
# CREDENTIAL
# ------------------------------------------------------------

# Navnet på credential-posten i
# Automation Server.
CREDENTIAL_NAME = "API_PRISME365_1"


# ------------------------------------------------------------
# VÆLG SØGETYPE
# ------------------------------------------------------------

# Tilladte værdier:
#
# "ventende_kreditorfaktura"
#     Søger dokumenter på en faktura.
#     Bruger RefTableId 6084.
#
# "cpr_cvr"
#     Søger dokumenter på CPR/CVR.
#     Bruger RefTableId 27526.
TABEL = "ventende_kreditorfaktura"


# ------------------------------------------------------------
# FAKTURASØGNING
# ------------------------------------------------------------

# Fakturaens RecIdLoc.
#
# Bruges kun, når:
# TABEL = "ventende_kreditorfaktura"
FAKTURA_REC_ID_LOC = 5637561949


# ------------------------------------------------------------
# CPR/CVR-SØGNING
# ------------------------------------------------------------

# CPR- eller CVR-værdi.
#
# Bruges kun, når:
# TABEL = "cpr_cvr"
CPR_CVR = None

# Eksempel:
# CPR_CVR = "29189757"


# ------------------------------------------------------------
# DOKUMENTPLACERING
# ------------------------------------------------------------

# True:
#     Fysiske dokumenter udvides med
#     Dokumentnavn, Dokumentsti, FilId og
#     AccessInformationRaw.
#
# False:
#     Dokumentreferencerne returneres stadig,
#     men Dokumentsti bliver None, og
#     DokumentplaceringStatus bliver
#     "ikke_hentet" for fysiske filer.
HENT_DOKUMENTPLACERING = True


# Domænet føjes til servernavnet, når en
# file-URI konverteres til en UNC-sti.
DOMAIN_SUFFIX = "prisme-365.dk"


# ------------------------------------------------------------
# RÅDATA
# ------------------------------------------------------------

# False:
#     Returnerer kun det normaliserede og
#     dokumenterede output.
#
# True:
#     Tilføjer også feltet raw med de
#     oprindelige Prisme-data.
INKLUDER_RAW = False


# ------------------------------------------------------------
# ANTAL
# ------------------------------------------------------------

# Maksimalt antal dokumenter.
TOP = 100


def main() -> None:
    """
    Initialisér Prisme, hent dokumenter og
    udskriv præcis funktionens returværdi.

    Testen:
        ændrer ikke dokumenterne
        omdøber ikke felter
        fjerner ikke felter
        tilføjer ikke felter
        foretager ikke ekstra dokumentopslag
    """

    initialiser_prisme(
        credential_name=CREDENTIAL_NAME
    )

    søgeargumenter = byg_søgeargumenter()

    dokumenter = search_dokumenter(
        **søgeargumenter
    )

    # Dette er den eneste udskrift.
    #
    # pprint ændrer ikke dataene.
    # Funktionen viser blot returværdien
    # i et mere læsbart format.
    pprint(
        dokumenter,
        sort_dicts=False,
        width=120,
    )


def byg_søgeargumenter() -> dict:
    """
    Byg argumenterne til search_dokumenter.

    Funktionen sikrer, at testen enten søger
    på en faktura eller på CPR/CVR.
    """

    if TABEL == "ventende_kreditorfaktura":
        faktura_rec_id = (
            kontrollér_positivt_heltal(
                FAKTURA_REC_ID_LOC,
                "FAKTURA_REC_ID_LOC",
            )
        )

        return {
            "ref_rec_id": faktura_rec_id,
            "tabel": (
                "ventende_kreditorfaktura"
            ),
            "hent_dokumentplacering": (
                HENT_DOKUMENTPLACERING
            ),
            "domain_suffix": DOMAIN_SUFFIX,
            "inkluder_raw": INKLUDER_RAW,
            "top": TOP,
        }

    if TABEL == "cpr_cvr":
        cpr_cvr = kontrollér_tekst(
            CPR_CVR,
            "CPR_CVR",
        )

        return {
            "tabel": "cpr_cvr",
            "cpr_cvr": cpr_cvr,
            "hent_dokumentplacering": (
                HENT_DOKUMENTPLACERING
            ),
            "domain_suffix": DOMAIN_SUFFIX,
            "inkluder_raw": INKLUDER_RAW,
            "top": TOP,
        }

    raise ValueError(
        "TABEL har en ugyldig værdi. "
        "Tilladte værdier er "
        "'ventende_kreditorfaktura' "
        "og 'cpr_cvr'. "
        f"Fundet: {TABEL!r}."
    )


def kontrollér_positivt_heltal(
    value: object,
    variable_name: str,
) -> int:
    """Kontrollér et positivt heltal."""

    if isinstance(
        value,
        bool,
    ):
        raise TypeError(
            f"{variable_name} skal være "
            "et positivt heltal."
        )

    try:
        integer_value = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise TypeError(
            f"{variable_name} skal være "
            "et positivt heltal."
        ) from error

    if integer_value <= 0:
        raise ValueError(
            f"{variable_name} skal være "
            "større end 0."
        )

    return integer_value


def kontrollér_tekst(
    value: object,
    variable_name: str,
) -> str:
    """Kontrollér en obligatorisk tekstværdi."""

    if value is None:
        raise ValueError(
            f"{variable_name} skal udfyldes."
        )

    text_value = str(
        value
    ).strip()

    if not text_value:
        raise ValueError(
            f"{variable_name} skal udfyldes."
        )

    return text_value


if __name__ == "__main__":
    main()