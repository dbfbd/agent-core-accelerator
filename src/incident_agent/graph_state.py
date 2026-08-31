"""Shared state carried between LangGraph nodes."""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from incident_agent.approval_gate import ApprovalProof


class AgentState(TypedDict):
    """Complete state available while one agent graph is running."""

    messages: Annotated[list[BaseMessage], add_messages]
    model_calls: int
    approval: ApprovalProof | None


class AgentStateUpdate(TypedDict, total=False):
    """Partial state changes returned by one graph node."""

    messages: list[BaseMessage]
    model_calls: int
    approval: ApprovalProof | None
