from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.responses import DetailResponse
from app.dependencies.database import get_db


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=DetailResponse[dict[str, str]])
def health_check() -> DetailResponse[dict[str, str]]:
    return DetailResponse(data={"status": "ok"})


@router.get("/db", response_model=DetailResponse[dict[str, str]])
def database_health_check(db: Session = Depends(get_db)) -> DetailResponse[dict[str, str]]:
    db.execute(text("SELECT 1"))
    return DetailResponse(data={"status": "ok"})
