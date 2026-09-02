"""Bridge model tool calls to approved, reliable Python tool execution."""

import json

from langchain_core.messages import ToolCall, ToolMessage
from pydantic import BaseModel, ConfigDict

from incident_agent.approval_gate import (
    ActionDenied,
    ApprovalProof,
    approval_proof_covers,
    tool_needs_human,
)
from incident_agent.tool_audit import ToolAuditLog, ToolFailureKind
from incident_agent.tool_catalog import (
    ToolCatalog,
    UnknownToolError,
    build_default_tool_catalog,
)
from incident_agent.tool_reliability import (
    ToolExecutionFailed,
    ToolReliabilityPolicy,
    run_with_reliability,
)

__all__ = ["UnknownToolError"]


class ToolApprovalError(PermissionError):
    """Raised when a protected tool lacks matching human approval proof."""


class ToolFailureReceipt(BaseModel):
    """Stable error content returned to the model after controlled failure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    failure_kind: ToolFailureKind
    attempts: int
    error_type: str
    message: str


def _result_content(result: object) -> str:
    """Serialize supported local or future remote tool results as message text."""

    if isinstance(result, BaseModel):
        return result.model_dump_json()
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)


class ToolRuntime:
    """Coordinate approval, catalog lookup, reliable execution, and messages."""

    def __init__(
        self,
        catalog: ToolCatalog,
        *,
        policy: ToolReliabilityPolicy | None = None,
        audit: ToolAuditLog | None = None,
    ) -> None:
        self._catalog = catalog
        self._policy = policy or ToolReliabilityPolicy()
        self._audit = audit or ToolAuditLog()

    @property
    def tool_schemas(self) -> tuple[dict[str, object], ...]:
        """Expose registered schemas for model tool binding."""

        return self._catalog.model_schemas()

    @property
    def audit(self) -> ToolAuditLog:
        """Expose the ledger used by this runtime for inspection."""

        return self._audit

    async def execute(
        self,
        tool_call: ToolCall,
        *,
        approval: ApprovalProof | None = None,
    ) -> ToolMessage:
        """Execute one approved tool call and always preserve its call ID."""

        name = tool_call["name"]
        tool_call_id = tool_call["id"]

        if tool_needs_human(tool_call):
            if approval is None or not approval_proof_covers(approval, tool_call):
                raise ToolApprovalError(
                    f"Protected tool {name!r} lacks approval for call {tool_call_id!r}"
                )
            if not approval.decision.approved:
                denied = ActionDenied(
                    tool_name=name,
                    operator=approval.decision.operator,
                    note=approval.decision.note,
                )
                self._audit.record_denied(
                    tool_call_id=tool_call_id,
                    tool_name=name,
                    reason=denied.model_dump_json(),
                )
                return ToolMessage(
                    content=denied.model_dump_json(),
                    tool_call_id=tool_call_id,
                    name=name,
                    status="error",
                )

        tool = self._catalog.resolve(name)
        try:
            result = await run_with_reliability(
                tool_call_id=tool_call_id,
                tool_name=name,
                handler=tool.handler,
                arguments=tool_call["args"],
                retry_safe=tool.retry_safe,
                policy=self._policy,
                audit=self._audit,
            )
        except ToolExecutionFailed as error:
            failure = ToolFailureReceipt(
                tool_name=name,
                failure_kind=error.failure_kind,
                attempts=error.attempts,
                error_type=type(error.cause).__name__,
                message=str(error.cause),
            )
            return ToolMessage(
                content=failure.model_dump_json(),
                tool_call_id=tool_call_id,
                name=name,
                status="error",
            )

        return ToolMessage(
            content=_result_content(result),
            tool_call_id=tool_call_id,
            name=name,
        )


def build_default_tool_runtime(
    *,
    policy: ToolReliabilityPolicy | None = None,
    audit: ToolAuditLog | None = None,
) -> ToolRuntime:
    """Build the local runtime used by course and HTTP entry points."""

    return ToolRuntime(
        build_default_tool_catalog(),
        policy=policy,
        audit=audit,
    )


DEFAULT_TOOL_RUNTIME = build_default_tool_runtime()
TOOL_SCHEMAS = DEFAULT_TOOL_RUNTIME.tool_schemas


async def execute_tool_call(
    tool_call: ToolCall,
    *,
    approval: ApprovalProof | None = None,
) -> ToolMessage:
    """Preserve the original direct-call API through the default runtime."""

    return await DEFAULT_TOOL_RUNTIME.execute(tool_call, approval=approval)
