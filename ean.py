from api_client import get

# ------------------------------------------------------------
# DTO MAPPING
# ------------------------------------------------------------
def map_ean(item):
    return {
        "ean": item.get("EANNumber"),
        "name": item.get("Name"),
        "rec_id": item.get("RecId")
    }


# ------------------------------------------------------------
# GET EAN
# ------------------------------------------------------------
def get_ean(ean: str = None, raw: bool = False):
    endpoint = "OMOperationUnitEANNumDatasEntity_FUJ"

    # filter hvis EAN angivet
    if ean:
        endpoint += f"?$filter=EANNumber eq '{ean}'"

    data = get(endpoint)

    if raw:
        return data

    values = data.get("value", [])
    return [map_ean(x) for x in values]