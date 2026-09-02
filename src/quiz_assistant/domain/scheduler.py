from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class ScheduleState:
    due_at: datetime
    interval_days: float
    ease: float
    repetitions: int
    lapses: int


def schedule_review(
    previous: ScheduleState | None, quality: int, now: datetime | None = None
) -> ScheduleState:
    """Small SM-2-inspired scheduler; review history remains the source of truth."""
    quality = max(0, min(5, int(quality)))
    now = now or datetime.now(UTC)
    if previous is None:
        ease, repetitions, lapses, interval = 2.5, 0, 0, 0.0
    else:
        ease, repetitions, lapses, interval = (
            previous.ease,
            previous.repetitions,
            previous.lapses,
            previous.interval_days,
        )
    if quality < 3:
        repetitions, lapses, interval = 0, lapses + 1, 0.0
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1.0
        elif repetitions == 2:
            interval = 6.0
        else:
            interval = max(1.0, interval * ease)
        ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    due = now + timedelta(days=interval)
    return ScheduleState(due, round(interval, 3), round(ease, 3), repetitions, lapses)
