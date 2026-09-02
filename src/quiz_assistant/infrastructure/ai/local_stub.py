from __future__ import annotations

from quiz_assistant.infrastructure.ai.protocol import ProviderResult, SolveRequest, request_hash


class LocalStubProvider:
    """Safe default provider: returns no answer and performs no network operation."""

    async def solve(self, request: SolveRequest) -> ProviderResult:
        return ProviderResult(
            explanation="AI is disabled; no network request was made.",
            raw_response_hash=request_hash(request),
        )
