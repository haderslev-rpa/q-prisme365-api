from api_client import get

# ------------------------------------------------------------
# BUILD FILTER QUERY
# ------------------------------------------------------------
def build_filter(
    identification_number=None,
    advice_text=None,
    handled=None,
    extra_filters=None,
    top=None
):
    filters = []

    # ------------------------------------------------------------
    # IdentificationNumber
    # ------------------------------------------------------------
    if identification_number:
        filters.append(f"IdentificationNumber eq '{identification_number}'")

    # ------------------------------------------------------------
    # AdviceText (understøtter wildcard '*')
    # ------------------------------------------------------------
    if advice_text:
        if "*" in advice_text:
            # D365 bruger startswith i stedet
            value = advice_text.replace("*", "")
            filters.append(f"startswith(AdviceText,'{value}')")
        else:
            filters.append(f"AdviceText eq '{advice_text}'")

    # ------------------------------------------------------------
    # Handled (D365 NoYes enum)
    # ------------------------------------------------------------
    if handled is not None:
        value = "Yes" if handled else "No"
        filters.append(
            f"Handled eq Microsoft.Dynamics.DataEntities.NoYes'{value}'"
        )

    # ------------------------------------------------------------
    # Extra filters (generisk)
    # ------------------------------------------------------------
    if extra_filters:
        for key, val in extra_filters.items():
            filters.append(f"{key} eq '{val}'")

    # ------------------------------------------------------------
    # Sammensæt query
    # ------------------------------------------------------------
    query = ""

    if filters:
        query += "$filter=" + " and ".join(filters)

    if top:
        if query:
            query += "&"
        query += f"$top={top}"

    # Prefix med '?'
    if query:
        return "?" + query

    return ""


# ------------------------------------------------------------
# GET ADVIS
# ------------------------------------------------------------
def get_advis(handled=None, extra_filters=None, raw=True):
    endpoint = "CustAdviceDataEntities_FUJ"

    endpoint += build_filter(handled, extra_filters)

    data = get(endpoint)

    if raw:
        return data

    # ------------------------------------------------------------
    # EKSEMPEL PÅ DTO (kommenteret – du kan aktivere senere)
    # ------------------------------------------------------------
    # values = data.get("value", [])
    # return [
    #     {
    #         "rec_id": x.get("RecId"),
    #         "handled": x.get("Handled"),
    #         "message": x.get("Message")
    #     }
    #     for x in values
    # ]

    return data