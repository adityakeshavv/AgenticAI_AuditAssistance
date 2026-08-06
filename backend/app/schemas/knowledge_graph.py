from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeGraphNodeRecord(BaseModel):
    node_id: str
    entity_type: str
    entity_id: str
    display_label: str
    node_kind: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeGraphEdgeRecord(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    strength: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeGraphSummary(BaseModel):
    entity_type: str
    entity_id: str
    root_node_id: str | None = None
    node_count: int = 0
    edge_count: int = 0
    relationship_breakdown: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeGraphResponse(BaseModel):
    success: bool = True
    entity_type: str
    entity_id: str
    root_node: KnowledgeGraphNodeRecord | None = None
    nodes: list[KnowledgeGraphNodeRecord] = Field(default_factory=list)
    edges: list[KnowledgeGraphEdgeRecord] = Field(default_factory=list)
    summary: KnowledgeGraphSummary | dict[str, Any] = Field(default_factory=dict)
    message: str | None = None

    model_config = ConfigDict(from_attributes=True)
