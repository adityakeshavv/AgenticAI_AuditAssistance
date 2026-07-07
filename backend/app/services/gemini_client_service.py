from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class GeminiClientService:
    """Small Gemini SDK adapter with graceful fallback between SDK variants.

    The repo currently does not ship the Gemini SDK. This adapter keeps the
    integration boundary in one place so the app can switch over once the
    dependency is installed, without rewriting callers.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        return bool(self.settings.google_api_key or self.settings.google_cloud_project_id)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
    ) -> str:
        client = self._create_client()
        if client is None:
            raise RuntimeError("Gemini SDK is not installed or not available in the current environment.")

        model_name = model or self.settings.gemini_model
        response_text = self._call_generate_content(client, model_name=model_name, system_prompt=system_prompt, user_prompt=user_prompt)
        if not response_text:
            raise ValueError("Gemini returned an empty response.")
        return response_text

    def _create_client(self) -> Any | None:
        api_key = self.settings.google_api_key
        project_id = self.settings.google_cloud_project_id
        if not api_key and not project_id:
            return None

        try:
            from google import genai as google_genai  # type: ignore

            if api_key:
                return google_genai.Client(api_key=api_key)
            return google_genai.Client(
                vertexai=True,
                project=project_id,
                location=self.settings.google_cloud_location,
            )
        except Exception:
            pass

        try:
            import google.generativeai as google_generativeai  # type: ignore

            if not api_key:
                return None
            google_generativeai.configure(api_key=api_key)
            return google_generativeai
        except Exception:
            pass

        logger.warning("Neither google.genai nor google.generativeai is available.")
        return None

    def _call_generate_content(
        self,
        client: Any,
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        try:
            if hasattr(client, "models"):
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        {"role": "user", "parts": [{"text": system_prompt + "\n\n" + user_prompt}]},
                    ],
                )
                text = getattr(response, "text", None)
                if text:
                    return str(text)
                candidates = getattr(response, "candidates", None) or []
                for candidate in candidates:
                    content = getattr(candidate, "content", None)
                    parts = getattr(content, "parts", None) or []
                    for part in parts:
                        part_text = getattr(part, "text", None)
                        if part_text:
                            return str(part_text)
                return ""

            if hasattr(client, "GenerativeModel"):
                model = client.GenerativeModel(model_name)
                response = model.generate_content(system_prompt + "\n\n" + user_prompt)
                text = getattr(response, "text", None)
                if text:
                    return str(text)
                return ""
        except Exception as exc:
            raise RuntimeError(f"Gemini generation failed: {exc}") from exc

        raise RuntimeError("Unsupported Gemini client implementation.")

    @staticmethod
    def parse_json(response_text: str) -> dict[str, Any]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Gemini response must be a JSON object.")
        return parsed
