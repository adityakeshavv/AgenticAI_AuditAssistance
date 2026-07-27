from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    connection_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    session_title: Mapped[str] = mapped_column(String(200), nullable=False, default="New chat")
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
