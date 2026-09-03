"""Deterministic local index that retrieves relevant runbook sections."""

import math
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from incident_agent.rag_models import (
    DocumentChunk,
    RetrievalHit,
    RetrievalResult,
    RunbookDocument,
)

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*|[\u4e00-\u9fff]", re.IGNORECASE)


def _tokenize(text: str) -> tuple[str, ...]:
    """Lowercase English words and retain individual Chinese characters."""

    return tuple(match.group(0).lower() for match in TOKEN_PATTERN.finditer(text))


def load_runbooks(directory: Path) -> tuple[RunbookDocument, ...]:
    """Load every Markdown runbook from one explicit directory."""

    documents = []
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        first_line = content.splitlines()[0].removeprefix("# ").strip()
        documents.append(
            RunbookDocument(
                source=path.name,
                title=first_line or path.stem,
                content=content,
            )
        )
    if not documents:
        raise FileNotFoundError(f"No Markdown runbooks found in {directory}")
    return tuple(documents)


def _build_chunk(
    document: RunbookDocument,
    heading: str,
    body_lines: list[str],
    section_number: int,
) -> DocumentChunk | None:
    """Build one non-empty section without capturing mutable loop variables."""

    text = "\n".join(body_lines).strip()
    if not text:
        return None
    return DocumentChunk(
        chunk_id=f"{document.source}:{section_number}",
        source=document.source,
        heading=heading,
        text=text,
        tokens=_tokenize(f"{heading} {text}"),
    )


def split_runbooks(
    documents: Iterable[RunbookDocument],
) -> tuple[DocumentChunk, ...]:
    """Split documents at headings while preserving source and section names."""

    chunks: list[DocumentChunk] = []
    for document in documents:
        heading = document.title
        body_lines: list[str] = []
        section_number = 0

        for line in document.content.splitlines():
            if line.startswith("## "):
                chunk = _build_chunk(
                    document,
                    heading,
                    body_lines,
                    section_number + 1,
                )
                if chunk is not None:
                    chunks.append(chunk)
                    section_number += 1
                heading = line.removeprefix("## ").strip()
                body_lines = []
            elif not line.startswith("# "):
                body_lines.append(line)
        chunk = _build_chunk(document, heading, body_lines, section_number + 1)
        if chunk is not None:
            chunks.append(chunk)

    return tuple(chunks)


class RunbookIndex:
    """Rank chunks with a small TF-IDF score and return cited evidence."""

    def __init__(self, chunks: tuple[DocumentChunk, ...]) -> None:
        if not chunks:
            raise ValueError("RunbookIndex requires at least one chunk")
        self._chunks = chunks
        self._document_frequency = Counter(
            token for chunk in chunks for token in set(chunk.tokens)
        )

    def _score(self, query_tokens: tuple[str, ...], chunk: DocumentChunk) -> float:
        """Calculate deterministic term-frequency/inverse-frequency relevance."""

        counts = Counter(chunk.tokens)
        total_chunks = len(self._chunks)
        score = 0.0
        for token in query_tokens:
            if counts[token] == 0:
                continue
            term_frequency = 1 + math.log(counts[token])
            inverse_frequency = 1 + math.log(
                (total_chunks + 1) / (self._document_frequency[token] + 1)
            )
            score += term_frequency * inverse_frequency
        return score

    def search(self, query: str, *, top_k: int = 3) -> RetrievalResult:
        """Return the highest-scoring sections with stable source citations."""

        query_tokens = _tokenize(query)
        ranked = sorted(
            ((self._score(query_tokens, chunk), chunk) for chunk in self._chunks),
            key=lambda item: (-item[0], item[1].chunk_id),
        )
        hits = tuple(
            RetrievalHit(
                source=chunk.source,
                heading=chunk.heading,
                text=chunk.text,
                score=round(score, 6),
            )
            for score, chunk in ranked[:top_k]
            if score > 0
        )
        return RetrievalResult(query=query, hits=hits)


def build_runbook_index(directory: Path) -> RunbookIndex:
    """Load, split, and index one runbook directory."""

    return RunbookIndex(split_runbooks(load_runbooks(directory)))
