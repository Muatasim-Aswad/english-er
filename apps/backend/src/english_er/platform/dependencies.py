from typing import Annotated

from fastapi import Depends

from english_er.platform.resources import ApiRuntime


async def get_runtime() -> ApiRuntime | None:
    raise RuntimeError("API runtime dependency was not configured")


RuntimeDep = Annotated[ApiRuntime | None, Depends(get_runtime)]
