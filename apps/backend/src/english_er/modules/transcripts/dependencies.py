from typing import Annotated

from fastapi import Depends

from english_er.modules.transcripts.service import ReviewService
from english_er.platform.dependencies import RuntimeDep


def get_review_service(runtime: RuntimeDep) -> ReviewService | None:
    return None if runtime is None else ReviewService(runtime.database.sessions, runtime.audio_root)


ReviewDep = Annotated[ReviewService | None, Depends(get_review_service)]
