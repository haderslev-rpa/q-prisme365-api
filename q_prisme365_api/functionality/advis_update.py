"""Opdatering af adviser i Prisme 365."""

import logging

from q_prisme365_api.api_client import patch


logger = logging.getLogger(__name__)


ADVIS_ENDPOINT = "CustAdviceDataEntities_FUJ"
DATA_AREA_ID = "had"


def build_advis_body(
    recid,
    handled,
):
    """
    Byg PATCH-indhold til et advis.

    Args:
        recid:
            Advisets unikke RecIdLoc.

        handled:
            True giver Yes.
            False giver No.

    Returns:
        En dictionary med de felter,
        som Prisme skal opdatere.
    """

    validated_recid = _validate_recid(
        recid
    )
    validated_handled = _validate_handled(
        handled
    )

    if validated_handled:
        handled_value = "Yes"
    else:
        handled_value = "No"

    return {
        "dataAreaId": DATA_AREA_ID,
        "Handled": handled_value,
        "RecIdLoc": validated_recid,
    }


def update_advis(
    recid: int,
    handled: bool,
) -> bool:
    """
    Opdatér behandlingsstatus på et advis.

    Args:
        recid:
            RecIdLoc på adviset.

        handled:
            True markerer adviset som behandlet.
            False markerer adviset som ubehandlet.

    Returns:
        True når PATCH-kaldet lykkes.

    Raises:
        TypeError:
            Hvis handled ikke er en bool.

        ValueError:
            Hvis recid ikke er et positivt heltal.

        PrismeApiError:
            Hvis Prisme returnerer en API-fejl.
    """

    validated_recid = _validate_recid(
        recid
    )
    validated_handled = _validate_handled(
        handled
    )

    endpoint = build_advis_endpoint(
        validated_recid
    )

    body = build_advis_body(
        validated_recid,
        validated_handled,
    )

    logger.info(
        "Opdaterer advis med RecIdLoc %s "
        "til Handled=%s",
        validated_recid,
        body["Handled"],
    )

    result = patch(
        endpoint,
        body,
    )

    if result is not True:
        raise RuntimeError(
            "PATCH-kaldet til advis returnerede "
            "ikke True."
        )

    logger.info(
        "Advis med RecIdLoc %s blev opdateret",
        validated_recid,
    )

    return True


def build_advis_endpoint(
    recid,
):
    """
    Byg endpointet til ét advis.

    Args:
        recid:
            Advisets unikke RecIdLoc.

    Returns:
        Endpoint med RecIdLoc og dataAreaId.
    """

    validated_recid = _validate_recid(
        recid
    )

    return (
        f"{ADVIS_ENDPOINT}"
        f"(RecIdLoc={validated_recid},"
        f"dataAreaId='{DATA_AREA_ID}')"
    )


def _validate_recid(
    recid,
):
    """
    Kontrollér og konvertér RecIdLoc.

    Bool afvises, selv om bool teknisk
    kan konverteres til et heltal i Python.
    """

    if isinstance(recid, bool):
        raise TypeError(
            "recid skal være et positivt heltal."
        )

    try:
        validated_recid = int(recid)
    except (TypeError, ValueError) as error:
        raise TypeError(
            "recid skal kunne konverteres "
            "til et heltal."
        ) from error

    if validated_recid <= 0:
        raise ValueError(
            "recid skal være større end 0."
        )

    return validated_recid


def _validate_handled(
    handled,
):
    """
    Kontrollér behandlingsstatus.

    Kun de rigtige bool-værdier
    True og False accepteres.
    """

    if not isinstance(handled, bool):
        raise TypeError(
            "handled skal være True eller False."
        )

    return handled