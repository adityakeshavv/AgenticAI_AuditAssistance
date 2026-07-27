from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from queue import Queue
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class RealtimeHub:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._connection_meta: dict[WebSocket, dict[str, Any]] = {}
        self._queue: Queue[dict[str, Any]] = Queue()
        self._dispatch_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._running = False
        self._stop_sentinel: dict[str, Any] = {"type": "__realtime_stop__"}

    async def ensure_started(self) -> None:
        async with self._lock:
            if self._dispatch_task and not self._dispatch_task.done():
                return
            self._running = True
            self._dispatch_task = asyncio.create_task(self._dispatch_loop())

    async def shutdown(self) -> None:
        async with self._lock:
            self._running = False
            self._queue.put(self._stop_sentinel)
            task = self._dispatch_task
            self._dispatch_task = None
        if task and not task.done():
            try:
                await asyncio.wait_for(task, timeout=2)
            except Exception:
                task.cancel()
        self._connections.clear()
        self._connection_meta.clear()

    def publish(self, payload: dict[str, Any]) -> None:
        self._queue.put(payload)

    async def attach(self, websocket: WebSocket, *, user_id: str, full_name: str, email: str, role: str) -> None:
        self._connections.add(websocket)
        self._connection_meta[websocket] = {
            "user_id": user_id,
            "full_name": full_name,
            "email": email,
            "role": role,
            "connected_at": self._now_iso(),
            "last_seen_at": self._now_iso(),
        }

    def detach(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        self._connection_meta.pop(websocket, None)

    def list_active_users(self) -> list[dict[str, Any]]:
        active: dict[str, dict[str, Any]] = {}
        for meta in self._connection_meta.values():
            user_id = str(meta.get("user_id") or "")
            if not user_id:
                continue
            current = active.get(user_id)
            snapshot = {
                "user_id": user_id,
                "full_name": meta.get("full_name") or user_id,
                "email": meta.get("email") or "",
                "role": meta.get("role") or "user",
                "connected_at": meta.get("connected_at"),
                "last_seen_at": meta.get("last_seen_at"),
                "session_count": 1,
            }
            if current:
                snapshot["session_count"] = int(current.get("session_count", 1)) + 1
                if str(snapshot.get("connected_at")) < str(current.get("connected_at")):
                    snapshot["connected_at"] = current.get("connected_at")
                if str(snapshot.get("last_seen_at")) > str(current.get("last_seen_at")):
                    snapshot["last_seen_at"] = meta.get("last_seen_at")
            active[user_id] = snapshot
        return sorted(active.values(), key=lambda item: (item.get("full_name") or item.get("user_id") or "").lower())

    async def _dispatch_loop(self) -> None:
        while self._running:
            payload = await asyncio.to_thread(self._queue.get)
            if payload == self._stop_sentinel:
                break
            await self._broadcast(payload)

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        if not self._connections:
            return
        stale: list[WebSocket] = []
        for connection in list(self._connections):
            try:
                await connection.send_json(payload)
            except Exception:  # pragma: no cover - connection lifecycle is runtime dependent
                stale.append(connection)
        for connection in stale:
            self._connections.discard(connection)
            self._connection_meta.pop(connection, None)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


realtime_hub = RealtimeHub()


def publish_realtime_event(payload: dict[str, Any]) -> None:
    try:
        realtime_hub.publish(payload)
    except Exception:  # pragma: no cover - realtime should never block primary flows
        logger.debug("Realtime event could not be queued.", exc_info=True)
