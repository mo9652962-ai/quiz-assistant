from __future__ import annotations

from pydantic import BaseModel, Field


class RejectedRow(BaseModel):
    row_number: int = Field(ge=1)
    error: str
    raw: dict[str, object]


class ImportReport(BaseModel):
    source: str
    total: int = 0
    imported: int = 0
    skipped_duplicate: int = 0
    rejected: list[RejectedRow] = Field(default_factory=list)
    dry_run: bool = False

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)
