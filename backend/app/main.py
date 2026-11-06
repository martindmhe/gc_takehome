from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.db.init_db import init_db
from app.db.session import engine
from app.services.errors import (
    ConflictError,
    FileTooLargeError,
    ForbiddenError,
    InvalidFileError,
    InvalidRequestError,
    NotFoundError,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db(engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lead Management API",
        lifespan=lifespan,
    )
    app.include_router(api_router)

    @app.exception_handler(NotFoundError)
    def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_404_NOT_FOUND)

    @app.exception_handler(ForbiddenError)
    def _forbidden(_: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_403_FORBIDDEN)

    @app.exception_handler(ConflictError)
    def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_409_CONFLICT)

    @app.exception_handler(InvalidRequestError)
    def _invalid_request(_: Request, exc: InvalidRequestError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(InvalidFileError)
    def _invalid_file(_: Request, exc: InvalidFileError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    @app.exception_handler(FileTooLargeError)
    def _too_large(_: Request, exc: FileTooLargeError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_413_CONTENT_TOO_LARGE)

    return app


app = create_app()
