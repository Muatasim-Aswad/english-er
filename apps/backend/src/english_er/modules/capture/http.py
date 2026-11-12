from typing import Annotated

from fastapi import APIRouter, Body

from english_er.modules.capture.dependencies import CaptureDep
from english_er.modules.capture.dto import CaptureState, CaptureUpdate
from english_er.platform.responses import UNAVAILABLE_RESPONSE, VALIDATION_RESPONSE
from english_er.shared.errors import AppError

router = APIRouter(prefix="/api/v1")


@router.get(
    "/capture",
    response_model=CaptureState,
    responses=UNAVAILABLE_RESPONSE,
    tags=["capture"],
)
async def get_capture(
    control: CaptureDep,
) -> CaptureState:
    if control is None:
        return CaptureState(enabled=False)
    return CaptureState(enabled=control.get())


@router.put(
    "/capture",
    response_model=CaptureState,
    responses=VALIDATION_RESPONSE | UNAVAILABLE_RESPONSE,
    tags=["capture"],
)
async def put_capture(
    update: Annotated[CaptureUpdate, Body()],
    control: CaptureDep,
) -> CaptureState:
    if control is None:
        raise AppError("not_ready", "The application runtime is unavailable.")
    return CaptureState(enabled=control.set(update.enabled))
