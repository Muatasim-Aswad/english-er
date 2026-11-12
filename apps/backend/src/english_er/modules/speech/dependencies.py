from typing import Annotated

from fastapi import Depends

from english_er.modules.speech.service import AudioService
from english_er.platform.dependencies import RuntimeDep
from english_er.shared.errors import AppError


def get_audio_service(runtime: RuntimeDep) -> AudioService:
    if runtime is None or runtime.synthesizer is None:
        raise AppError("speech_unavailable", "Speech generation is unavailable.")
    return AudioService(
        runtime.database.sessions,
        runtime.audio_root,
        runtime.synthesizer,
        runtime.audio_lock,
        queue_timeout=runtime.speech_queue_timeout,
        synthesis_timeout=runtime.speech_timeout,
    )


AudioDep = Annotated[AudioService, Depends(get_audio_service)]
