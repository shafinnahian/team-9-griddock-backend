"""FastAPI application entrypoint.

Wires CORS, request-id propagation, the RFC 9457 error handlers, and routers.
Phase 1 mounts only the health router; the analytics + role routers are added
in Phase 3. The warm read-cache is hooked here at startup in Phase 3.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.errors import AppError
from app.routers import health

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach an X-Request-Id to state and every response (logging/debug aid)."""
    request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content=exc.to_problem(request.url.path, _request_id(request)),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(p) for p in err.get("loc", []) if p != "query"),
            "message": err.get("msg", "invalid"),
            "code": err.get("type", "invalid").upper(),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "type": "https://griddock.local/errors/validation-error",
            "title": "Validation Error",
            "status": 422,
            "detail": "One or more query parameters are invalid.",
            "instance": request.url.path,
            "request_id": _request_id(request),
            "errors": errors,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"https://griddock.local/errors/http-{exc.status_code}",
            "title": "HTTP Error",
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": request.url.path,
            "request_id": _request_id(request),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Programming errors: never leak the stack trace to the client.
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://griddock.local/errors/internal",
            "title": "Internal Error",
            "status": 500,
            "detail": "An unexpected error occurred.",
            "instance": request.url.path,
            "request_id": _request_id(request),
        },
    )


app.include_router(health.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": settings.app_version, "docs": "/docs"}
