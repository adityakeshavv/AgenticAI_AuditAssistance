from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import AppUser


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_user_by_id(db: Session, user_id: str) -> AppUser | None:
    return db.get(AppUser, user_id)


def get_user_by_email(db: Session, email: str) -> AppUser | None:
    stmt = select(AppUser).where(AppUser.email == email.strip().lower())
    return db.scalar(stmt)


def get_user_by_google_sub(db: Session, google_sub: str) -> AppUser | None:
    stmt = select(AppUser).where(AppUser.google_sub == google_sub)
    return db.scalar(stmt)


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    auth_provider: str,
    password_salt: str | None = None,
    password_hash: str | None = None,
    google_sub: str | None = None,
) -> AppUser:
    user = AppUser(
        user_id=str(uuid4()),
        full_name=full_name.strip(),
        email=email.strip().lower(),
        password_salt=password_salt,
        password_hash=password_hash,
        auth_provider=auth_provider,
        google_sub=google_sub,
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
        last_login_at=_now(),
    )
    db.add(user)
    db.flush()
    return user


def update_user_login_metadata(
    db: Session,
    user: AppUser,
    *,
    auth_provider: str | None = None,
    google_sub: str | None = None,
) -> AppUser:
    if auth_provider is not None:
        user.auth_provider = auth_provider
    if google_sub is not None:
        user.google_sub = google_sub
    user.last_login_at = _now()
    user.updated_at = _now()
    db.add(user)
    db.flush()
    return user
