"""Manual bridge from model tool calls to Python tool execution."""

from langchain_core.messages import ToolCall, ToolMessage

from incident_agent.action_tools import RestartInput, restart_service
from incident_agent.approval_gate import (
    ActionDenied,
    ApprovalProof,
    approval_proof_covers,
    tool_needs_human,
)
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
    {
        "name": "restart_service",
        "description": "Restart one service after explicit human approval.",
        "parameters": RestartInput.model_json_schema(),
    },
)


class UnknownToolError(LookupError):
    """Raised when a model requests a tool that is not registered."""


class ToolApprovalError(PermissionError):
    """Raised when a protected tool lacks matching human approval proof."""


async def execute_tool_call(
    tool_call: ToolCall,
    *,
    approval: ApprovalProof | None = None,
) -> ToolMessage:
    """Validate and execute one model-requested tool call."""

    name = tool_call["name"]
    arguments = tool_call["args"]

    if tool_needs_human(tool_call):
        if approval is None or not approval_proof_covers(approval, tool_call):
            raise ToolApprovalError(
                f"Protected tool {name!r} lacks approval for call {tool_call['id']!r}"
            )
        if not approval.decision.approved:
            denied = ActionDenied(
                tool_name=name,
                operator=approval.decision.operator,
                note=approval.decision.note,
            )
            return ToolMessage(
                content=denied.model_dump_json(),
                tool_call_id=tool_call["id"],
                name=name,
                status="error",
            )

    if name == "get_service_metrics":
        result = await get_service_metrics(MetricsQuery.model_validate(arguments))
    elif name == "search_logs":
        result = await search_logs(LogSearchQuery.model_validate(arguments))
    elif name == "get_recent_deployments":
        result = await get_recent_deployments(DeploymentQuery.model_validate(arguments))
    elif name == "restart_service":
        result = await restart_service(RestartInput.model_validate(arguments))
    else:
        raise UnknownToolError(f"Unknown tool: {name!r}")

    return ToolMessage(
        content=result.model_dump_json(),
        tool_call_id=tool_call["id"],
        name=name,
    )
