from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Path, status
from fastapi.responses import FileResponse
from pydantic import Field

from english_er.modules.speech.dependencies import AudioDep
from english_er.platform.responses import (
    NOT_FOUND_RESPONSE,
    UNAVAILABLE_RESPONSE,
    VALIDATION_RESPONSE,
)
from english_er.platform.schemas import ErrorResponse
from english_er.shared.schema import ContractModel


class AudioRequest(ContractModel):
    expected_revision: int = Field(ge=1)


router = APIRouter(prefix="/api/v1")


@router.post(
    "/transcripts/{id}/audio",
    response_class=FileResponse,
    responses={
        status.HTTP_200_OK: {
            "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
            "description": "The persisted corrected-transcript audio.",
        },
        **NOT_FOUND_RESPONSE,
        **VALIDATION_RESPONSE,
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "A current completed correction is not available.",
        },
        **UNAVAILABLE_RESPONSE,
    },
    tags=["speech"],
)
async def post_transcript_audio(
    transcript_id: Annotated[UUID, Path(alias="id")],
    request: Annotated[AudioRequest, Body()],
    service: AudioDep,
) -> FileResponse:
    path = await service.get_or_generate(transcript_id, request.expected_revision)
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{transcript_id}.wav",
        content_disposition_type="inline",
    )
