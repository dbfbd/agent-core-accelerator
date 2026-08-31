"""Tests for the explicit LangGraph state, nodes, and edges."""

import json

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from incident_agent.agent_loop import AgentStepLimitError
from incident_agent.graph_agent import build_agent_graph, run_graph_agent
from incident_agent.scripted_model import ScriptedModel


def metrics_tool_call_message() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_service_metrics",
                "args": {
                    "service": "checkout-api",
                    "start": "2026-08-20T10:00:00+00:00",
                    "end": "2026-08-20T10:10:00+00:00",
                },
                "id": "call_metrics_graph_1",
                "type": "tool_call",
            }
        ],
    )


def test_graph_contains_explicit_nodes_and_routes() -> None:
    model = ScriptedModel(responses=[AIMessage(content="No tools needed.")])

    graph = build_agent_graph(model)
    drawable_graph = graph.get_graph()
    edge_pairs = {(edge.source, edge.target) for edge in drawable_graph.edges}

    assert set(drawable_graph.nodes) == {"__start__", "model", "tools", "__end__"}
    assert ("__start__", "model") in edge_pairs
    assert ("model", "tools") in edge_pairs
    assert ("model", "__end__") in edge_pairs
    assert ("tools", "model") in edge_pairs


@pytest.mark.asyncio
async def test_graph_runs_model_tool_model_sequence() -> None:
    model = ScriptedModel(
        responses=[
            metrics_tool_call_message(),
            AIMessage(
                content=(
                    "Evidence: error rate rose from 0.01 to 0.21. "
                    "Inference: checkout-api is degraded."
                )
            ),
        ]
    )

    state = await run_graph_agent(
        model,
        "Investigate checkout-api between 10:00 and 10:10 UTC.",
    )

    assert [type(message) for message in state["messages"]] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
    ]
    assert state["model_calls"] == 2

    tool_message = state["messages"][3]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call_metrics_graph_1"
    assert isinstance(tool_message.content, str)
    tool_result = json.loads(tool_message.content)
    assert [point["error_rate"] for point in tool_result["points"]] == [
        0.01,
        0.18,
        0.21,
    ]

    assert len(model.calls) == 2
    assert len(model.calls[0]) == 2
    assert len(model.calls[1]) == 4


@pytest.mark.asyncio
async def test_graph_stops_after_model_call_limit() -> None:
    model = ScriptedModel(responses=[metrics_tool_call_message()])

    with pytest.raises(AgentStepLimitError, match="after 1 calls"):
        await run_graph_agent(model, "Keep investigating.", max_model_calls=1)
