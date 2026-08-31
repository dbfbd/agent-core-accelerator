"""Manual bridge from model tool calls to Python tool execution."""

from langchain_core.messages import ToolCall, ToolMessage

from incident_agent.models import DeploymentQuery, LogSearchQuery, MetricsQuery
from incident_agent.tools import (
    get_recent_deployments,
    get_service_metrics,
    search_logs,
)

TOOL_SCHEMAS: tuple[dict[str, object], ...] = (
    {
        "name": "get_service_metrics",
        "description": "Return metric samples for one service and time window.",
        "parameters": MetricsQuery.model_json_schema(),
    },
    {
        "name": "search_logs",
        "description": "Search one service's logs by text and time window.",
        "parameters": LogSearchQuery.model_json_schema(),
    },
    {
        "name": "get_recent_deployments",
        "description": "Return deployment records for one service and time window.",
        "parameters": DeploymentQuery.model_json_schema(),
    },
)


class UnknownToolError(LookupError):
    """Raised when a model requests a tool that is not registered."""


async def execute_tool_call(tool_call: ToolCall) -> ToolMessage:
    """Validate and execute one model-requested tool call."""

    name = tool_call["name"]
    arguments = tool_call["args"]

    if name == "get_service_metrics":
        result = await get_service_metrics(MetricsQuery.model_validate(arguments))
    elif name == "search_logs":
        result = await search_logs(LogSearchQuery.model_validate(arguments))
    elif name == "get_recent_deployments":
        result = await get_recent_deployments(DeploymentQuery.model_validate(arguments))
    else:
        raise UnknownToolError(f"Unknown tool: {name!r}")

    return ToolMessage(
        content=result.model_dump_json(),
        tool_call_id=tool_call["id"],
        name=name,
    )
