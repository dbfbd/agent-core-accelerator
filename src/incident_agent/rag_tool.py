"""Register runbook retrieval as one normal Agent tool."""

from incident_agent.rag_index import RunbookIndex
from incident_agent.rag_models import RunbookQuery
from incident_agent.tool_catalog import ToolCatalog, ToolHandler, ToolSpec

RAG_TOOL_NAME = "search_runbooks"


def make_rag_handler(index: RunbookIndex) -> ToolHandler:
    """Bind one built index into the catalog's async handler shape."""

    async def search(arguments: dict[str, object]) -> object:
        query = RunbookQuery.model_validate(arguments)
        return index.search(query.query, top_k=query.top_k)

    return search


def register_rag_tool(catalog: ToolCatalog, index: RunbookIndex) -> None:
    """Add the cited runbook search capability to an existing catalog."""

    catalog.register(
        ToolSpec(
            name=RAG_TOOL_NAME,
            description=(
                "Search incident runbooks and return relevant sections with sources."
            ),
            parameters=RunbookQuery.model_json_schema(),
            handler=make_rag_handler(index),
            retry_safe=True,
        )
    )
