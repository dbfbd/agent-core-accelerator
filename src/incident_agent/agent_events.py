"""Stable application events emitted while the agent graph is running."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from incident_agent.approval_gate import ApprovalTicket


class AgentEvent(BaseModel):
    """Shared validation rules for every public stream event."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentStartedEvent(AgentEvent):
    """The request was accepted and graph execution is about to begin."""

    event: Literal["agent_started"] = "agent_started"
    run_id: str
    user_input: str


class ToolRequest(BaseModel):
    """Small public summary of one model-requested tool call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    tool_call_id: str


class ToolsRequestedEvent(AgentEvent):
    """One model turn requested one or more tools."""

    event: Literal["tools_requested"] = "tools_requested"
    model_call: int
    requests: tuple[ToolRequest, ...]


class ToolCompletedEvent(AgentEvent):
    """One requested tool finished and produced a ToolMessage."""

    event: Literal["tool_completed"] = "tool_completed"
    name: str
    tool_call_id: str
    content: str


class ToolFailedEvent(AgentEvent):
    """One requested tool ended with a controlled error ToolMessage."""

    event: Literal["tool_failed"] = "tool_failed"
    name: str
    tool_call_id: str
    content: str


class AgentCompletedEvent(AgentEvent):
    """The graph reached END after the model produced a final answer."""

    event: Literal["agent_completed"] = "agent_completed"
    model_calls: int
    answer: str


class ApprovalRequiredEvent(AgentEvent):
    """The graph paused and exposed one high-risk action for human review."""

    event: Literal["approval_required"] = "approval_required"
    ticket: ApprovalTicket


type AgentStreamEvent = (
    AgentStartedEvent
    | ToolsRequestedEvent
    | ToolCompletedEvent
    | ToolFailedEvent
    | AgentCompletedEvent
    | ApprovalRequiredEvent
)
