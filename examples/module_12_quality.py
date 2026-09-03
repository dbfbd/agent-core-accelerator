"""Run deterministic tracing and evaluation over two complete Agent paths."""

import asyncio
import json
from pathlib import Path

from langchain_core.messages import AIMessage

from incident_agent.evaluation import evaluate_state
from incident_agent.evaluation_cases import CONTROLLED_FAILURE_CASE, RAG_CASE
from incident_agent.graph_agent import run_graph_agent
from incident_agent.rag_index import build_runbook_index
from incident_agent.rag_tool import register_rag_tool
from incident_agent.scripted_model import ScriptedModel
from incident_agent.tool_catalog import (
    ToolCatalog,
    ToolSpec,
    build_default_tool_catalog,
)
from incident_agent.tool_runtime import ToolRuntime
from incident_agent.trace_observer import TraceObserver


async def _unavailable_dependency(arguments: dict[str, object]) -> object:
    """Produce one permanent external dependency failure."""

    raise ValueError(f"dependency unavailable for {arguments['service']}")


async def _rag_state():
    """Return a complete cited RAG state for evaluation."""

    catalog = build_default_tool_catalog()
    register_rag_tool(catalog, build_runbook_index(Path("knowledge/runbooks")))
    runtime = ToolRuntime(catalog)
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_runbooks",
                        "args": {"query": "checkout timeout safe restart", "top_k": 2},
                        "id": "eval-rag-001",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="checkout-api.md says restart requires operator approval."
            ),
        ]
    )
    return await run_graph_agent(
        model,
        "Find the checkout timeout runbook.",
        tool_runtime=runtime,
    )


async def _failure_state():
    """Return a complete controlled tool-error state for evaluation."""

    catalog = ToolCatalog(
        (
            ToolSpec(
                name="unavailable_dependency",
                description="Demonstrate a permanent dependency failure.",
                parameters={
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
                    "required": ["service"],
                },
                handler=_unavailable_dependency,
                retry_safe=True,
            ),
        )
    )
    runtime = ToolRuntime(catalog)
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "unavailable_dependency",
                        "args": {"service": "checkout-api"},
                        "id": "eval-failure-001",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="The dependency is unavailable; evidence is incomplete."),
        ]
    )
    return await run_graph_agent(
        model,
        "Check an unavailable dependency.",
        tool_runtime=runtime,
    )


async def main() -> None:
    """Trace and grade the RAG and controlled-failure business cases."""

    observer = TraceObserver()
    scenarios = (
        (
            RAG_CASE,
            "eval-thread-rag",
            "Find the checkout timeout runbook.",
            await _rag_state(),
        ),
        (
            CONTROLLED_FAILURE_CASE,
            "eval-thread-failure",
            "Check an unavailable dependency.",
            await _failure_state(),
        ),
    )

    for case, thread_id, user_input, state in scenarios:
        trace = observer.capture_state(
            thread_id=thread_id,
            user_input=user_input,
            state=state,
            status="completed",
        )
        result = evaluate_state(case, state)
        print(f"\n=== {case.case_id} ===")
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        print(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False, indent=2))
        if not result.passed:
            raise RuntimeError(f"Evaluation failed: {case.case_id}")


if __name__ == "__main__":
    asyncio.run(main())
