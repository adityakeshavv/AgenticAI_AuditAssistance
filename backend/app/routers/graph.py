from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.knowledge_graph import KnowledgeGraphResponse
from app.services.knowledge_graph_service import KnowledgeGraphService


router = APIRouter(prefix="/graph", tags=["knowledge-graph"])


@router.get("/entity/{entity_type}/{entity_id}", response_model=KnowledgeGraphResponse)
def get_entity_graph(
    entity_type: str,
    entity_id: str,
    refresh: bool = Query(default=True),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> KnowledgeGraphResponse:
    service = KnowledgeGraphService(db)
    try:
        graph = (
            service.build_entity_graph(entity_type, entity_id, limit=limit)
            if refresh
            else service.view_entity_graph(entity_type, entity_id)
        )
        db.commit()
        return graph
    except LookupError as exc:
        db.rollback()
        return KnowledgeGraphResponse(
            success=False,
            entity_type=entity_type,
            entity_id=entity_id,
            message=str(exc),
        )
    except ValueError as exc:
        db.rollback()
        return KnowledgeGraphResponse(
            success=False,
            entity_type=entity_type,
            entity_id=entity_id,
            message=str(exc),
        )
