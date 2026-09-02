from __future__ import annotations

import asyncio
import json
import urllib.request
from collections.abc import Iterable
from urllib.parse import urlsplit

from quiz_assistant.infrastructure.ai.privacy import redact_provider_text
from quiz_assistant.infrastructure.ai.protocol import (
    Candidate,
    ProviderResult,
    SolveRequest,
    request_hash,
)


class OpenAICompatibleProvider:
    """Minimal opt-in adapter for a Chat Completions-compatible endpoint.

    It is intentionally not constructed by the CLI unless AI is explicitly enabled.
    The response is still validated by the caller before it can affect local data.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        allowed_base_urls: Iterable[str] = (),
    ) -> None:
        normalized = base_url.rstrip("/")
        if urlsplit(normalized).scheme != "https":
            raise ValueError("AI provider must use HTTPS")
        allowlist = {item.rstrip("/") for item in allowed_base_urls}
        if normalized not in allowlist:
            raise ValueError("AI provider base URL is not in the allowlist")
        self.base_url, self.api_key, self.model, self.timeout = (
            normalized,
            api_key,
            model,
            timeout,
        )

    async def solve(self, request: SolveRequest) -> ProviderResult:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return JSON only. Answer only from the supplied option keys. If uncertain, return empty answer_keys.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "stem": redact_provider_text(request.question.stem),
                            "options": [
                                {"key": o.key, "text": redact_provider_text(o.text)}
                                for o in request.question.options
                            ],
                            "context": redact_provider_text(request.context)
                            if request.context
                            else None,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "quiz_answer",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "answer_keys": {"type": "array", "items": {"type": "string"}},
                            "answer_texts": {"type": "array", "items": {"type": "string"}},
                            "reasoning_summary": {"type": "string"},
                            "confidence": {"type": ["number", "null"]},
                            "uncertainties": {"type": "array", "items": {"type": "string"}},
                            "needs_human_confirmation": {"type": "boolean"},
                        },
                        "required": [
                            "answer_keys",
                            "answer_texts",
                            "reasoning_summary",
                            "confidence",
                            "uncertainties",
                            "needs_human_confirmation",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
        }
        data = await asyncio.to_thread(self._request, payload)
        choice = data["choices"][0]["message"]
        parsed = json.loads(choice.get("content") or "{}")
        return ProviderResult(
            candidates=[
                Candidate(key=key, text=text)
                for key, text in zip(parsed.get("answer_keys", []), parsed.get("answer_texts", []))
            ],
            explanation=parsed.get("reasoning_summary"),
            confidence=parsed.get("confidence"),
            raw_response_hash=request_hash(request),
        )

    def _request(self, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310: URL is explicit configuration
            return json.loads(response.read())
