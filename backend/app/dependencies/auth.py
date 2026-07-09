from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import audit_workspace_crud, database_connection_crud
from app.dependencies.database import get_db
from app.schemas.auth import AuthUser
from app.services.auth_service import AuthService


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token.")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token.")

    return AuthService(db).get_current_user(token)


def require_role(*allowed_roles: str):
    normalized_roles = {role.strip().lower() for role in allowed_roles if role.strip()}

    def dependency(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if normalized_roles and current_user.role.strip().lower() not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return dependency


def require_admin(current_user: AuthUser = Depends(require_role("admin"))) -> AuthUser:
    return current_user


def require_workspace_access(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    if current_user.role.strip().lower() == "admin":
        return current_user
    workspace = audit_workspace_crud.get_workspace_by_id(db, workspace_id)
    if workspace is None or workspace.owner_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this workspace.",
        )
    return current_user


def require_connection_access(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    if current_user.role.strip().lower() == "admin":
        return current_user
    connection = database_connection_crud.get_connection_by_id(db, connection_id)
    if connection is None or connection.owner_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this database source.",
        )
    return current_user
