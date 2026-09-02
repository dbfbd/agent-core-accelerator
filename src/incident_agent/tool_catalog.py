"""Registry that gives every local tool one uniform executable shape."""

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from incident_agent.action_tools import RestartInput, restart_service
from incident_agent.models import DeploymentQuery, LogSearchQuery, MetricsQuery
from incident_agent.tools import (
    get_recent_deployments,
    get_service_metrics,
    search_logs,
)

type ToolHandler = Callable[[dict[str, object]], Awaitable[object]]


class UnknownToolError(LookupError):
    """Raised when a model requests a tool that is not registered."""


class DuplicateToolError(ValueError):
    """Raised when two tools try to claim the same public name."""


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Keep one tool's model-facing schema beside its Python handler."""

    name: str
    description: str
    parameters: dict[str, object]
    handler: ToolHandler
    retry_safe: bool = False

    def model_schema(self) -> dict[str, object]:
        """Return the function schema supplied to a tool-bindable model."""

        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolCatalog:
    """Register tools once and resolve model requests by exact name."""

    def __init__(self, tools: Iterable[ToolSpec] = ()) -> None:
        self._tools: dict[str, ToolSpec] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolSpec) -> None:
        """Add one tool while rejecting ambiguous duplicate names."""

        if tool.name in self._tools:
            raise DuplicateToolError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def resolve(self, name: str) -> ToolSpec:
        """Return one registered tool or raise an explicit lookup error."""

        try:
            return self._tools[name]
        except KeyError as error:
            raise UnknownToolError(f"Unknown tool: {name!r}") from error

    def model_schemas(self) -> tuple[dict[str, object], ...]:
        """Return every registered tool schema in stable registration order."""

        return tuple(tool.model_schema() for tool in self._tools.values())


async def _execute_metrics(arguments: dict[str, object]) -> object:
    """Validate raw metric arguments and call the metrics tool."""

    return await get_service_metrics(MetricsQuery.model_validate(arguments))


async def _execute_logs(arguments: dict[str, object]) -> object:
    """Validate raw log arguments and call the log-search tool."""

    return await search_logs(LogSearchQuery.model_validate(arguments))


async def _execute_deployments(arguments: dict[str, object]) -> object:
    """Validate raw deployment arguments and call the deployment tool."""

    return await get_recent_deployments(DeploymentQuery.model_validate(arguments))


async def _execute_restart(arguments: dict[str, object]) -> object:
    """Validate raw restart arguments and call the protected action tool."""

    return await restart_service(RestartInput.model_validate(arguments))


def build_default_tool_catalog() -> ToolCatalog:
    """Build the local course catalog used when no external tools are injected."""

    return ToolCatalog(
        (
            ToolSpec(
                name="get_service_metrics",
                description="Return metric samples for one service and time window.",
                parameters=MetricsQuery.model_json_schema(),
                handler=_execute_metrics,
                retry_safe=True,
            ),
            ToolSpec(
                name="search_logs",
                description="Search one service's logs by text and time window.",
                parameters=LogSearchQuery.model_json_schema(),
                handler=_execute_logs,
                retry_safe=True,
            ),
            ToolSpec(
                name="get_recent_deployments",
                description="Return deployment records for one service and time window.",
                parameters=DeploymentQuery.model_json_schema(),
                handler=_execute_deployments,
                retry_safe=True,
            ),
            ToolSpec(
                name="restart_service",
                description="Restart one service after explicit human approval.",
                parameters=RestartInput.model_json_schema(),
                handler=_execute_restart,
                retry_safe=False,
            ),
        )
    )
