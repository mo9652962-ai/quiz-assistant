from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher

from quiz_assistant.domain.models import MatchCandidate, MatchResult
from quiz_assistant.schemas.question import Question

NORMALIZER_VERSION = "v1"
_INVISIBLE = re.compile(r"[\u0000-\u001f\u007f\u00ad\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_HTML = re.compile(r"<[^>]+>")
_OPTION_PREFIX = re.compile(r"^\s*[A-Za-zＡ-Ｚａ-ｚ][\s.)、:：-]+")


def normalize_text(value: str, *, strip_option_prefix: bool = False) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(value))
    value = _HTML.sub(" ", value)
    value = _INVISIBLE.sub("", value)
    value = value.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    value = value.replace("。", ".").replace("，", ",").replace("：", ":").replace("；", ";")
    value = re.sub(r"\s+", " ", value).strip().casefold()
    if strip_option_prefix:
        value = _OPTION_PREFIX.sub("", value, count=1)
    return value


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[\w\u4e00-\u9fff]+", value) if token}


def _score(query: str, candidate: str) -> float:
    if query == candidate:
        return 0.98
    q_tokens, c_tokens = _tokens(query), _tokens(candidate)
    overlap = len(q_tokens & c_tokens) / max(len(q_tokens | c_tokens), 1)
    sequence = SequenceMatcher(None, query, candidate).ratio()
    return round(min(0.94, 0.55 * sequence + 0.45 * overlap), 4)


def match_questions(
    questions: list[Question], stem: str, options: list[str] | None = None, top_k: int = 5
) -> MatchResult:
    query = normalize_text(stem)
    option_query = [normalize_text(item, strip_option_prefix=True) for item in options or []]
    candidates: list[MatchCandidate] = []
    for question in questions:
        candidate_stem = normalize_text(question.stem)
        if query == question.id.casefold():
            score, method, evidence = 1.0, "id_exact", ("question id exact match",)
        elif stem == question.stem:
            score, method, evidence = 1.0, "exact", ("raw stem exact match",)
        else:
            score, method, evidence = (
                _score(query, candidate_stem),
                "token_overlap",
                ("normalized text similarity",),
            )
            if score == 0.98:
                method, evidence = "normalized_exact", ("normalized stem uniquely matches",)
            if option_query and score >= 0.90:
                stored = [
                    normalize_text(item.text, strip_option_prefix=True) for item in question.options
                ]
                if option_query == stored:
                    score = min(0.99, score + 0.04)
                    method = "normalized_exact_with_options"
                    evidence = ("normalized stem and option order match",)
        if score >= 0.55:
            candidates.append(MatchCandidate(question, score, method, evidence))
    candidates.sort(key=lambda item: (-item.score, item.question.id))
    candidates = candidates[: max(top_k, 1)]
    if not candidates:
        return MatchResult("no_match", None, [], [], "none", 0.0, ["no candidate reached 0.55"], [])
    best = candidates[0]
    second_score = candidates[1].score if len(candidates) > 1 else -1
    unique = best.score - second_score >= 0.05
    if best.score >= 0.95 and unique:
        status = "high_confidence"
    elif best.score >= 0.80 and unique:
        status = "needs_confirmation"
    else:
        status = "needs_confirmation" if best.score >= 0.55 else "no_match"
    answers = [option for option in best.question.options if option.correct]
    return MatchResult(
        status=status,
        question_id=best.question.id,
        answer_keys=[option.key for option in answers],
        answer_texts=[option.text for option in answers],
        method=best.method,
        score=best.score,
        evidence=list(best.evidence),
        alternatives=candidates[1:],
    )
