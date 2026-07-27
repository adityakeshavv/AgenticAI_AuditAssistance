from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.services.auth_service import AuthService
from app.services.realtime_service import realtime_hub


router = APIRouter(prefix="/ws", tags=["realtime"])


@router.websocket("/updates")
async def realtime_updates(
    websocket: WebSocket,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        current_user = AuthService(db).get_current_user(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await realtime_hub.ensure_started()
    await realtime_hub.attach(
        websocket,
        user_id=current_user.user_id,
        full_name=current_user.full_name or current_user.email,
        email=current_user.email,
        role=current_user.role,
    )

    try:
        await websocket.send_json(
            {
                "type": "realtime_connected",
                "user_id": current_user.user_id,
                "role": current_user.role,
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        realtime_hub.detach(websocket)
