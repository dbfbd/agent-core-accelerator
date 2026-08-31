"""Human-approval payloads and the resumable interrupt boundary."""

from collections.abc import Sequence
from typing import Literal

from langchain_core.messages import ToolCall
from langgraph.types import interrupt
from pydantic import BaseModel, Field

PROTECTED_TOOL_NAMES = frozenset({"restart_service"})


class RiskAction(BaseModel):
    """One exact high-risk tool call shown to the human reviewer."""

    tool_call_id: str
    tool_name: str
    arguments: dict[str, object]


class ApprovalTicket(BaseModel):
    """The complete approval request surfaced when the graph pauses."""

    headline: str = "High-risk service action requires human approval"
    risk: Literal["high"] = "high"
    actions: list[RiskAction] = Field(min_length=1)


class HumanDecision(BaseModel):
    """The human reviewer's validated resume input."""

    approved: bool
    operator: str = Field(min_length=1)
    note: str = ""


class ApprovalProof(BaseModel):
    """The ticket and matching human decision carried to tool execution."""

    ticket: ApprovalTicket
    decision: HumanDecision


class ActionDenied(BaseModel):
    """Structured tool result produced when the reviewer refuses an action."""

    status: Literal["denied"] = "denied"
    tool_name: str
    operator: str
    note: str


def tool_needs_human(tool_call: ToolCall) -> bool:
    """Return whether one tool call is protected by the approval gate."""

    return tool_call["name"] in PROTECTED_TOOL_NAMES


def build_approval_ticket(tool_calls: Sequence[ToolCall]) -> ApprovalTicket:
    """Copy all protected calls into one human-readable approval ticket."""

    actions = [
        RiskAction(
            tool_call_id=tool_call["id"],
            tool_name=tool_call["name"],
            arguments=dict(tool_call["args"]),
        )
        for tool_call in tool_calls
        if tool_needs_human(tool_call)
    ]
    return ApprovalTicket(actions=actions)


def pause_for_human(ticket: ApprovalTicket) -> ApprovalProof:
    """Pause the graph and turn the later resume value into approval proof."""

    raw_decision = interrupt(ticket.model_dump(mode="json"))
    decision = HumanDecision.model_validate(raw_decision)
    return ApprovalProof(ticket=ticket, decision=decision)


def approval_proof_covers(
    proof: ApprovalProof,
    tool_call: ToolCall,
) -> bool:
    """Check that approval references the exact call ID, name, and arguments."""

    return any(
        action.tool_call_id == tool_call["id"]
        and action.tool_name == tool_call["name"]
        and action.arguments == tool_call["args"]
        for action in proof.ticket.actions
    )
