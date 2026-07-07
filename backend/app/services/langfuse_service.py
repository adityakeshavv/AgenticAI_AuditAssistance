from __future__ import annotations

import os
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LangfuseObservation:
    service: "LangfuseService"
    trace_id: str
    name: str
    kind: str
    input_payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    sdk_observation: Any | None = None
    started_at: float = field(default_factory=time.perf_counter)
    ended_at: float | None = None
    output_payload: Any = None
    error: str | None = None

    def finish(
        self,
        *,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if self.ended_at is not None:
            return

        self.ended_at = time.perf_counter()
        self.output_payload = output
        self.error = error
        if metadata:
            self.metadata.update(metadata)

        payload = {
            "name": self.name,
            "kind": self.kind,
            "input": self.input_payload,
            "output": output,
            "metadata": self.metadata,
            "latency_ms": round((self.ended_at - self.started_at) * 1000, 2),
            "error": error,
        }
        self.service._record_observation(self.trace_id, payload)
        self.service._finalize_sdk_observation(self.sdk_observation, output=output, metadata=self.metadata, error=error)


@dataclass
class LangfuseTraceContext:
    service: "LangfuseService"
    trace_id: str
    name: str
    input_payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    sdk_trace: Any | None = None
    started_at: str = field(default_factory=_now_iso)
    ended_at: str | None = None
    observations: list[dict[str, Any]] = field(default_factory=list)

    def begin_span(
        self,
        name: str,
        *,
        input_payload: Any = None,
        metadata: dict[str, Any] | None = None,
        kind: str = "span",
    ) -> LangfuseObservation:
        sdk_observation = self.service._start_sdk_observation(
            self.sdk_trace,
            name=name,
            kind=kind,
            input_payload=input_payload,
            metadata=metadata or {},
        )
        return LangfuseObservation(
            service=self.service,
            trace_id=self.trace_id,
            name=name,
            kind=kind,
            input_payload=input_payload,
            metadata=dict(metadata or {}),
            sdk_observation=sdk_observation,
        )

    def log_generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input_payload: Any = None,
        output_payload: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        observation = self.begin_span(
            name,
            input_payload=input_payload,
            metadata={**(metadata or {}), **({"model": model} if model else {})},
            kind="generation",
        )
        observation.finish(output=output_payload)

    def finalize(self, *, output: Any = None, metadata: dict[str, Any] | None = None) -> None:
        if metadata:
            self.metadata.update(metadata)
        self.ended_at = _now_iso()
        self.service._finalize_sdk_trace(self.sdk_trace, output=output, metadata=self.metadata)

    def as_traceability(self) -> dict[str, Any]:
        return {
            "enabled": self.service.is_enabled(),
            "trace_id": self.trace_id,
            "trace_url": self.service.trace_url(self.trace_id),
            "session_id": self.metadata.get("session_id"),
            "name": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "observations": list(self.service._trace_events.get(self.trace_id, [])),
        }


class LangfuseService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = self._create_client()
        self._trace_events: dict[str, list[dict[str, Any]]] = {}

    def is_enabled(self) -> bool:
        return self._client is not None

    def start_trace(
        self,
        *,
        name: str,
        input_payload: Any = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> LangfuseTraceContext:
        trace_id = uuid.uuid4().hex
        sdk_trace = self._start_sdk_trace(
            name=name,
            trace_id=trace_id,
            input_payload=input_payload,
            metadata=metadata or {},
            user_id=user_id,
            session_id=session_id,
        )
        sdk_trace_id = None
        if sdk_trace is not None:
            sdk_trace_id = getattr(sdk_trace, "id", None) or getattr(sdk_trace, "trace_id", None) or getattr(sdk_trace, "_id", None)
        if sdk_trace_id:
            trace_id = str(sdk_trace_id)
        return LangfuseTraceContext(
            service=self,
            trace_id=trace_id,
            name=name,
            input_payload=input_payload,
            metadata=dict(metadata or {}),
            sdk_trace=sdk_trace,
        )

    def trace_url(self, trace_id: str) -> str | None:
        if self._client is not None:
            getter = getattr(self._client, "get_trace_url", None)
            if callable(getter):
                try:
                    trace_url = getter(trace_id=trace_id)
                    if trace_url:
                        return str(trace_url)
                except Exception as exc:
                    logger.debug("Langfuse trace URL lookup failed: %s", exc)
        template = str(self.settings.langfuse_trace_url_template or "").strip()
        if template:
            return template.replace("{trace_id}", trace_id)
        host = str(self.settings.langfuse_host or "").strip()
        if not host:
            return None
        return host.rstrip("/")

    def _create_client(self) -> Any | None:
        if not self.settings.langfuse_enabled:
            return None
        if not (self.settings.langfuse_public_key and self.settings.langfuse_secret_key):
            return None

        try:
            from langfuse import get_client  # type: ignore
        except Exception:
            logger.warning("langfuse package is not installed; Langfuse tracing will stay disabled.")
            return None

        try:
            os.environ.setdefault("LANGFUSE_PUBLIC_KEY", self.settings.langfuse_public_key)
            os.environ.setdefault("LANGFUSE_SECRET_KEY", self.settings.langfuse_secret_key)
            if self.settings.langfuse_host:
                os.environ.setdefault("LANGFUSE_BASE_URL", self.settings.langfuse_host)
                os.environ.setdefault("LANGFUSE_HOST", self.settings.langfuse_host)
            return get_client()
        except Exception as exc:
            logger.warning("Failed to initialize Langfuse client: %s", exc)
            return None

    def _start_sdk_trace(
        self,
        *,
        name: str,
        trace_id: str,
        input_payload: Any,
        metadata: dict[str, Any],
        user_id: str | None,
        session_id: str | None,
    ) -> Any | None:
        if self._client is None:
            return None

        try:
            trace_kwargs: dict[str, Any] = {
                "name": name,
                "input": input_payload,
                "metadata": metadata,
            }
            if user_id:
                trace_kwargs["user_id"] = user_id
            if session_id:
                trace_kwargs["session_id"] = session_id
            if hasattr(self._client, "trace"):
                return self._client.trace(**trace_kwargs)
        except Exception as exc:
            logger.warning("Langfuse trace creation failed: %s", exc)
        return None

    def _start_sdk_observation(
        self,
        sdk_trace: Any | None,
        *,
        name: str,
        kind: str,
        input_payload: Any,
        metadata: dict[str, Any],
    ) -> Any | None:
        if sdk_trace is None:
            return None

        try:
            starter = getattr(sdk_trace, kind, None) or getattr(sdk_trace, "span", None)
            if starter is None:
                return None
            return starter(name=name, input=input_payload, metadata=metadata)
        except Exception as exc:
            logger.warning("Langfuse observation creation failed: %s", exc)
            return None

    def _finalize_sdk_trace(self, sdk_trace: Any | None, *, output: Any, metadata: dict[str, Any]) -> None:
        if sdk_trace is None:
            return
        self._safe_finalize(sdk_trace, output=output, metadata=metadata)

    def _finalize_sdk_observation(
        self,
        sdk_observation: Any | None,
        *,
        output: Any,
        metadata: dict[str, Any],
        error: str | None,
    ) -> None:
        if sdk_observation is None:
            return
        self._safe_finalize(sdk_observation, output=output, metadata=metadata, error=error)

    def _safe_finalize(self, sdk_object: Any, **kwargs: Any) -> None:
        for method_name in ("end", "finish", "update"):
            method = getattr(sdk_object, method_name, None)
            if method is None:
                continue
            try:
                method(**kwargs)
                return
            except TypeError:
                try:
                    method(kwargs.get("output"))
                    return
                except Exception:
                    continue
            except Exception:
                continue

    def _record_observation(self, trace_id: str, payload: dict[str, Any]) -> None:
        # This keeps a local breadcrumb trail even when the SDK is disabled.
        self._trace_events.setdefault(trace_id, []).append(payload)
        logger.debug("Langfuse observation trace_id=%s payload=%s", trace_id, payload)
