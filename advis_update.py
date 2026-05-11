from api_client import patch

# ------------------------------------------------------------
# BUILD BODY (fra dit diagram)
# ------------------------------------------------------------
def build_advis_body(recid: int, handled: bool):
    return {
        "dataAreaId": "had",
        "Handled": "Yes" if handled else "No",
        "RecIdLoc": recid
    }


# ------------------------------------------------------------
# UPDATE ADVIS
# ------------------------------------------------------------
def update_advis(recid: int, handled: bool):
    endpoint = f"CustAdviceDataEntities_FUJ(RecIdLoc={recid},dataAreaId='had')"

    body = build_advis_body(recid, handled)

    success = patch(endpoint, body)

    if success:
        print("✅ Advis opdateret")
    else:
        print("❌ Fejl ved opdatering")

    return success