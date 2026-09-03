"""Small in-memory audit ledger for individual tool execution attempts."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type ToolFailureKind = Literal["timeout", "transient", "permanent"]
type ToolAttemptOutcome = Literal["succeeded", "retrying", "failed", "denied"]


class ToolAttemptRecord(BaseModel):
    """One immutable record describing a single tool execution attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = "untracked"
    tool_call_id: str
    tool_name: str
    attempt: int = Field(ge=0)
    started_at: datetime
    duration_ms: float = Field(ge=0)
    outcome: ToolAttemptOutcome
    failure_kind: ToolFailureKind | None = None
    error_type: str | None = None
    error_message: str | None = None


class ToolAuditLog:
    """Append and query tool attempt records for the current process."""

    def __init__(self) -> None:
        self._records: list[ToolAttemptRecord] = []

    def record(self, record: ToolAttemptRecord) -> None:
        """Append one already validated attempt record."""

        self._records.append(record)

    def record_denied(
        self,
        *,
        run_id: str = "untracked",
        tool_call_id: str,
        tool_name: str,
        reason: str,
    ) -> None:
        """Record that approval policy prevented execution before attempt one."""

        self.record(
            ToolAttemptRecord(
                run_id=run_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                attempt=0,
                started_at=datetime.now(UTC),
                duration_ms=0,
                outcome="denied",
                failure_kind="permanent",
                error_type="ActionDenied",
                error_message=reason,
            )
        )

    def list_records(
        self,
        *,
        run_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> tuple[ToolAttemptRecord, ...]:
        """Return an immutable snapshot, optionally limited to one tool call."""

        return tuple(
            record
            for record in self._records
            if (run_id is None or record.run_id == run_id)
            and (tool_call_id is None or record.tool_call_id == tool_call_id)
        )
