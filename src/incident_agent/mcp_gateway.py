"""MCP client gateway that turns discovered remote tools into ToolSpec values."""

from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

from incident_agent.tool_catalog import ToolHandler, ToolSpec


class McpNotConnectedError(RuntimeError):
    """Raised when discovery or execution is attempted before connection."""


class McpToolCallError(RuntimeError):
    """Raised when a remote MCP tool reports an application error."""


class McpGateway:
    """Own one stdio MCP session and expose remote tools in local catalog shape."""

    def __init__(self, server: StdioServerParameters) -> None:
        self._server = server
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        """Start the configured server process and initialize one MCP session."""

        read_stream, write_stream = await self._stack.enter_async_context(
            stdio_client(self._server)
        )
        self._session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()

    async def close(self) -> None:
        """Close the MCP session and its server process."""

        self._session = None
        await self._stack.aclose()

    def _connected_session(self) -> ClientSession:
        """Return the active session or explain the lifecycle mistake."""

        if self._session is None:
            raise McpNotConnectedError("MCP gateway is not connected")
        return self._session

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
    ) -> object:
        """Call one remote tool and normalize its supported result content."""

        result = await self._connected_session().call_tool(name, arguments)
        return _mcp_result_value(name, result)

    def _make_handler(self, name: str) -> ToolHandler:
        """Bind one discovered remote name into the local handler signature."""

        async def call_remote(arguments: dict[str, object]) -> object:
            return await self.call_tool(name, arguments)

        return call_remote

    async def discover_tool_specs(self) -> tuple[ToolSpec, ...]:
        """List remote MCP tools and translate them into catalog entries."""

        result = await self._connected_session().list_tools()
        return tuple(
            ToolSpec(
                name=tool.name,
                description=tool.description or f"Remote MCP tool {tool.name}",
                parameters=dict(tool.inputSchema),
                handler=self._make_handler(tool.name),
                retry_safe=tool.name != "restart_service",
            )
            for tool in result.tools
        )


def _mcp_result_value(name: str, result: CallToolResult) -> object:
    """Prefer structured MCP output and preserve readable text fallback."""

    if result.isError:
        detail = "\n".join(
            item.text for item in result.content if isinstance(item, TextContent)
        )
        raise McpToolCallError(f"MCP tool {name!r} failed: {detail}")
    if result.structuredContent is not None:
        return result.structuredContent

    text_parts = [item.text for item in result.content if isinstance(item, TextContent)]
    if len(text_parts) == 1:
        return text_parts[0]
    return {"text": text_parts}
