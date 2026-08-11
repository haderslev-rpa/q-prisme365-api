"""Enkel live-test af fakturakontering."""

from decimal import Decimal

from q_prisme365_api.api_client import initialiser_prisme
from q_prisme365_api.functionality.faktura_kontering import (
    konter_faktura,
)

initialiser_prisme(
    credential_name="API_PRISME365_1"
)


# ------------------------------------------------------------
# TESTFAKTURA
# ------------------------------------------------------------

HEADER_REFERENCE = "000682112"


# ------------------------------------------------------------
# VÆLG ØNSKET SLUTRESULTAT
# ------------------------------------------------------------

# Dette er det eneste, du normalt ændrer.
ANTAL_OENSKEDE_LINJER = 50


# ------------------------------------------------------------
# FASTE TESTOPLYSNINGER
# ------------------------------------------------------------

FAKTURABELOEB = Decimal("50768.60")

KONTOSTRENG = (
    "100201010000-645511002-10021-40-"
)

FAKTURA_AFDELING = "180123000000"

KREDITORKONTO = "000065"

ENHED = "STK"

YDELSESMODTAGER = "3112999999"

# True bekræfter, at alle udfyldte
# CPR-numre er valideret via Datafordeleren.
CPR_NUMRE_VALIDERET = True


def main() -> None:
    """Byg linjerne og udfør konteringen."""

    konteringslinjer = byg_konteringslinjer(
        antal_linjer=(
            ANTAL_OENSKEDE_LINJER
        ),
        totalbeloeb=FAKTURABELOEB,
    )

    konter_faktura(
        header_reference=HEADER_REFERENCE,
        konteringslinjer=konteringslinjer,
        cpr_numre_valideret=(
            CPR_NUMRE_VALIDERET
        ),
    )


def byg_konteringslinjer(
    antal_linjer: int,
    totalbeloeb: Decimal,
) -> list[dict[str, object]]:
    """
    Byg det ønskede antal testlinjer.

    Beløbet fordeles i hele øre, så summen
    altid bliver præcis lig fakturabeløbet.
    """

    if isinstance(
        antal_linjer,
        bool,
    ):
        raise TypeError(
            "antal_linjer skal være "
            "et positivt heltal."
        )

    if not isinstance(
        antal_linjer,
        int,
    ):
        raise TypeError(
            "antal_linjer skal være "
            "et heltal."
        )

    if antal_linjer <= 0:
        raise ValueError(
            "antal_linjer skal være "
            "større end 0."
        )

    if not isinstance(
        totalbeloeb,
        Decimal,
    ):
        raise TypeError(
            "totalbeloeb skal være Decimal."
        )

    if totalbeloeb <= Decimal("0"):
        raise ValueError(
            "totalbeloeb skal være "
            "større end 0."
        )

    total_i_oere = (
        totalbeloeb
        * Decimal("100")
    )

    if (
        total_i_oere
        != total_i_oere.to_integral_value()
    ):
        raise ValueError(
            "totalbeloeb må højst have "
            "to decimaler."
        )

    samlet_antal_oere = int(
        total_i_oere
    )

    grundbeloeb_oere = (
        samlet_antal_oere
        // antal_linjer
    )

    resterende_oere = (
        samlet_antal_oere
        % antal_linjer
    )

    konteringslinjer = []

    for linjenummer in range(
        1,
        antal_linjer + 1,
    ):
        beloeb_oere = grundbeloeb_oere

        if linjenummer <= resterende_oere:
            beloeb_oere += 1

        bruttobeloeb = (
            Decimal(beloeb_oere)
            / Decimal("100")
        )

        konteringslinjer.append(
            {
                "kontostreng": KONTOSTRENG,
                "bruttobeloeb": bruttobeloeb,
                "ydelsesmodtager": (
                    YDELSESMODTAGER
                ),
                "enhed": ENHED,
                "faktura_afdeling": (
                    FAKTURA_AFDELING
                ),
                "posteringstekst": (
                    "Python kontering "
                    f"linje {linjenummer}"
                ),
                "kreditorkonto": (
                    KREDITORKONTO
                ),
            }
        )

    beregnet_total = sum(
        (
            linje["bruttobeloeb"]
            for linje in konteringslinjer
        ),
        Decimal("0"),
    )

    if beregnet_total != totalbeloeb:
        raise RuntimeError(
            "Konteringslinjernes totalbeløb "
            "matcher ikke fakturabeløbet. "
            f"Fakturabeløb: {totalbeloeb}. "
            f"Linjetotal: {beregnet_total}."
        )

    return konteringslinjer


if __name__ == "__main__":
    main()