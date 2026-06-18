from q_prisme365_api.api_client import patch

def build_advis_body(recid, handled):
    return {
        "dataAreaId": "had",
        "Handled": "Yes" if handled else "No",
        "RecIdLoc": recid
    }


def update_advis(recid: int, handled: bool) -> bool:
    """
      Args:
        recid (int):
            RecId på adviset (unik ID fra Prisme)

        handled (bool):
            True  = marker som behandlet - Skriv fx handled=True (man kan nøjes med blot at skrive True)
            False = marker som ikke behandlet

    Returns:
        bool:
            True hvis opdatering lykkedes
            False hvis fejl
    """
    recid = int(recid)  # ✅ TVING TIL INT (vigtigt)
    endpoint = f"CustAdviceDataEntities_FUJ(RecIdLoc={recid},dataAreaId='had')"

    body = {
        "dataAreaId": "had",
        "Handled": "Yes" if handled else "No",
        "RecIdLoc": recid
    }

    return patch(endpoint, body)