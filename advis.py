from api_client import get


# ------------------------------------------------------------
# BUILD FILTER QUERY (D365 kompatibel)
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
    # AdviceText (beholder wildcard '*')
    # ------------------------------------------------------------
    if advice_text:
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
    # BUILD QUERY (vigtigt: $top først!)
    # ------------------------------------------------------------
    query_parts = []

    if top:
        query_parts.append(f"$top={top}")

    if filters:
        filter_string = " and ".join(filters)
        query_parts.append(f"$filter={filter_string}")

    if query_parts:
        return "?" + "&".join(query_parts)

    return ""


# ------------------------------------------------------------
# GET ADVIS
# ------------------------------------------------------------
def get_advis(
    identification_number=None,
    advice_text=None,
    handled=None,
    extra_filters=None,
    top=None,
    raw=True
):
    endpoint = "CustAdviceDataEntities_FUJ"

    query = build_filter(
        identification_number=identification_number,
        advice_text=advice_text,
        handled=handled,
        extra_filters=extra_filters,
        top=top
    )

    endpoint += query

    # ------------------------------------------------------------
    # DEBUG (meget vigtigt!)
    # ------------------------------------------------------------
    print("\n--- BUILD ADVIS REQUEST ---")
    print("Endpoint:", endpoint)

    data = get(endpoint)

    return data