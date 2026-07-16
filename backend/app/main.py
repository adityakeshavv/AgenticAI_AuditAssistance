from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.database import Base, engine
from app.core.config import get_settings
from app.core.exceptions import safe_detail
from app import models as _models  # noqa: F401
from app.routers import admin, audit, auth, chat, connections, health, workspaces


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(workspaces.router)
app.include_router(admin.router)
app.include_router(audit.router)
app.include_router(chat.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": safe_detail(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    messages = []
    for error in exc.errors():
        loc = error.get("loc", [])
        if isinstance(loc, (list, tuple)):
            location = ".".join(str(part) for part in loc if part != "body")
        else:
            location = str(loc)
        message = safe_detail(error.get("msg"), "Invalid input.")
        messages.append(f"{location}: {message}" if location else message)
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages) or "Invalid input."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": safe_detail(exc, "An unexpected error occurred. Please try again.")},
    )


@app.on_event("startup")
def create_missing_tables() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
