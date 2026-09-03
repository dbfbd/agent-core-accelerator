"""Composition root that wires every final-project capability together."""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from mcp import StdioServerParameters

from incident_agent.api_app import AgentServiceContextFactory, create_app
from incident_agent.api_service import AgentHttpService
from incident_agent.graph_agent import build_agent_graph
from incident_agent.mcp_gateway import McpGateway
from incident_agent.model_gateway import build_chat_model
from incident_agent.persistence import open_sqlite_checkpointer
from incident_agent.rag_index import build_runbook_index
from incident_agent.rag_tool import register_rag_tool
from incident_agent.settings import AppSettings, load_settings
from incident_agent.tool_catalog import ToolCatalog, build_default_tool_catalog
from incident_agent.tool_runtime import ToolRuntime
from incident_agent.trace_observer import TraceObserver


async def _build_catalog(
    settings: AppSettings,
) -> tuple[ToolCatalog, McpGateway | None]:
    """Choose local tools or an MCP server, then add runbook retrieval."""

    gateway = None
    if settings.mcp_command is None:
        catalog = build_default_tool_catalog()
    else:
        gateway = McpGateway(
            StdioServerParameters(
                command=settings.mcp_command,
                args=list(settings.mcp_args()),
            )
        )
        try:
            await gateway.connect()
            catalog = ToolCatalog(await gateway.discover_tool_specs())
        except Exception:
            await gateway.close()
            raise

    try:
        register_rag_tool(catalog, build_runbook_index(settings.runbook_dir))
    except Exception:
        if gateway is not None:
            await gateway.close()
        raise
    return catalog, gateway


@asynccontextmanager
async def open_agent_service(
    settings: AppSettings,
) -> AsyncIterator[AgentHttpService]:
    """Own model, tools, SQLite, trace, and MCP lifecycles for one process."""

    gateway: McpGateway | None = None
    try:
        catalog, gateway = await _build_catalog(settings)
        runtime = ToolRuntime(catalog)
        trace = TraceObserver()
        model = build_chat_model(settings)
        async with open_sqlite_checkpointer(settings.checkpoint_path) as checkpointer:
            graph = build_agent_graph(
                model,
                checkpoint_saver=checkpointer,
                tool_runtime=runtime,
            )
            yield AgentHttpService(graph, trace=trace, audit=runtime.audit)
    finally:
        if gateway is not None:
            await gateway.close()


def build_service_context(settings: AppSettings) -> AgentServiceContextFactory:
    """Freeze validated settings into FastAPI's zero-argument lifecycle shape."""

    def service_context() -> AbstractAsyncContextManager[AgentHttpService]:
        return open_agent_service(settings)

    return service_context


def create_production_app(settings: AppSettings | None = None) -> FastAPI:
    """Create the final HTTP application from environment-backed settings."""

    configured = settings or load_settings()
    return create_app(
        api_token=configured.api_token_value,
        service_context_factory=build_service_context(configured),
    )
