from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.auth import AuthResponse, AuthUser, LoginRequest, SignupRequest
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> dict:
    return AuthService(db).signup(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    return AuthService(db).login(payload)


@router.get("/me", response_model=AuthUser)
def me(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    return current_user


@router.get("/google/start")
def google_start(
    redirect_uri: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    auth_url = auth_service.create_google_login_url(redirect_uri=redirect_uri)
    return RedirectResponse(auth_url)


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    redirect_url = AuthService(db).handle_google_callback(code=code, state=state)
    return RedirectResponse(redirect_url)

