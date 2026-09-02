"""Run three complete Agent paths through the reliable tool runtime."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import cast

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from incident_agent.graph_state import AgentState
from incident_agent.scripted_model import ScriptedModel
from incident_agent.streaming_agent import stream_compiled_graph
from incident_agent.thread_archive import (
    checkpoint_build_resumable_agent,
    checkpoint_load_latest,
    thread_prepare_turn,
)
from incident_agent.tool_audit import ToolAuditLog
from incident_agent.tool_catalog import ToolCatalog, ToolHandler, ToolSpec
from incident_agent.tool_reliability import (
    ToolReliabilityPolicy,
    TransientToolError,
)
from incident_agent.tool_runtime import ToolRuntime

type ScenarioHandler = Callable[[dict[str, object]], Awaitable[object]]


def _make_temporary_handler() -> ScenarioHandler:
    """Fail once with a temporary error and succeed on the second attempt."""

    attempts = 0

    async def fetch_status(arguments: dict[str, object]) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TransientToolError("metrics gateway briefly unavailable")
        return {
            "service": arguments["service"],
            "status": "healthy after retry",
        }

    return fetch_status


async def _permanent_failure(arguments: dict[str, object]) -> object:
    """Raise a business error that must not be retried."""

    raise ValueError(f"unknown service: {arguments['service']}")


async def _slow_tool(arguments: dict[str, object]) -> object:
    """Take longer than the scenario's timeout limit."""

    await asyncio.sleep(0.05)
    return {"service": arguments["service"], "status": "too late"}


def _scenario_catalog(name: str, handler: ToolHandler) -> ToolCatalog:
    """Build a one-tool catalog so each failure route stays visually isolated."""

    return ToolCatalog(
        (
            ToolSpec(
                name=name,
                description="Return one demonstration service status.",
                parameters={
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
                    "required": ["service"],
                    "additionalProperties": False,
                },
                handler=handler,
                retry_safe=True,
            ),
        )
    )


def _scenario_model(
    *,
    tool_name: str,
    tool_call_id: str,
    final_answer: str,
) -> ScriptedModel:
    """Return one ToolCall followed by a final answer for a scenario."""

    return ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": tool_name,
                        "args": {"service": "checkout-api"},
                        "id": tool_call_id,
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content=final_answer),
        ]
    )


def _print_message(position: int, message: BaseMessage) -> None:
    """Print every message field needed to inspect the complete business state."""

    print(f"{position}. {type(message).__name__}")
    print(f"   content={message.content!r}")
    if isinstance(message, AIMessage):
        print(f"   tool_calls={message.tool_calls!r}")
    if isinstance(message, ToolMessage):
        print(
            "   "
            f"tool_call_id={message.tool_call_id!r} "
            f"name={message.name!r} status={message.status!r}"
        )


async def run_scenario(
    *,
    title: str,
    thread_id: str,
    tool_name: str,
    handler: ToolHandler,
    policy: ToolReliabilityPolicy,
    final_answer: str,
) -> None:
    """Stream one graph run, then print its complete state and attempt audit."""

    tool_call_id = f"{thread_id}-call"
    audit = ToolAuditLog()
    runtime = ToolRuntime(
        _scenario_catalog(tool_name, handler),
        policy=policy,
        audit=audit,
    )
    model = _scenario_model(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        final_answer=final_answer,
    )
    graph = checkpoint_build_resumable_agent(model, tool_runtime=runtime)
    user_input = f"Check checkout-api through {tool_name}."
    graph_input, thread_address = await thread_prepare_turn(
        graph,
        thread_id,
        user_input,
    )

    events = [
        event
        async for event in stream_compiled_graph(
            graph,
            graph_input,
            user_input=user_input,
            config=thread_address,
        )
    ]
    snapshot = await checkpoint_load_latest(graph, thread_id)
    if snapshot is None:
        raise RuntimeError(f"Scenario {thread_id!r} did not save a checkpoint")
    state = cast(AgentState, snapshot.values)

    print(f"\n=== {title} ===")
    print("events:")
    for event in events:
        print(json.dumps(event.model_dump(mode="json"), ensure_ascii=False))

    print("messages:")
    for position, message in enumerate(state["messages"], start=1):
        _print_message(position, message)

    print("audit:")
    for record in audit.list_records(tool_call_id=tool_call_id):
        print(json.dumps(record.model_dump(mode="json"), ensure_ascii=False))


async def main() -> None:
    """Run retry-success, permanent-failure, and timeout business paths."""

    await run_scenario(
        title="TEMPORARY FAILURE: retry then succeed",
        thread_id="reliability-retry",
        tool_name="fetch_status_with_retry",
        handler=_make_temporary_handler(),
        policy=ToolReliabilityPolicy(
            timeout_seconds=0.2,
            max_attempts=2,
            retry_delay_seconds=0,
        ),
        final_answer="The temporary metrics failure recovered on retry.",
    )
    await run_scenario(
        title="PERMANENT FAILURE: do not retry",
        thread_id="reliability-permanent",
        tool_name="fetch_unknown_service",
        handler=_permanent_failure,
        policy=ToolReliabilityPolicy(
            timeout_seconds=0.2,
            max_attempts=3,
            retry_delay_seconds=0,
        ),
        final_answer="The service name is invalid, so no retry was attempted.",
    )
    await run_scenario(
        title="TIMEOUT: stop waiting and return controlled failure",
        thread_id="reliability-timeout",
        tool_name="fetch_slow_status",
        handler=_slow_tool,
        policy=ToolReliabilityPolicy(
            timeout_seconds=0.01,
            max_attempts=1,
            retry_delay_seconds=0,
        ),
        final_answer="The status lookup timed out without crashing the agent.",
    )


if __name__ == "__main__":
    asyncio.run(main())
