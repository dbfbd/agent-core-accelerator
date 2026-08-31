"""Integration tests for the explicit model-tool-model loop."""

import json

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from incident_agent.agent_loop import AgentStepLimitError, run_agent
from incident_agent.scripted_model import ScriptedModel
from incident_agent.tool_runtime import UnknownToolError


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
                "id": "call_metrics_1",
                "type": "tool_call",
            }
        ],
    )


@pytest.mark.asyncio
async def test_agent_runs_model_tool_model_sequence() -> None:
    model = ScriptedModel(
        responses=[
            metrics_tool_call_message(),
            AIMessage(
                content=(
                    "Evidence: error rate rose from 0.01 to 0.21. "
                    "Inference: the service is degraded. "
                    "Unknown: the root cause is not yet proven."
                )
            ),
        ]
    )

    messages = await run_agent(
        model,
        "Investigate checkout-api between 10:00 and 10:10 UTC.",
    )

    assert [type(message) for message in messages] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
    ]

    tool_message = messages[3]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call_metrics_1"
    assert isinstance(tool_message.content, str)

    tool_result = json.loads(tool_message.content)
    assert tool_result["service"] == "checkout-api"
    assert [point["evidence_id"] for point in tool_result["points"]] == [
        "metric-checkout-1000",
        "metric-checkout-1005",
        "metric-checkout-1010",
    ]

    assert [schema["name"] for schema in model.bound_tools] == [
        "get_service_metrics",
        "search_logs",
        "get_recent_deployments",
    ]
    assert len(model.calls) == 2
    assert len(model.calls[0]) == 2
    assert len(model.calls[1]) == 4


@pytest.mark.asyncio
async def test_agent_rejects_unknown_tool_name() -> None:
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "restart_production",
                        "args": {},
                        "id": "call_unknown_1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )

    with pytest.raises(UnknownToolError, match="restart_production"):
        await run_agent(model, "Restart production.")


@pytest.mark.asyncio
async def test_agent_stops_after_model_call_limit() -> None:
    model = ScriptedModel(responses=[metrics_tool_call_message()])

    with pytest.raises(AgentStepLimitError, match="after 1 calls"):
        await run_agent(model, "Keep investigating.", max_model_calls=1)
