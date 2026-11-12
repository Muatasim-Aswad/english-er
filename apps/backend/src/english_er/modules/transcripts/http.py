"""Implemented version-1 local review routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Path, Query, Response, status

from english_er.modules.transcripts.dependencies import ReviewDep
from english_er.modules.transcripts.domain import ProcessingStatus, ReviewedState
from english_er.modules.transcripts.dto import (
    PageMetadata,
    ReviewUpdate,
    TranscriptDetail,
    TranscriptPage,
    TranscriptSummary,
    TranscriptTextUpdate,
)
from english_er.modules.transcripts.health import DatabaseHealth, HealthResponse
from english_er.modules.transcripts.service import ReviewService
from english_er.platform.responses import (
    NOT_FOUND_RESPONSE,
    UNAVAILABLE_RESPONSE,
    VALIDATION_RESPONSE,
)
from english_er.platform.schemas import ErrorResponse
from english_er.shared.errors import AppError

router = APIRouter(prefix="/api/v1")


def _require_service(service: ReviewService | None) -> ReviewService:
    if service is None:
        raise AppError("not_ready", "The application runtime is unavailable.")
    return service


@router.get(
    "/health",
    response_model=HealthResponse,
    responses=UNAVAILABLE_RESPONSE,
    tags=["system"],
)
async def get_health(
    service: ReviewDep,
) -> HealthResponse:
    if service is None:
        return HealthResponse(database=DatabaseHealth.UNAVAILABLE)
    return await service.health()


@router.get(
    "/transcripts",
    response_model=TranscriptPage,
    responses=VALIDATION_RESPONSE | UNAVAILABLE_RESPONSE,
    tags=["transcripts"],
)
async def list_transcripts(
    service: ReviewDep,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    processing_status: Annotated[ProcessingStatus | None, Query(alias="status")] = None,
    reviewed: Annotated[ReviewedState | None, Query()] = None,
) -> TranscriptPage:
    if service is None:
        return TranscriptPage(items=[], metadata=PageMetadata(next_cursor=None))
    return await service.list_transcripts(
        cursor=cursor,
        limit=limit,
        status=processing_status,
        reviewed=reviewed,
    )


@router.get(
    "/transcripts/{id}",
    response_model=TranscriptDetail,
    responses=NOT_FOUND_RESPONSE | VALIDATION_RESPONSE | UNAVAILABLE_RESPONSE,
    tags=["transcripts"],
)
async def get_transcript(
    transcript_id: Annotated[UUID, Path(alias="id")],
    service: ReviewDep,
) -> TranscriptDetail:
    service = _require_service(service)
    return await service.get_transcript(transcript_id)


@router.put(
    "/transcripts/{id}/text",
    response_model=TranscriptDetail,
    responses={
        **NOT_FOUND_RESPONSE,
        **VALIDATION_RESPONSE,
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The expected transcript revision is stale.",
        },
        **UNAVAILABLE_RESPONSE,
    },
    tags=["transcripts"],
)
async def put_transcript_text(
    transcript_id: Annotated[UUID, Path(alias="id")],
    update: Annotated[TranscriptTextUpdate, Body()],
    service: ReviewDep,
) -> TranscriptDetail:
    service = _require_service(service)
    return await service.update_text(
        transcript_id,
        update.text,
        update.expected_revision,
    )


@router.put(
    "/transcripts/{id}/review",
    response_model=TranscriptDetail,
    responses=NOT_FOUND_RESPONSE | VALIDATION_RESPONSE | UNAVAILABLE_RESPONSE,
    tags=["transcripts"],
)
async def put_transcript_review(
    transcript_id: Annotated[UUID, Path(alias="id")],
    update: Annotated[ReviewUpdate, Body()],
    service: ReviewDep,
) -> TranscriptDetail:
    service = _require_service(service)
    return await service.set_reviewed(transcript_id, update.reviewed)


@router.post(
    "/transcripts/{id}/retry",
    response_model=TranscriptSummary,
    responses={
        **NOT_FOUND_RESPONSE,
        **VALIDATION_RESPONSE,
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The transcript is not in the failed state.",
        },
        **UNAVAILABLE_RESPONSE,
    },
    tags=["transcripts"],
)
async def retry_transcript(
    transcript_id: Annotated[UUID, Path(alias="id")],
    service: ReviewDep,
) -> TranscriptSummary:
    service = _require_service(service)
    return await service.retry(transcript_id)


@router.delete(
    "/transcripts/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=NOT_FOUND_RESPONSE | VALIDATION_RESPONSE | UNAVAILABLE_RESPONSE,
    tags=["transcripts"],
)
async def delete_transcript(
    transcript_id: Annotated[UUID, Path(alias="id")],
    service: ReviewDep,
) -> Response:
    service = _require_service(service)
    await service.delete(transcript_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health/live", response_model=dict[str, str], tags=["system"])
async def get_liveness() -> dict[str, str]:
    return {"api": "ok"}


@router.get(
    "/health/ready", response_model=HealthResponse, responses=UNAVAILABLE_RESPONSE, tags=["system"]
)
async def get_readiness(service: ReviewDep) -> HealthResponse:
    health = await get_health(service)
    if health.database != DatabaseHealth.OK:
        raise AppError("not_ready", "The transcript database is not ready.")
    return health
