"""One privacy-safe error format and log record at the HTTP boundary."""

import json
import logging
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from english_er.platform.schemas import ErrorBody, ErrorResponse, ValidationIssue
from english_er.shared.errors import AppError, Code

logger = logging.getLogger("english_er.http")

STATUS_BY_CODE: dict[Code, int] = {
    "not_ready": 503,
    "not_found": 404,
    "validation_error": 422,
    "invalid_cursor": 422,
    "revision_conflict": 409,
    "invalid_state": 409,
    "database_unavailable": 503,
    "capture_unavailable": 503,
    "capture_conflict": 409,
    "speech_unavailable": 503,
    "correction_unavailable": 409,
    "speech_generation_failed": 503,
    "speech_timeout": 504,
    "busy": 503,
    "invalid_host": 400,
    "invalid_origin": 403,
    "request_too_large": 413,
    "request_timeout": 504,
    "rate_limited": 429,
    "internal_error": 500,
}


def error_response(
    error: AppError,
    request_id: str,
    *,
    status: int | None = None,
    issues: list[ValidationIssue] | None = None,
) -> JSONResponse:
    response_status = status or STATUS_BY_CODE[error.code]
    body = ErrorResponse(
        error=ErrorBody(
            status=response_status,
            code=error.code,
            message=error.message,
            request_id=request_id,
            details=error.public,
            issues=issues,
        )
    )
    if response_status >= 500:
        logger.error(
            json.dumps(
                {
                    "event": "request_failed",
                    "code": error.code,
                    "status": response_status,
                    "request_id": request_id,
                }
            )
        )
    return JSONResponse(
        status_code=response_status,
        content=body.model_dump(exclude_none=True),
        headers={"X-Request-ID": request_id},
    )


async def handle_error(request: Request, error: Exception) -> JSONResponse:
    request_id = request.scope.get("request_id", str(uuid4()))
    if isinstance(error, AppError):
        return error_response(error, request_id)
    if isinstance(error, RequestValidationError):
        issues = [
            ValidationIssue(
                location=[str(item["loc"][0])] if item["loc"] else [], code=str(item["type"])
            )
            for item in error.errors()
        ]
        return error_response(
            AppError("validation_error", "The request is invalid."), request_id, issues=issues
        )
    if isinstance(error, HTTPException):
        code: Code = "not_found" if error.status_code == 404 else "invalid_state"
        return error_response(
            AppError(
                code,
                "Not found." if error.status_code == 404 else "The request cannot be completed.",
            ),
            request_id,
            status=error.status_code,
        )
    return error_response(
        AppError("internal_error", "The service could not complete the request."), request_id
    )
