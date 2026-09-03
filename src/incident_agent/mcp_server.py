"""Standalone MCP server exposing the deterministic incident tools."""

from mcp.server.fastmcp import FastMCP

from incident_agent.action_tools import RestartInput, restart_service
from incident_agent.models import DeploymentQuery, LogSearchQuery, MetricsQuery
from incident_agent.tools import (
    get_recent_deployments,
    get_service_metrics,
    search_logs,
)

mcp = FastMCP(
    "incident-operations",
    instructions="Deterministic service metrics, logs, deployments, and actions.",
)


@mcp.tool(name="get_service_metrics", structured_output=True)
async def mcp_get_service_metrics(
    service: str,
    start: str,
    end: str,
) -> dict[str, object]:
    """Return metric samples for one service and ISO-8601 time window."""

    result = await get_service_metrics(
        MetricsQuery.model_validate({"service": service, "start": start, "end": end})
    )
    return result.model_dump(mode="json")


@mcp.tool(name="search_logs", structured_output=True)
async def mcp_search_logs(
    service: str,
    start: str,
    end: str,
    contains: str = "",
) -> dict[str, object]:
    """Search one service's logs by text and ISO-8601 time window."""

    result = await search_logs(
        LogSearchQuery.model_validate(
            {
                "service": service,
                "start": start,
                "end": end,
                "contains": contains,
            }
        )
    )
    return result.model_dump(mode="json")


@mcp.tool(name="get_recent_deployments", structured_output=True)
async def mcp_get_recent_deployments(
    service: str,
    start: str,
    end: str,
) -> dict[str, object]:
    """Return deployments for one service and ISO-8601 time window."""

    result = await get_recent_deployments(
        DeploymentQuery.model_validate({"service": service, "start": start, "end": end})
    )
    return result.model_dump(mode="json")


@mcp.tool(name="restart_service", structured_output=True)
async def mcp_restart_service(service: str, reason: str) -> dict[str, object]:
    """Return a simulated service restart receipt."""

    result = await restart_service(
        RestartInput.model_validate({"service": service, "reason": reason})
    )
    return result.model_dump(mode="json")


def main() -> None:
    """Run the incident MCP server over standard input and output."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
