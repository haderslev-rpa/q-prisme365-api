from ean import get_ean
from advis import get_advis
from advis_update import update_advis


if __name__ == "__main__":

    print("\n🚀 TEST START")

    # ------------------------------------------------------------
    # 1. HENT EAN
    # ------------------------------------------------------------
    #print("\n📦 Henter EAN...")
    #ean_data = get_ean()
    #print(ean_data[:3])


    # ------------------------------------------------------------
    # 2. HENT SPECIFIK EAN
    # ------------------------------------------------------------
    print("\n🔍 Henter specifik EAN...")
    ean_single = get_ean("5798005223825")
    print(ean_single)


    # ------------------------------------------------------------
    # 3. HENT ADVIS (RAW)
    # ------------------------------------------------------------
    print("\n📨 Henter advis...")
    advis_data = get_advis()
    print(advis_data)


    # ------------------------------------------------------------
    # 4. HENT ADVIS MED FILTER
    # ------------------------------------------------------------
    print("\n📨 Henter uhandlede advis...")
    advis_filtered = get_advis(handled=False)
    print(advis_filtered)


    # ------------------------------------------------------------
    # 5. UPDATE ADVIS
    # ------------------------------------------------------------
    print("\n✏️ Opdaterer advis...")
    success = update_advis(123456789, True)
    print("Success:", success)