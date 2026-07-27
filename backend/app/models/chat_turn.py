from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatTurn(Base):
    __tablename__ = "chat_turn"

    turn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_session.session_id", ondelete="CASCADE"), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="audit", index=True)
    is_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
