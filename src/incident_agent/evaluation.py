"""Business-level evaluation of complete Agent message trajectories."""

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, ConfigDict

from incident_agent.evaluation_cases import EvaluationCase
from incident_agent.graph_state import AgentState


class EvaluationResult(BaseModel):
    """Explain every deterministic quality check for one completed case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    passed: bool
    used_tools: tuple[str, ...]
    final_answer: str | None
    checks: dict[str, bool]


def _used_tools(state: AgentState) -> tuple[str, ...]:
    """Read requested tool names from every AIMessage in order."""

    return tuple(
        tool_call["name"]
        for message in state["messages"]
        if isinstance(message, AIMessage)
        for tool_call in message.tool_calls
    )


def _final_answer(state: AgentState) -> str | None:
    """Return the newest non-tool AI answer."""

    for message in reversed(state["messages"]):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return (
                message.content
                if isinstance(message.content, str)
                else str(message.content)
            )
    return None


def evaluate_state(case: EvaluationCase, state: AgentState) -> EvaluationResult:
    """Grade tool selection, error expectation, and required answer evidence."""

    used_tools = _used_tools(state)
    final_answer = _final_answer(state)
    tool_errors = [
        message
        for message in state["messages"]
        if isinstance(message, ToolMessage) and message.status == "error"
    ]
    checks = {
        "tool_route": used_tools == case.expected_tools,
        "answer_present": final_answer is not None,
        "answer_evidence": final_answer is not None
        and all(
            required.lower() in final_answer.lower()
            for required in case.answer_must_contain
        ),
        "tool_error_expectation": bool(tool_errors) is case.expect_tool_error,
    }
    return EvaluationResult(
        case_id=case.case_id,
        passed=all(checks.values()),
        used_tools=used_tools,
        final_answer=final_answer,
        checks=checks,
    )
