"""Tests for translating graph updates into public stream events."""

import json

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from incident_agent.agent_events import (
    AgentCompletedEvent,
    AgentStartedEvent,
    ToolCompletedEvent,
    ToolsRequestedEvent,
)
from incident_agent.graph_agent import build_agent_graph, create_initial_state
from incident_agent.scripted_model import ScriptedModel
from incident_agent.streaming_agent import stream_graph_agent


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
                "id": "call_metrics_stream_1",
                "type": "tool_call",
            }
        ],
    )


@pytest.mark.asyncio
async def test_stream_yields_each_business_event_in_execution_order() -> None:
    model = ScriptedModel(
        responses=[
            metrics_tool_call_message(),
            AIMessage(content="checkout-api is degraded based on metric evidence."),
        ]
    )
    stream = stream_graph_agent(model, "Investigate checkout-api.")

    started = await anext(stream)
    assert isinstance(started, AgentStartedEvent)
    assert model.calls == []

    requested = await anext(stream)
    assert isinstance(requested, ToolsRequestedEvent)
    assert len(model.calls) == 1
    assert [type(message) for message in model.calls[0]] == [
        SystemMessage,
        HumanMessage,
    ]
    assert requested.model_call == 1
    assert requested.requests[0].name == "get_service_metrics"
    assert requested.requests[0].tool_call_id == "call_metrics_stream_1"

    tool_completed = await anext(stream)
    assert isinstance(tool_completed, ToolCompletedEvent)
    assert len(model.calls) == 1
    assert tool_completed.tool_call_id == "call_metrics_stream_1"
    tool_result = json.loads(tool_completed.content)
    assert [point["error_rate"] for point in tool_result["points"]] == [
        0.01,
        0.18,
        0.21,
    ]

    completed = await anext(stream)
    assert isinstance(completed, AgentCompletedEvent)
    assert len(model.calls) == 2
    assert [type(message) for message in model.calls[1]] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        ToolMessage,
    ]
    assert completed.model_calls == 2
    assert completed.answer == "checkout-api is degraded based on metric evidence."

    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_stream_finishes_without_tool_events_for_direct_answer() -> None:
    model = ScriptedModel(responses=[AIMessage(content="No investigation is needed.")])

    events = [
        event async for event in stream_graph_agent(model, "Can this finish directly?")
    ]

    assert [type(event) for event in events] == [
        AgentStartedEvent,
        AgentCompletedEvent,
    ]
    assert events[-1].model_calls == 1


@pytest.mark.asyncio
async def test_values_stream_exposes_complete_message_state_after_each_step() -> None:
    model = ScriptedModel(
        responses=[
            metrics_tool_call_message(),
            AIMessage(content="checkout-api is degraded based on metric evidence."),
        ]
    )
    graph = build_agent_graph(model)

    states = [
        part["data"]
        async for part in graph.astream(
            create_initial_state("Investigate checkout-api."),
            stream_mode="values",
            version="v2",
        )
    ]

    assert [state["model_calls"] for state in states] == [0, 1, 1, 2]
    assert [[type(message) for message in state["messages"]] for state in states] == [
        [SystemMessage, HumanMessage],
        [SystemMessage, HumanMessage, AIMessage],
        [SystemMessage, HumanMessage, AIMessage, ToolMessage],
        [SystemMessage, HumanMessage, AIMessage, ToolMessage, AIMessage],
    ]

    first_ai_message = states[1]["messages"][2]
    assert isinstance(first_ai_message, AIMessage)
    assert first_ai_message.tool_calls[0]["id"] == "call_metrics_stream_1"

    tool_message = states[2]["messages"][3]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call_metrics_stream_1"

    final_ai_message = states[3]["messages"][4]
    assert isinstance(final_ai_message, AIMessage)
    assert final_ai_message.tool_calls == []
