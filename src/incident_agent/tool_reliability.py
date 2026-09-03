"""Timeout, selective retry, and failure classification for tool handlers."""

import asyncio
from datetime import UTC, datetime
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from incident_agent.tool_audit import (
    ToolAttemptRecord,
    ToolAuditLog,
    ToolFailureKind,
)
from incident_agent.tool_catalog import ToolHandler


class TransientToolError(RuntimeError):
    """Signal a temporary dependency problem that may succeed on retry."""


class ToolExecutionFailed(RuntimeError):
    """Describe a tool call that exhausted its permitted attempts."""

    def __init__(
        self,
        *,
        tool_name: str,
        failure_kind: ToolFailureKind,
        attempts: int,
        cause: Exception,
    ) -> None:
        super().__init__(
            f"Tool {tool_name!r} failed after {attempts} attempt(s): {cause}"
        )
        self.tool_name = tool_name
        self.failure_kind = failure_kind
        self.attempts = attempts
        self.cause = cause


class ToolReliabilityPolicy(BaseModel):
    """Validated limits shared by one tool runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout_seconds: float = Field(default=5.0, gt=0)
    max_attempts: int = Field(default=2, ge=1)
    retry_delay_seconds: float = Field(default=0.05, ge=0)


def classify_tool_error(error: Exception) -> ToolFailureKind:
    """Classify one failure without retrying unknown or business errors."""

    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, (TransientToolError, ConnectionError)):
        return "transient"
    return "permanent"


def should_retry(
    failure_kind: ToolFailureKind,
    *,
    retry_safe: bool,
    attempt: int,
    policy: ToolReliabilityPolicy,
) -> bool:
    """Retry only safe temporary failures while an attempt remains."""

    return (
        retry_safe
        and failure_kind in {"timeout", "transient"}
        and attempt < policy.max_attempts
    )


async def run_with_reliability(
    *,
    run_id: str,
    tool_call_id: str,
    tool_name: str,
    handler: ToolHandler,
    arguments: dict[str, object],
    retry_safe: bool,
    policy: ToolReliabilityPolicy,
    audit: ToolAuditLog,
) -> object:
    """Run one handler under timeout and retry rules, auditing every attempt."""

    for attempt in range(1, policy.max_attempts + 1):
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        try:
            async with asyncio.timeout(policy.timeout_seconds):
                result = await handler(arguments)
        except Exception as error:
            reported_error = error
            if isinstance(error, TimeoutError) and not str(error):
                reported_error = TimeoutError(
                    f"exceeded {policy.timeout_seconds:g} second timeout"
                )
            duration_ms = (perf_counter() - started_clock) * 1000
            failure_kind = classify_tool_error(reported_error)
            retrying = should_retry(
                failure_kind,
                retry_safe=retry_safe,
                attempt=attempt,
                policy=policy,
            )
            audit.record(
                ToolAttemptRecord(
                    run_id=run_id,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    attempt=attempt,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    outcome="retrying" if retrying else "failed",
                    failure_kind=failure_kind,
                    error_type=type(reported_error).__name__,
                    error_message=str(reported_error),
                )
            )
            if retrying:
                await asyncio.sleep(policy.retry_delay_seconds)
                continue
            raise ToolExecutionFailed(
                tool_name=tool_name,
                failure_kind=failure_kind,
                attempts=attempt,
                cause=reported_error,
            ) from error
        else:
            audit.record(
                ToolAttemptRecord(
                    run_id=run_id,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    attempt=attempt,
                    started_at=started_at,
                    duration_ms=(perf_counter() - started_clock) * 1000,
                    outcome="succeeded",
                )
            )
            return result

    raise AssertionError("The reliability loop must return or raise")
