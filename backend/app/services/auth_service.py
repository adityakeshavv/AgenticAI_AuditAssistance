from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_signed_token, hash_password, verify_password, verify_signed_token
from app.crud import user_crud
from app.models.user import AppUser
from app.schemas.auth import AuthResponse, AuthUser, LoginRequest, SignupRequest
from app.services.governance_audit_service import GovernanceAuditService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def signup(self, payload: SignupRequest) -> dict[str, Any]:
        email = payload.email.lower()
        existing = user_crud.get_user_by_email(self.db, email)
        if existing:
            GovernanceAuditService(self.db).record_event(
                actor_name=email,
                action_type="signup_failed",
                entity_type="user",
                severity="warning",
                summary=f"Signup attempt blocked because the email '{email}' already exists.",
            )
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

        salt_hex, hash_hex = hash_password(payload.password)
        user = user_crud.create_user(
            self.db,
            full_name=payload.full_name,
            email=email,
            auth_provider="LOCAL",
            password_salt=salt_hex,
            password_hash=hash_hex,
        )
        self.db.commit()
        self.db.refresh(user)
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user.user_id,
            actor_name=user.full_name or user.email,
            action_type="signup_completed",
            entity_type="user",
            entity_id=user.user_id,
            severity="info",
            summary=f"User '{user.full_name or user.email}' created a local account.",
            after_state={"email": user.email, "auth_provider": user.auth_provider},
        )
        self.db.commit()
        token = self._create_access_token(user)
        return self._build_response(user, token)

    def login(self, payload: LoginRequest) -> dict[str, Any]:
        email = payload.email.lower()
        user = user_crud.get_user_by_email(self.db, email)
        if not user or not user.password_hash or not user.password_salt:
            GovernanceAuditService(self.db).record_event(
                actor_name=email,
                action_type="login_failed",
                entity_type="user",
                severity="warning",
                summary=f"Login failed for '{email}'.",
                after_state={"email": email, "reason": "invalid_credentials"},
            )
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        if not user.is_active:
            GovernanceAuditService(self.db).record_event(
                actor_user_id=user.user_id,
                actor_name=user.full_name or user.email,
                action_type="login_failed",
                entity_type="user",
                entity_id=user.user_id,
                severity="warning",
                summary=f"Login blocked because '{user.email}' is inactive.",
                after_state={"email": user.email, "reason": "inactive_account"},
            )
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.")
        if not verify_password(payload.password, salt_hex=user.password_salt, password_hash_hex=user.password_hash):
            GovernanceAuditService(self.db).record_event(
                actor_user_id=user.user_id,
                actor_name=user.full_name or user.email,
                action_type="login_failed",
                entity_type="user",
                entity_id=user.user_id,
                severity="warning",
                summary=f"Login failed for '{user.email}'.",
                after_state={"email": user.email, "reason": "invalid_credentials"},
            )
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        user_crud.update_user_login_metadata(self.db, user, auth_provider="LOCAL")
        self.db.commit()
        self.db.refresh(user)
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user.user_id,
            actor_name=user.full_name or user.email,
            action_type="login_completed",
            entity_type="user",
            entity_id=user.user_id,
            severity="info",
            summary=f"User '{user.email}' signed in successfully.",
            after_state={"email": user.email, "auth_provider": "LOCAL"},
        )
        self.db.commit()
        token = self._create_access_token(user)
        return self._build_response(user, token)

    def get_current_user(self, token: str) -> AuthUser:
        payload = verify_signed_token(token, secret=self.settings.auth_token_secret, expected_type="auth_session")
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")
        user_id = payload.get("sub")
        if not isinstance(user_id, str):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")
        user = user_crud.get_user_by_id(self.db, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive or missing.")
        return self._serialize_user(user)

    def create_google_login_url(self, redirect_uri: str | None = None) -> str:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google sign-in is not configured.")

        target_redirect = self._normalize_frontend_redirect(redirect_uri)
        state = create_signed_token(
            {
                "type": "google_oauth_state",
                "redirect_uri": target_redirect,
                "exp": self._now_ts() + 600,
            },
            secret=self.settings.auth_token_secret,
        )
        query = urllib.parse.urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "offline",
                "prompt": "select_account",
                "state": state,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    def handle_google_callback(self, code: str, state: str) -> str:
        state_payload = verify_signed_token(state, secret=self.settings.auth_token_secret, expected_type="google_oauth_state")
        if not state_payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google sign-in state.")

        token_payload = self._exchange_google_code(code)
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google sign-in did not return an access token.")

        profile = self._fetch_google_profile(access_token)
        email = str(profile.get("email") or "").lower()
        google_sub = str(profile.get("sub") or "")
        full_name = str(profile.get("name") or profile.get("email") or "Google User")
        if not email or not google_sub:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google profile is missing email or subject.")

        user = user_crud.get_user_by_google_sub(self.db, google_sub)
        if not user:
            user = user_crud.get_user_by_email(self.db, email)
        if user:
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.")
            user.full_name = full_name
            user.email = email
            user.google_sub = google_sub
            provider = "GOOGLE" if not user.password_hash else user.auth_provider
            user_crud.update_user_login_metadata(self.db, user, auth_provider=provider, google_sub=google_sub)
        else:
            user = user_crud.create_user(
                self.db,
                full_name=full_name,
                email=email,
                auth_provider="GOOGLE",
                google_sub=google_sub,
            )

        self.db.commit()
        self.db.refresh(user)
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user.user_id,
            actor_name=user.full_name or user.email,
            action_type="google_login_completed",
            entity_type="user",
            entity_id=user.user_id,
            severity="info",
            summary=f"User '{user.email}' signed in with Google.",
            after_state={"email": user.email, "auth_provider": user.auth_provider},
        )
        self.db.commit()
        token = self._create_access_token(user)
        redirect_uri = self._normalize_frontend_redirect(str(state_payload.get("redirect_uri") or ""))
        return self._build_frontend_redirect(redirect_uri, token, user)

    def _serialize_user(self, user: AppUser) -> AuthUser:
        return AuthUser(
            user_id=user.user_id,
            full_name=user.full_name,
            email=user.email,
            auth_provider=user.auth_provider,
            role=self._resolve_role(user.email),
            is_active=user.is_active,
            last_login_at=user.last_login_at,
        )

    def serialize_user(self, user: AppUser) -> AuthUser:
        return self._serialize_user(user)

    def _build_response(self, user: AppUser, token: str) -> dict[str, Any]:
        return AuthResponse(access_token=token, user=self._serialize_user(user)).model_dump()

    def _create_access_token(self, user: AppUser) -> str:
        return create_signed_token(
            {
                "type": "auth_session",
                "sub": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "role": self._resolve_role(user.email),
                "exp": self._now_ts() + (self.settings.auth_token_expiry_minutes * 60),
            },
            secret=self.settings.auth_token_secret,
        )

    def _build_frontend_redirect(self, redirect_uri: str, token: str, user: AppUser) -> str:
        params = urllib.parse.urlencode(
            {
                "auth": "success",
                "token": token,
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
            }
        )
        separator = "&" if "?" in redirect_uri else "?"
        return f"{redirect_uri}{separator}{params}"

    def _exchange_google_code(self, code: str) -> dict[str, Any]:
        body = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "redirect_uri": self.settings.google_redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else exc.reason
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Google token exchange failed: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network dependent
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to reach Google sign-in endpoints.") from exc

    def _fetch_google_profile(self, access_token: str) -> dict[str, Any]:
        request = urllib.request.Request(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else exc.reason
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Google profile lookup failed: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network dependent
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to retrieve Google profile information.") from exc

    @staticmethod
    def _now_ts() -> int:
        return int(datetime.now(timezone.utc).timestamp())

    def _normalize_frontend_redirect(self, redirect_uri: str | None) -> str:
        configured = self.settings.frontend_auth_redirect_uri
        candidate = redirect_uri or configured
        configured_parsed = urllib.parse.urlparse(configured)
        candidate_parsed = urllib.parse.urlparse(candidate)
        allowed_origin = f"{configured_parsed.scheme}://{configured_parsed.netloc}"
        candidate_origin = f"{candidate_parsed.scheme}://{candidate_parsed.netloc}"
        if candidate_origin == allowed_origin:
            return candidate
        return configured

    def _resolve_role(self, email: str) -> str:
        allowlist = {
            value.strip().lower()
            for value in self.settings.admin_email_allowlist.split(",")
            if value.strip()
        }
        return "admin" if email.strip().lower() in allowlist else "user"
