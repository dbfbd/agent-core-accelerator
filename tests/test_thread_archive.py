"""Tests for thread IDs and automatic graph checkpoints."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from incident_agent.scripted_model import ScriptedModel
from incident_agent.thread_archive import (
    checkpoint_build_resumable_agent,
    checkpoint_load_latest,
    thread_continue,
)


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
                "id": "call_metrics_checkpoint_1",
                "type": "tool_call",
            }
        ],
    )


@pytest.mark.asyncio
async def test_same_thread_continues_the_complete_message_history() -> None:
    model = ScriptedModel(
        responses=[
            metrics_tool_call_message(),
            AIMessage(content="First investigation found degraded metrics."),
            AIMessage(content="Second turn continued from the saved history."),
        ]
    )
    graph = checkpoint_build_resumable_agent(model)

    first_state = await thread_continue(
        graph,
        "thread-checkout-001",
        "Start investigating checkout-api.",
    )
    second_state = await thread_continue(
        graph,
        "thread-checkout-001",
        "Continue the same investigation.",
    )

    assert [type(message) for message in first_state["messages"]] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
    ]
    assert [type(message) for message in second_state["messages"]] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
        HumanMessage,
        AIMessage,
    ]
    tool_message = second_state["messages"][3]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call_metrics_checkpoint_1"
    assert second_state["messages"][4].content == (
        "First investigation found degraded metrics."
    )
    assert second_state["messages"][5].content == "Continue the same investigation."
    assert second_state["messages"][6].content == (
        "Second turn continued from the saved history."
    )
    assert [type(message) for message in model.calls[2]] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
        HumanMessage,
    ]

    latest_checkpoint = await checkpoint_load_latest(graph, "thread-checkout-001")
    assert latest_checkpoint is not None
    assert latest_checkpoint.next == ()
    assert latest_checkpoint.values["messages"] == second_state["messages"]


@pytest.mark.asyncio
async def test_different_thread_starts_with_separate_message_history() -> None:
    model = ScriptedModel(
        responses=[
            AIMessage(content="Checkout thread answer."),
            AIMessage(content="Inventory thread answer."),
        ]
    )
    graph = checkpoint_build_resumable_agent(model)

    await thread_continue(graph, "thread-checkout-001", "Investigate checkout-api.")
    inventory_state = await thread_continue(
        graph,
        "thread-inventory-001",
        "Investigate inventory-api.",
    )

    assert [message.content for message in inventory_state["messages"][1:]] == [
        "Investigate inventory-api.",
        "Inventory thread answer.",
    ]
    assert len(inventory_state["messages"]) == 3


@pytest.mark.asyncio
async def test_unknown_thread_has_no_checkpoint() -> None:
    graph = checkpoint_build_resumable_agent(
        ScriptedModel(responses=[AIMessage(content="Unused response.")])
    )

    assert await checkpoint_load_latest(graph, "thread-does-not-exist") is None
