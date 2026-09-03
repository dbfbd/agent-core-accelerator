"""Stable business expectations used by the module evaluation runner."""

from pydantic import BaseModel, ConfigDict


class EvaluationCase(BaseModel):
    """Expected tool route and final-answer evidence for one scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    expected_tools: tuple[str, ...]
    answer_must_contain: tuple[str, ...]
    expect_tool_error: bool = False


RAG_CASE = EvaluationCase(
    case_id="rag-cited-runbook",
    expected_tools=("search_runbooks",),
    answer_must_contain=("checkout-api.md", "approval"),
)

CONTROLLED_FAILURE_CASE = EvaluationCase(
    case_id="controlled-tool-failure",
    expected_tools=("unavailable_dependency",),
    answer_must_contain=("unavailable",),
    expect_tool_error=True,
)
