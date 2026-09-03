"""Stable HTTP request and response models for the FastAPI boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from incident_agent.approval_gate import ApprovalTicket
from incident_agent.tool_audit import ToolAttemptRecord


class HttpPayload(BaseModel):
    """Shared validation rules for public HTTP payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentInvokeRequest(HttpPayload):
    """One HTTP request that starts or continues an agent thread."""

    thread_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    user_input: str = Field(min_length=1)


class ApprovalResumeRequest(HttpPayload):
    """One HTTP request that resumes a thread waiting for human approval."""

    thread_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    approved: bool
    operator: str = Field(min_length=1)
    note: str = ""


class PublicToolCall(HttpPayload):
    """Small JSON-safe view of one model-requested tool call."""

    tool_call_id: str
    name: str
    arguments: dict[str, object]


class PublicMessage(HttpPayload):
    """Stable public view of one LangChain message."""

    message_type: str
    content: str | list[str | dict[str, object]]
    tool_calls: tuple[PublicToolCall, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_status: str | None = None


class AgentRunResponse(HttpPayload):
    """JSON response returned after invoke or approval resume."""

    status: Literal["completed", "approval_required"]
    run_id: str
    thread_id: str
    answer: str | None
    model_calls: int
    approval: ApprovalTicket | None
    messages: tuple[PublicMessage, ...]


class ThreadHistoryResponse(HttpPayload):
    """Newest checkpoint state exposed through the history endpoint."""

    run_id: str
    thread_id: str
    model_calls: int
    approval: ApprovalTicket | None
    messages: tuple[PublicMessage, ...]


class ToolAuditResponse(HttpPayload):
    """All recorded tool attempts belonging to one Agent run."""

    run_id: str
    records: tuple[ToolAttemptRecord, ...]


class HealthResponse(HttpPayload):
    """Small process-health response that does not run the agent."""

    status: Literal["ok"] = "ok"
    service: Literal["incident-agent"] = "incident-agent"
