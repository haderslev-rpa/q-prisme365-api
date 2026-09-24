"""Lokal integrationstest af kreditorfakturaer og originale OIOUBL-filer."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pprint import pprint
from typing import Any

from q_prisme365_api.api_client import initialiser_prisme
from q_prisme365_api.functionality.dokumenter import (
    get_dokumentinformation,
    hent_dokumentreferencer,
    search_dokumenter,
)
from q_prisme365_api.functionality.kreditorfakturaer import (
    hent_kreditorfakturaer,
    hent_oprindelige_fakturaposter,
)

CREDENTIAL_NAME = "API_PRISME365_1"
FAKTURADATO_FRA = date(2026, 9, 23)
FAKTURADATO_TIL = date(2026, 9, 25)  # eksklusiv
VOUCHER_PREFIX = "EFAK-"
DOKUMENTTYPER = ("OIOUBL",)
DATA_AREA_ID = "had"
DOMAIN_SUFFIX = "prisme-365.dk"


def main() -> None:
    """Test to dage og print kun de fire felter til den senere ATS-kø."""
    initialiser_prisme(credential_name=CREDENTIAL_NAME)
    fakturaer = hent_kreditorfakturaer(
        FAKTURADATO_FRA, FAKTURADATO_TIL,
        voucher_prefix=VOUCHER_PREFIX, data_area_id=DATA_AREA_ID,
    )
    kilder = hent_oprindelige_fakturaposter(
        fakturadato_fra=FAKTURADATO_FRA,
        fakturadato_til=FAKTURADATO_TIL,
        data_area_id=DATA_AREA_ID,
    )
    kildeindeks = _byg_kildeindeks(kilder)
    dokumentreferencer = hent_dokumentreferencer(
        ref_table_id=6084,
        oprettet_fra=FAKTURADATO_FRA,
        oprettet_til=FAKTURADATO_TIL,
        dokumenttyper=DOKUMENTTYPER,
        data_area_id=DATA_AREA_ID,
    )
    dokumentindeks = _grupper(dokumentreferencer, "ReferenceRecId")
    output: list[dict[str, str]] = []
    statistik = {"fakturaer": len(fakturaer), "kilde_fallback": 0, "dokument_fallback": 0, "uden_oioubl": 0}

    for faktura in fakturaer:
        kilde = _find_entydig_kilde(faktura, kildeindeks.get(_nøgle(faktura), []))
        if kilde is None:
            statistik["kilde_fallback"] += 1
            fallback = hent_oprindelige_fakturaposter(
                fakturanummer=faktura["Fakturanummer"],
                kreditorkonto=faktura["Kreditorkonto"],
                data_area_id=DATA_AREA_ID,
                top=20,
            )
            kilde = _find_entydig_kilde(faktura, fallback)
        if kilde is None or not kilde.get("RecIdLoc"):
            statistik["uden_oioubl"] += 1
            continue

        docs = dokumentindeks.get(kilde["RecIdLoc"], [])
        if not docs:
            statistik["dokument_fallback"] += 1
            docs = search_dokumenter(
                ref_rec_id=kilde["RecIdLoc"],
                tabel="ventende_kreditorfaktura",
                dokumenttyper=DOKUMENTTYPER,
                data_area_id=DATA_AREA_ID,
                hent_dokumentplacering=False,
            )
        docs = [d for d in docs if d.get("ErFysiskFil") and str(d.get("TypeId") or "").casefold() == "oioubl"]
        if len(docs) != 1:
            statistik["uden_oioubl"] += 1
            continue
        info = get_dokumentinformation(docs[0]["ValueRecId"], domain_suffix=DOMAIN_SUFFIX)
        if not info.document_path:
            statistik["uden_oioubl"] += 1
            continue
        output.append({
            "fakturanummer": faktura["Fakturanummer"],
            "kreditorkonto": faktura["Kreditorkonto"],
            "filnavn": info.original_file_name,
            "dokumentsti": info.document_path,
        })

    print("=" * 78)
    print("RESULTAT TIL SENERE ATS-KØ")
    print("=" * 78)
    pprint(output, sort_dicts=False, width=160)
    print("=" * 78)
    print("STATISTIK")
    print("=" * 78)
    statistik["outputrækker"] = len(output)
    pprint(statistik, sort_dicts=False)


def _byg_kildeindeks(kilder: list[dict[str, Any]]) -> dict[tuple[str, str, str, Decimal | None], list[dict[str, Any]]]:
    result: dict[tuple[str, str, str, Decimal | None], list[dict[str, Any]]] = {}
    for kilde in kilder:
        result.setdefault(_nøgle(kilde), []).append(kilde)
    return result


def _nøgle(row: dict[str, Any]) -> tuple[str, str, str, Decimal | None]:
    return (
        str(row.get("Fakturanummer") or "").strip().casefold(),
        str(row.get("Kreditorkonto") or "").strip().casefold(),
        str(row.get("Fakturadato") or "")[:10],
        _decimal_abs(row.get("Beløb")),
    )


def _find_entydig_kilde(faktura: dict[str, Any], kandidater: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [k for k in kandidater if _nøgle(k) == _nøgle(faktura)]
    return matches[0] if len(matches) == 1 else None


def _decimal_abs(value: Any) -> Decimal | None:
    try:
        return abs(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _grupper(rows: list[dict[str, Any]], field: str) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        value = row.get(field)
        if isinstance(value, int) and value > 0:
            result.setdefault(value, []).append(row)
    return result


if __name__ == "__main__":
    main()
