"""Discover and execute an incident tool through a real stdio MCP session."""

import asyncio
import json
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage
from mcp import StdioServerParameters

from incident_agent.graph_agent import run_graph_agent
from incident_agent.mcp_gateway import McpGateway
from incident_agent.scripted_model import ScriptedModel
from incident_agent.tool_audit import ToolAuditLog
from incident_agent.tool_catalog import ToolCatalog
from incident_agent.tool_reliability import ToolReliabilityPolicy
from incident_agent.tool_runtime import ToolRuntime


async def main() -> None:
    """Run model-to-MCP-to-ToolMessage-to-model through the real Agent graph."""

    gateway = McpGateway(
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "incident_agent.mcp_server"],
            cwd=Path.cwd(),
        )
    )
    await gateway.connect()
    try:
        specs = await gateway.discover_tool_specs()
        audit = ToolAuditLog()
        runtime = ToolRuntime(
            ToolCatalog(specs),
            policy=ToolReliabilityPolicy(max_attempts=2),
            audit=audit,
        )
        model = ScriptedModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_service_metrics",
                            "args": {
                                "service": "checkout-api",
                                "start": "2026-08-20T10:00:00Z",
                                "end": "2026-08-20T10:11:00Z",
                            },
                            "id": "mcp-metrics-001",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="MCP evidence shows checkout-api degradation."),
            ]
        )

        state = await run_graph_agent(
            model,
            "Read checkout-api metrics through MCP.",
            tool_runtime=runtime,
        )

        print("discovered_tools:")
        print([spec.name for spec in specs])
        print("messages:")
        for message in state["messages"]:
            print(type(message).__name__, repr(message.content))
            if isinstance(message, AIMessage):
                print("tool_calls=", message.tool_calls)
            if isinstance(message, ToolMessage):
                print(
                    "tool_call_id=",
                    message.tool_call_id,
                    "status=",
                    message.status,
                )
        print("audit:")
        for record in audit.list_records():
            print(json.dumps(record.model_dump(mode="json"), ensure_ascii=False))
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
