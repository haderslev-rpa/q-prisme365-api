from q_prisme365_api.api_client import get

def map_ean(item):
    return {
        "ean": item.get("EANNumber"),
        "name": item.get("Name"),
        "rec_id": item.get("RecId")
    }


def get_ean(ean=None, raw=False):
    endpoint = "OMOperationUnitEANNumDatasEntity_FUJ"

    if ean:
        endpoint += f"?$filter=EANNumber eq '{ean}'"

    data = get(endpoint)

    if raw:
        return data

    values = data.get("value", [])
    return [map_ean(x) for x in values]