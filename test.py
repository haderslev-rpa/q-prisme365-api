from pprint import pprint

# Importerer vores funktioner fra de andre filer
from ean import get_ean
from advis import get_advis
from advis_update import update_advis


"""
============================================================
TEST.PY = DIN DEBUG / TEST FIL
============================================================

Denne fil bruges til:

✅ At teste API kald
✅ At debugge data
✅ At se hvad API returnerer

Du kan selv styre hvad der køres ved at kommentere/afkommentere.

Den bruges IKKE i produktion – kun til udvikling.
"""


if __name__ == "__main__":

    print("\n🚀 TEST START")

    # ============================================================
    # 1. TEST: HENT EAN (STANDARD / DTO OUTPUT)
    # ============================================================
    #print("\n📦 Henter EAN (standard output)...")

    #ean_data = get_ean()

    # Antal records
    #print("Antal EAN:", len(ean_data))

    # Print kun de første 5 (meget vigtigt!)
    #pprint(ean_data[:5], width=120)


    # ============================================================
    # 2. TEST: HENT EN SPECIFIK EAN
    # ============================================================
    #print("\n🔍 Henter specifik EAN...")

    #specific_ean = get_ean("123456")  # indsæt en rigtig EAN

    #pprint(specific_ean, width=120)


    # ============================================================
    # 3. TEST: HENT ADVIS (MED FILTER)
    # ============================================================
    print("\n📨 Henter advis med filter...")

    advis_data = get_advis(
        #identification_number="",   # filtrer på ID
        advice_text="Rune*",                  # wildcard (starter med)
        handled=False,                        # kun uhandlede
        top=10000                             # maks antal
    )

    # D365 returnerer data i "value"
    values = advis_data.get("value", [])

    print("Antal advis:", len(values))

    # Print kun første 5
    pprint(values[:5], width=120)

   
    # ============================================================
    # 5. TEST: UPDATE ADVIS (PATCH)
    # ============================================================
    print("\n✏️ Opdaterer advis (manuel test)...")

    # ------------------------------------------------------------
    # HER SÆTTER DU SELV ID
    # ------------------------------------------------------------
    test_recid = 5637521826   # 👈 indsæt dit eget RecId her

    # hvis du har sat et manuelt ID → brug det
    if test_recid:
        print("Bruger manuelt RecId:", test_recid)

        success = update_advis(recid=test_recid, handled=True)

        print("Success:", success)

    # ellers fallback til første fra listen
    elif values:
        recid = values[0].get("RecId")

        print("Fallback RecId:", recid)

        success = update_advis(recid, True)

        print("Success:", success)

    else:
        print("❌ Ingen advis fundet → kan ikke teste update")


    print("\n✅ TEST FÆRDIG")


