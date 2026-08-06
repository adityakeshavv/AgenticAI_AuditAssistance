from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.database import Base, engine
from app.core.config import get_settings
from app.core.exceptions import safe_detail
from app import models as _models  # noqa: F401
from app.routers import admin, audit, auth, chat, connections, graph, health, realtime, workspaces, workspace_collaboration
from app.services.monitoring_service import monitoring_supervisor
from app.services.realtime_service import realtime_hub


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
app.include_router(workspace_collaboration.router)
app.include_router(admin.router)
app.include_router(audit.router)
app.include_router(graph.router)
app.include_router(chat.router)
app.include_router(realtime.router)


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
async def create_missing_tables() -> None:
    Base.metadata.create_all(bind=engine)
    await realtime_hub.ensure_started()
    await monitoring_supervisor.ensure_started()


@app.on_event("shutdown")
async def shutdown_realtime_hub() -> None:
    await monitoring_supervisor.shutdown()
    await realtime_hub.shutdown()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
