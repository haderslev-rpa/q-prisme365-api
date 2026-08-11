"""Hjælpefunktioner til OData-filtre og endpoints."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime
from typing import Any, TypeVar
from urllib.parse import quote


T = TypeVar("T")

DEFAULT_TOP = 1000


def escape_odata_text(value: str) -> str:
    """Escape apostroffer i en OData-tekstværdi."""

    return str(value).replace("'", "''")


def quote_odata_text(value: str) -> str:
    """Omgiv en tekstværdi med apostroffer."""

    escaped_value = escape_odata_text(value)

    return f"'{escaped_value}'"


def format_odata_date(
    value: date | datetime,
) -> str:
    """Formatér en dato til Dynamics OData-format."""

    if isinstance(value, datetime):
        return value.isoformat(
            timespec="seconds"
        )

    return value.isoformat()


def eq_text(
    field: str,
    value: str,
) -> str:
    """Byg et tekstfilter med præcis lighed."""

    quoted_value = quote_odata_text(value)

    return f"{field} eq {quoted_value}"


def string_equals(
    field: str,
    value: str,
) -> str:
    """
    Byg et tekstfilter med præcis lighed.

    Navnet bevares til eksisterende filer,
    eksempelvis debitor.py.
    """

    return eq_text(
        field,
        value,
    )


def eq_number(
    field: str,
    value: int,
) -> str:
    """Byg et numerisk filter med præcis lighed."""

    return f"{field} eq {int(value)}"


def number_equals(
    field: str,
    value: int,
) -> str:
    """Alternativt navn til numerisk lighed."""

    return eq_number(
        field,
        value,
    )


def eq_boolean(
    field: str,
    value: bool,
) -> str:
    """Byg et boolsk OData-filter."""

    if not isinstance(value, bool):
        raise TypeError(
            "value skal være True eller False."
        )

    if value:
        formatted_value = "true"
    else:
        formatted_value = "false"

    return f"{field} eq {formatted_value}"


def eq_no_yes_enum(
    field: str,
    value: bool,
) -> str:
    """Byg et Dynamics 365 NoYes-filter."""

    if not isinstance(value, bool):
        raise TypeError(
            "value skal være True eller False."
        )

    if value:
        enum_value = "Yes"
    else:
        enum_value = "No"

    return (
        f"{field} eq "
        "Microsoft.Dynamics.DataEntities."
        f"NoYes'{enum_value}'"
    )


def eq_date(
    field: str,
    value: date | datetime,
) -> str:
    """Byg et datofilter med præcis lighed."""

    formatted_value = format_odata_date(
        value
    )

    return f"{field} eq {formatted_value}"


def ge_date(
    field: str,
    value: date | datetime,
) -> str:
    """Byg et større-end-eller-lig-med filter."""

    formatted_value = format_odata_date(
        value
    )

    return f"{field} ge {formatted_value}"


def le_date(
    field: str,
    value: date | datetime,
) -> str:
    """Byg et mindre-end-eller-lig-med filter."""

    formatted_value = format_odata_date(
        value
    )

    return f"{field} le {formatted_value}"


def and_filter(
    *expressions: str | None,
) -> str:
    """Saml udfyldte filtre med and."""

    values = []

    for expression in expressions:
        if expression is None:
            continue

        stripped_expression = expression.strip()

        if stripped_expression:
            values.append(
                stripped_expression
            )

    return " and ".join(values)


def or_filter(
    *expressions: str | None,
) -> str:
    """Saml udfyldte filtre med parenteseret or."""

    values = []

    for expression in expressions:
        if expression is None:
            continue

        stripped_expression = expression.strip()

        if stripped_expression:
            values.append(
                stripped_expression
            )

    if not values:
        return ""

    if len(values) == 1:
        return values[0]

    joined_values = " or ".join(
        values
    )

    return f"({joined_values})"


def or_equals_text(
    field: str,
    values: Iterable[str],
) -> str:
    """Byg et or-filter for flere tekstværdier."""

    unique_values = list(
        dict.fromkeys(values)
    )

    expressions = []

    for value in unique_values:
        expressions.append(
            eq_text(
                field,
                value,
            )
        )

    return or_filter(
        *expressions
    )


def chunked(
    values: Sequence[T],
    size: int,
) -> Iterator[list[T]]:
    """Opdel en liste i mindre grupper."""

    if size <= 0:
        raise ValueError(
            "size skal være større end 0."
        )

    for index in range(
        0,
        len(values),
        size,
    ):
        yield list(
            values[index : index + size]
        )


def extract_odata_rows(
    response: Any,
) -> list[dict[str, Any]]:
    """Udtræk rækker fra et OData-svar."""

    if response is None:
        return []

    if isinstance(response, list):
        rows = []

        for row in response:
            if isinstance(row, dict):
                rows.append(row)

        return rows

    if isinstance(response, dict):
        value = response.get("value")

        if isinstance(value, list):
            rows = []

            for row in value:
                if isinstance(row, dict):
                    rows.append(row)

            return rows

        return [response]

    raise TypeError(
        "Ukendt OData-svarformat: "
        f"{type(response).__name__}"
    )


def build_odata_endpoint(
    entity: str,
    filters: Iterable[str] | None = None,
    top: int | None = DEFAULT_TOP,
    select: Iterable[str] | None = None,
    order_by: str | None = None,
) -> str:
    """
    Byg et komplet OData-endpoint.

    Funktionen bevarer det format,
    som api_client.get forventer.
    """

    entity_value = str(entity).strip()

    if not entity_value:
        raise ValueError(
            "entity skal udfyldes."
        )

    query_parts = []

    if top is not None:
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

        query_parts.append(
            f"$top={top_value}"
        )

    filter_values = []

    if filters is not None:
        for filter_value in filters:
            if filter_value is None:
                continue

            clean_filter = str(
                filter_value
            ).strip()

            if clean_filter:
                filter_values.append(
                    clean_filter
                )

    if filter_values:
        filter_expression = " and ".join(
            filter_values
        )

        query_parts.append(
            f"$filter={filter_expression}"
        )

    selected_fields = []

    if select is not None:
        for field in select:
            clean_field = str(
                field
            ).strip()

            if clean_field:
                selected_fields.append(
                    clean_field
                )

    if selected_fields:
        query_parts.append(
            "$select="
            + ",".join(selected_fields)
        )

    if order_by:
        clean_order_by = str(
            order_by
        ).strip()

        if clean_order_by:
            query_parts.append(
                f"$orderby={clean_order_by}"
            )

    if not query_parts:
        return entity_value

    return (
        entity_value
        + "?"
        + "&".join(query_parts)
    )


def encode_odata_value(
    value: str,
) -> str:
    """
    URL-encode en OData-værdi.

    Funktionen bør kun bruges, når
    manuel encoding er nødvendig.
    """

    return quote(
        str(value),
        safe="'(),-$*",
    )