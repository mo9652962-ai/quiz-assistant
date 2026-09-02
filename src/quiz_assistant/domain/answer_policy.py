from __future__ import annotations

from dataclasses import dataclass

from quiz_assistant.domain.models import MatchResult


@dataclass(frozen=True)
class AnswerDecision:
    label: str
    can_show_answer: bool
    requires_confirmation: bool


def decide(result: MatchResult) -> AnswerDecision:
    if result.status == "high_confidence" and result.score >= 0.95:
        return AnswerDecision("high_confidence", True, False)
    if result.status == "needs_confirmation" and result.score >= 0.80:
        return AnswerDecision("needs_confirmation", True, True)
    return AnswerDecision("no_match", False, True)
