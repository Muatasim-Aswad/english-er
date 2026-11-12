from typing import Annotated

from fastapi import Depends

from english_er.modules.capture.control import CaptureControl
from english_er.platform.dependencies import RuntimeDep


def get_capture_control(runtime: RuntimeDep) -> CaptureControl | None:
    return None if runtime is None else CaptureControl(runtime.capture_marker)


CaptureDep = Annotated[CaptureControl | None, Depends(get_capture_control)]
