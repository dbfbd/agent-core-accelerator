"""Retrieve cited runbook evidence through the complete Agent tool path."""

import asyncio
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from incident_agent.graph_agent import run_graph_agent
from incident_agent.rag_index import build_runbook_index
from incident_agent.rag_tool import register_rag_tool
from incident_agent.scripted_model import ScriptedModel
from incident_agent.tool_catalog import build_default_tool_catalog
from incident_agent.tool_runtime import ToolRuntime


async def main() -> None:
    """Run HumanMessage-to-RAG-ToolMessage-to-cited-AIMessage."""

    catalog = build_default_tool_catalog()
    index = build_runbook_index(Path("knowledge/runbooks"))
    register_rag_tool(catalog, index)
    runtime = ToolRuntime(catalog)
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_runbooks",
                        "args": {
                            "query": "checkout payment upstream timeout restart safety",
                            "top_k": 2,
                        },
                        "id": "rag-runbook-001",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content=(
                    "Check payment latency and the latest deployment before restart; "
                    "restart still requires approval. Source: "
                    "checkout-api.md#Payment upstream timeout and #Safe response."
                )
            ),
        ]
    )
    state = await run_graph_agent(
        model,
        "How should I handle checkout payment upstream timeouts?",
        tool_runtime=runtime,
    )

    for message in state["messages"]:
        print(type(message).__name__, repr(message.content))
        if isinstance(message, AIMessage):
            print("tool_calls=", message.tool_calls)
        if isinstance(message, ToolMessage):
            print("source_payload=", message.content)


if __name__ == "__main__":
    asyncio.run(main())
