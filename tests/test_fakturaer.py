"""Enkel live-test af faktura med dokumenter."""

from q_prisme365_api.api_client import (
    initialiser_prisme,
)
from q_prisme365_api.functionality.fakturaer import (
    search_fakturaer,
)


# ------------------------------------------------------------
# TESTINDSTILLINGER
# ------------------------------------------------------------

CREDENTIAL_NAME = "API_PRISME365_1"

HEADER_REFERENCE = "000684819"

HENT_DETALJER = True
HENT_DOKUMENTER = True


def main() -> None:
    """Hent én faktura med detaljer og dokumenter."""

    initialiser_prisme(
        credential_name=CREDENTIAL_NAME
    )

    fakturaer = search_fakturaer(
        header_reference=HEADER_REFERENCE,
        hent_detaljer=HENT_DETALJER,
        hent_dokumenter=HENT_DOKUMENTER,
        hent_dokumentplacering=True,
        dokument_domain_suffix=(
            "prisme-365.dk"
        ),
        top=1,
    )

    if not fakturaer:
        raise RuntimeError(
            "Fakturaen blev ikke fundet. "
            f"HeaderReference: "
            f"{HEADER_REFERENCE!r}."
        )

    if len(fakturaer) != 1:
        raise RuntimeError(
            "Fakturaopslaget var ikke entydigt. "
            f"Antal fundet: {len(fakturaer)}."
        )

    faktura = fakturaer[0]

    kontrollér_faktura(
        faktura
    )

    print_faktura(
        faktura
    )


def kontrollér_faktura(
    faktura: dict,
) -> None:
    """Kontrollér det vigtigste testresultat."""

    faktisk_reference = str(
        faktura.get(
            "HeaderReference",
            "",
        )
        or ""
    ).strip()

    if faktisk_reference != HEADER_REFERENCE:
        raise RuntimeError(
            "HeaderReference matcher ikke. "
            f"Forventet: {HEADER_REFERENCE!r}. "
            f"Fundet: {faktisk_reference!r}."
        )

    if HENT_DETALJER:
        if "raw_details" not in faktura:
            raise RuntimeError(
                "Fakturadetaljerne blev ikke "
                "tilføjet til resultatet."
            )

        rec_id_loc = faktura.get(
            "RecIdLoc"
        )

        if rec_id_loc in (
            None,
            "",
            0,
            "0",
        ):
            raise RuntimeError(
                "Fakturadetaljerne mangler "
                "RecIdLoc."
            )

    if HENT_DOKUMENTER:
        dokumenter = faktura.get(
            "Vedhæftede dokumenter"
        )

        if dokumenter is None:
            raise RuntimeError(
                "Resultatet mangler feltet "
                "'Vedhæftede dokumenter'."
            )

        if not isinstance(
            dokumenter,
            list,
        ):
            raise TypeError(
                "'Vedhæftede dokumenter' "
                "skal være en liste."
            )


def print_faktura(
    faktura: dict,
) -> None:
    """Udskriv fakturaen kort og læsbart."""

    dokumenter = faktura.get(
        "Vedhæftede dokumenter",
        [],
    )

    print()
    print("=" * 70)
    print("FAKTURA HENTET")
    print("=" * 70)
    print(
        "HeaderReference:",
        faktura.get("HeaderReference"),
    )
    print(
        "RecIdLoc:",
        faktura.get("RecIdLoc"),
    )
    print(
        "Fakturanummer:",
        faktura.get("Fakturanr"),
    )
    print(
        "Leverandør:",
        faktura.get("Leverandørnavn"),
    )
    print(
        "Kreditorkonto:",
        faktura.get("Kreditorkonto"),
    )
    print(
        "CVR:",
        faktura.get("CVR"),
    )
    print(
        "Afdeling:",
        faktura.get("Afdeling"),
    )
    print(
        "Godkender:",
        faktura.get("Godkender"),
    )
    print(
        "Fakturabeløb:",
        faktura.get(
            "Importeret fakturabeløb"
        ),
    )
    print(
        "Momsbeløb:",
        faktura.get("Momsbeløb"),
    )
    print(
        "Fakturadato:",
        faktura.get("Fakturadato"),
    )
    print(
        "Forfaldsdato:",
        faktura.get("Forfaldsdato"),
    )
    print(
        "Workflowstatus:",
        faktura.get(
            "VendorInvoiceReviewStatus"
        ),
    )
    print(
        "Detaljer hentet:",
        "raw_details" in faktura,
    )
    print(
        "Antal dokumenter:",
        len(dokumenter),
    )

    if not dokumenter:
        print()
        print(
            "Fakturaen har ingen dokumenter "
            "eller notater."
        )
        print("=" * 70)
        return

    print()
    print("-" * 70)
    print("DOKUMENTER OG NOTATER")
    print("-" * 70)

    for nummer, dokument in enumerate(
        dokumenter,
        start=1,
    ):
        print()
        print(
            f"Dokument {nummer}"
        )
        print(
            "Type:",
            dokument.get("TypeId"),
        )
        print(
            "Navn:",
            dokument.get("Name"),
        )
        print(
            "DocumentId:",
            dokument.get("DocumentId"),
        )
        print(
            "ValueRecId:",
            dokument.get("ValueRecId"),
        )
        print(
            "Oprettet af:",
            dokument.get(
                "OriginallyCreatedBy"
            ),
        )
        print(
            "Oprettet dato:",
            dokument.get("CreatedOn"),
        )

        notes = str(
            dokument.get(
                "Notes",
                "",
            )
            or ""
        ).strip()

        if notes:
            print(
                "Notat:",
                notes,
            )

        dokumentnavn = dokument.get(
            "Dokumentnavn"
        )

        if dokumentnavn:
            print(
                "Filnavn:",
                dokumentnavn,
            )

        dokumentsti = dokument.get(
            "Dokumentsti"
        )

        if dokumentsti:
            print(
                "Dokumentsti:",
                dokumentsti,
            )

        if dokument.get(
            "ValueRecId"
        ) in (
            None,
            "",
            0,
            "0",
        ):
            print(
                "Fysisk fil:",
                "Nej",
            )
        else:
            print(
                "Fysisk fil:",
                "Ja",
            )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()