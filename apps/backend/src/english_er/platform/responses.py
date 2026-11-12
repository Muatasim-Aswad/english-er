from typing import Any

from fastapi import status

from english_er.platform.schemas import ErrorResponse

UNAVAILABLE_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ErrorResponse,
        "description": "The persistence service is not available.",
    }
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The transcript does not exist.",
    }
}
VALIDATION_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "The request is invalid.",
    }
}


BOUNDARY_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse, "description": description}
    for code, description in {
        400: "The host or request is invalid.",
        403: "The origin is not allowed.",
        413: "The request exceeds the size limit.",
        429: "The request rate limit was reached.",
        500: "An unexpected failure occurred.",
        503: "The service is unavailable or busy.",
        504: "The request or synthesis deadline expired.",
    }.items()
}
