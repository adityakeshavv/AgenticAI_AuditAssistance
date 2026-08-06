from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KnowledgeGraphNode(Base):
    __tablename__ = "knowledge_graph_node"

    node_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_label: Mapped[str] = mapped_column(String(255), nullable=False)
    node_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeGraphEdge(Base):
    __tablename__ = "knowledge_graph_edge"

    edge_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    source_node_id: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("knowledge_graph_node.node_id"),
        nullable=False,
    )
    target_node_id: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("knowledge_graph_node.node_id"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    edge_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
