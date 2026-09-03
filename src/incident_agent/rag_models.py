"""Stable document and retrieval models for local runbook RAG."""

from pydantic import BaseModel, ConfigDict, Field


class RagPayload(BaseModel):
    """Shared strict validation for RAG data crossing file boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RunbookDocument(RagPayload):
    """One complete source document loaded from disk."""

    source: str
    title: str
    content: str


class DocumentChunk(RagPayload):
    """One independently searchable runbook section."""

    chunk_id: str
    source: str
    heading: str
    text: str
    tokens: tuple[str, ...]


class RetrievalHit(RagPayload):
    """One matching section with its source and relevance score."""

    source: str
    heading: str
    text: str
    score: float


class RetrievalResult(RagPayload):
    """Stable tool result containing ranked runbook evidence."""

    query: str
    hits: tuple[RetrievalHit, ...]


class RunbookQuery(RagPayload):
    """Validated arguments accepted by the runbook search tool."""

    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=5)
