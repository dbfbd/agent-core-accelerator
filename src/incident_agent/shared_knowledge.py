"""Cross-thread service knowledge stored outside graph checkpoints."""

from langchain_core.messages import SystemMessage
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from pydantic import BaseModel, ConfigDict, Field

KNOWLEDGE_SHELF = "service_knowledge"


class ServiceKnowledgeNote(BaseModel):
    """One explicit service fact that can be shared across threads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    note_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_thread_id: str = Field(min_length=1)


def _store_service_shelf(service: str) -> tuple[str, str]:
    """Return the Store namespace used as one service's shelf address."""

    return (KNOWLEDGE_SHELF, service)


def store_create_in_memory() -> InMemoryStore:
    """Create the development-only shared knowledge cabinet."""

    return InMemoryStore()


async def store_save_service_note(
    knowledge_store: BaseStore,
    note: ServiceKnowledgeNote,
) -> None:
    """Save or replace one note by its stable note ID."""

    await knowledge_store.aput(
        _store_service_shelf(note.service),
        note.note_id,
        note.model_dump(),
    )


async def store_list_service_notes(
    knowledge_store: BaseStore,
    service: str,
) -> list[ServiceKnowledgeNote]:
    """Read every shared note stored for one service."""

    items = await knowledge_store.asearch(_store_service_shelf(service))
    return [ServiceKnowledgeNote.model_validate(item.value) for item in items]


async def store_recall_as_system_message(
    knowledge_store: BaseStore,
    service: str,
) -> SystemMessage | None:
    """Turn shared service notes into one clearly labelled model-context message."""

    notes = await store_list_service_notes(knowledge_store, service)
    if not notes:
        return None

    note_lines = "\n".join(
        f"- {note.text} (source thread: {note.source_thread_id})" for note in notes
    )
    return SystemMessage(
        id=f"shared-knowledge:{service}",
        content=f"Shared service knowledge for {service}:\n{note_lines}",
    )
