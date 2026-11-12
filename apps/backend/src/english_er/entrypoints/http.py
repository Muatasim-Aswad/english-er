"""Compose the loopback HTTP application without opening runtime resources."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from english_er.config import Settings
from english_er.entrypoints.runtime import RuntimeProvider
from english_er.infra.build import VERSION, BuildInfo, served_build
from english_er.modules.capture.http import router as capture_router
from english_er.modules.speech.http import router as speech_router
from english_er.modules.transcripts.http import router as transcripts_router
from english_er.platform.dependencies import get_runtime
from english_er.platform.errors import handle_error
from english_er.platform.http import LocalHttpBoundary
from english_er.platform.resources import ApiRuntime
from english_er.platform.responses import BOUNDARY_RESPONSES
from english_er.shared.errors import AppError


def create_app(
    *,
    runtime: ApiRuntime | None = None,
    database_path: Path | None = None,
    capture_marker: Path | None = None,
    audio_root: Path | None = None,
    static_root: Path | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    config = settings or Settings()
    contract_only = (
        runtime is None
        and database_path is None
        and capture_marker is None
        and audio_root is None
        and settings is None
    )
    provider = RuntimeProvider(
        settings=config,
        runtime=runtime,
        database_path=database_path,
        capture_marker=capture_marker,
        audio_root=audio_root,
    )

    web_root = static_root or Path(__file__).resolve().parents[4] / "web/dist"

    running_build: BuildInfo | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        nonlocal running_build
        running_build = served_build(web_root)
        logging.getLogger("uvicorn.error").info(
            json.dumps({"event": "build_started", **running_build})
        )
        try:
            yield
        finally:
            await provider.close()

    app = FastAPI(
        title="English-er API",
        version=VERSION,
        description="Local text capture, correction, and review API.",
        lifespan=lifespan,
        responses=BOUNDARY_RESPONSES,
    )
    for error_type in (AppError, RequestValidationError, StarletteHTTPException, Exception):
        app.add_exception_handler(error_type, handle_error)

    async def runtime_dependency() -> ApiRuntime | None:
        return None if contract_only else await provider.get()

    app.dependency_overrides[get_runtime] = runtime_dependency
    for router in (capture_router, transcripts_router, speech_router):
        app.include_router(router)

    @app.get("/version.json", include_in_schema=False)
    async def build_identity() -> JSONResponse:
        return JSONResponse(
            running_build or served_build(web_root), headers={"Cache-Control": "no-store"}
        )

    @app.get("/{asset_path:path}", include_in_schema=False)
    async def serve_web(asset_path: str) -> Response:
        if asset_path == "api" or asset_path.startswith("api/"):
            raise HTTPException(404)
        candidate = (web_root / asset_path).resolve()
        try:
            candidate.relative_to(web_root.resolve())
        except ValueError:
            raise HTTPException(404) from None
        if asset_path and candidate.is_file():
            return FileResponse(candidate)
        index = web_root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(404)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_methods=["GET", "PUT", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(LocalHttpBoundary, settings=config)
    return app


app = create_app(settings=Settings())
