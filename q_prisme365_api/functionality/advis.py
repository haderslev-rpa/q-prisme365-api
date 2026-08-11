"""Søgning efter adviser i Prisme 365."""

import logging
from typing import Any

from q_prisme365_api.api_client import get


logger = logging.getLogger(__name__)


ADVIS_ENDPOINT = "CustAdviceDataEntities_FUJ"

NO_YES_ENUM = (
    "Microsoft.Dynamics.DataEntities.NoYes"
)


def build_filter(
    identification_number=None,
    advice_text=None,
    handled=None,
    extra_filters=None,
    top=None,
):
    """
    Byg søgeparametre til advis-endpointet.

    Args:
        identification_number:
            Identifikationsnummeret i Prisme.

        advice_text:
            Advisteksten. Eventuelle jokertegn
            som stjernetegn bevares.

        handled:
            True giver Yes.
            False giver No.
            None betyder intet filter.

        extra_filters:
            Ekstra filtre som dictionary
            med feltnavn og værdi.

        top:
            Maksimalt antal rækker.

    Returns:
        En query string, som starter med
        spørgsmålstegn, eller en tom streng.
    """

    filters = []

    identification_value = _clean_optional_text(
        identification_number
    )

    if identification_value is not None:
        filters.append(
            _build_text_filter(
                "IdentificationNumber",
                identification_value,
            )
        )

    advice_value = _clean_optional_text(
        advice_text
    )

    if advice_value is not None:
        filters.append(
            _build_text_filter(
                "AdviceText",
                advice_value,
            )
        )

    if handled is not None:
        handled_filter = (
            _build_handled_filter(handled)
        )
        filters.append(handled_filter)

    if extra_filters is not None:
        extra_filter_values = (
            _build_extra_filters(
                extra_filters
            )
        )
        filters.extend(extra_filter_values)

    query_parts = []

    if top is not None:
        validated_top = _validate_top(top)

        query_parts.append(
            f"$top={validated_top}"
        )

    if filters:
        filter_string = " and ".join(filters)

        query_parts.append(
            f"$filter={filter_string}"
        )

    if not query_parts:
        return ""

    return "?" + "&".join(query_parts)


def get_advis(
    identification_number=None,
    advice_text=None,
    handled=None,
    extra_filters=None,
    top=None,
    raw=True,
):
    """
    Hent adviser fra Prisme 365.

    Funktionsnavnet og argumenterne er bevaret,
    så eksisterende processer fortsat virker.

    Args:
        identification_number:
            Valgfrit identifikationsnummer.

        advice_text:
            Valgfri advistekst.

        handled:
            True søger efter Yes.
            False søger efter No.
            None undlader filteret.

        extra_filters:
            Valgfri dictionary med ekstra filtre.

        top:
            Valgfrit maksimalt antal rækker.

        raw:
            Bevares for kompatibilitet.
            Resultatet returneres uændret.

    Returns:
        Data fra api_client.get.
    """

    query = build_filter(
        identification_number=(
            identification_number
        ),
        advice_text=advice_text,
        handled=handled,
        extra_filters=extra_filters,
        top=top,
    )

    endpoint = ADVIS_ENDPOINT + query

    logger.info(
        "Henter adviser fra endpoint: %s",
        endpoint,
    )

    data = get(endpoint)

    row_count = _get_result_count(data)

    if row_count is not None:
        logger.info(
            "Advis-søgning returnerede %s rækker",
            row_count,
        )
    else:
        logger.info(
            "Advis-søgning returnerede rå data"
        )

    return data


def _build_handled_filter(
    handled,
):
    """
    Byg filter til Dynamics 365 NoYes-enum.

    True bliver Yes.
    False bliver No.
    """

    if not isinstance(handled, bool):
        raise TypeError(
            "handled skal være True, False "
            "eller None."
        )

    if handled:
        enum_value = "Yes"
    else:
        enum_value = "No"

    return (
        f"Handled eq {NO_YES_ENUM}"
        f"'{enum_value}'"
    )


def _build_extra_filters(
    extra_filters,
):
    """
    Byg ekstra tekstfiltre.

    extra_filters skal være en dictionary,
    eksempelvis:

    {
        "AccountNumber": "123",
        "CurrencyCode": "DKK",
    }
    """

    if not isinstance(extra_filters, dict):
        raise TypeError(
            "extra_filters skal være en dict "
            "eller None."
        )

    filters = []

    for field_name, field_value in (
        extra_filters.items()
    ):
        clean_field_name = str(
            field_name
        ).strip()

        if not clean_field_name:
            raise ValueError(
                "Et feltnavn i extra_filters "
                "må ikke være tomt."
            )

        if field_value is None:
            continue

        clean_value = str(field_value)

        filters.append(
            _build_text_filter(
                clean_field_name,
                clean_value,
            )
        )

    return filters


def _build_text_filter(
    field_name,
    value,
):
    """
    Byg et sikkert OData-tekstfilter.

    Apostroffer escapes til to apostroffer.
    Jokertegn som stjernetegn bevares.
    """

    escaped_value = _escape_odata_text(
        str(value)
    )

    return (
        f"{field_name} eq "
        f"'{escaped_value}'"
    )


def _escape_odata_text(
    value,
):
    """
    Escape apostroffer til OData.

    Eksempel:
        Rune's advis

    Bliver:
        Rune''s advis
    """

    return str(value).replace(
        "'",
        "''",
    )


def _clean_optional_text(
    value,
):
    """
    Normalisér valgfri tekst.

    None og tom tekst giver None.
    Andre værdier bliver tekst.
    """

    if value is None:
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    return text_value


def _validate_top(
    top,
):
    """Kontrollér maksimal antal rækker."""

    if isinstance(top, bool):
        raise TypeError(
            "top skal være et positivt heltal."
        )

    try:
        top_value = int(top)
    except (TypeError, ValueError) as error:
        raise TypeError(
            "top skal være et positivt heltal."
        ) from error

    if top_value <= 0:
        raise ValueError(
            "top skal være større end 0."
        )

    return top_value


def _get_result_count(
    data,
):
    """Find antal rækker, når resultatet er en liste."""

    if isinstance(data, list):
        return len(data)

    return None