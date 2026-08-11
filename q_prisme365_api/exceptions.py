"""Projektspecifikke fejl for Prisme 365 API."""


class PrismeApiError(RuntimeError):
    """Grundfejl for alle Prisme API-fejl."""

    def __init__(
        self,
        message: str,
        method: str = "",
        endpoint: str = "",
        status_code: int | None = None,
        response_text: str = "",
    ) -> None:
        """
        Opret en Prisme API-fejl.

        Args:
            message:
                En kort beskrivelse af fejlen.

            method:
                HTTP-metoden, eksempelvis GET,
                POST, PATCH eller DELETE.

            endpoint:
                Det endpoint som blev kaldt.

            status_code:
                HTTP-statuskoden fra Prisme.

            response_text:
                Fejlteksten returneret af Prisme.
        """

        self.message = message
        self.method = method
        self.endpoint = endpoint
        self.status_code = status_code

        if response_text:
            self.response_text = str(
                response_text
            )[:1000]
        else:
            self.response_text = ""

        details = [message]

        if method:
            details.append(
                f"Metode: {method}"
            )

        if endpoint:
            details.append(
                f"Endpoint: {endpoint}"
            )

        if status_code is not None:
            details.append(
                f"HTTP-status: {status_code}"
            )

        if self.response_text:
            details.append(
                f"Svar: {self.response_text}"
            )

        complete_message = " | ".join(
            details
        )

        super().__init__(
            complete_message
        )


class PrismeAuthenticationError(
    PrismeApiError
):
    """Token eller godkendelse blev afvist."""


class PrismePermissionError(
    PrismeApiError
):
    """Brugeren mangler rettigheder."""


class PrismeNotFoundError(
    PrismeApiError
):
    """Den ønskede post blev ikke fundet."""


class PrismeRateLimitError(
    PrismeApiError
):
    """Prisme har begrænset antal API-kald."""


class PrismeResponseError(
    PrismeApiError
):
    """Prisme returnerede et ugyldigt svar."""


class PrismeServerError(
    PrismeApiError
):
    """Prisme returnerede en serverfejl."""


class KontostrengIkkeFundetError(
    ValueError
):
    """Kontostrengen blev ikke fundet."""


class KontostrengIkkeEntydigError(
    ValueError
):
    """Kontostrengen matcher flere kombinationer."""


class UgyldigKontostrengError(
    ValueError
):
    """Kontostrengens format er ugyldigt."""