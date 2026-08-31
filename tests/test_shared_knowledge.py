"""Tests for service knowledge shared independently of thread checkpoints."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from incident_agent.scripted_model import ScriptedModel
from incident_agent.shared_knowledge import (
    ServiceKnowledgeNote,
    store_create_in_memory,
    store_list_service_notes,
    store_recall_as_system_message,
    store_save_service_note,
)
from incident_agent.thread_archive import (
    checkpoint_build_resumable_agent,
    thread_continue,
)


@pytest.mark.asyncio
async def test_note_saved_from_one_thread_is_visible_to_another_thread() -> None:
    knowledge_store = store_create_in_memory()
    note_from_thread_a = ServiceKnowledgeNote(
        note_id="checkout-owner",
        service="checkout-api",
        text="The Payments team owns checkout-api incidents.",
        source_thread_id="thread-checkout-001",
    )

    await store_save_service_note(knowledge_store, note_from_thread_a)

    requesting_thread_b = "thread-checkout-002"
    notes_seen_by_thread_b = await store_list_service_notes(
        knowledge_store,
        "checkout-api",
    )

    assert requesting_thread_b != note_from_thread_a.source_thread_id
    assert notes_seen_by_thread_b == [note_from_thread_a]


@pytest.mark.asyncio
async def test_service_shelves_keep_shared_knowledge_separate() -> None:
    knowledge_store = store_create_in_memory()
    checkout_note = ServiceKnowledgeNote(
        note_id="checkout-runbook",
        service="checkout-api",
        text="Check payment upstream timeouts first.",
        source_thread_id="thread-checkout-001",
    )
    inventory_note = ServiceKnowledgeNote(
        note_id="inventory-runbook",
        service="inventory-api",
        text="Check stock synchronization lag first.",
        source_thread_id="thread-inventory-001",
    )

    await store_save_service_note(knowledge_store, checkout_note)
    await store_save_service_note(knowledge_store, inventory_note)

    assert await store_list_service_notes(knowledge_store, "checkout-api") == [
        checkout_note
    ]
    assert await store_list_service_notes(knowledge_store, "inventory-api") == [
        inventory_note
    ]


@pytest.mark.asyncio
async def test_new_thread_model_receives_recalled_store_knowledge() -> None:
    knowledge_store = store_create_in_memory()
    await store_save_service_note(
        knowledge_store,
        ServiceKnowledgeNote(
            note_id="checkout-owner",
            service="checkout-api",
            text="The Payments team owns checkout-api incidents.",
            source_thread_id="thread-checkout-001",
        ),
    )
    shared_knowledge_message = await store_recall_as_system_message(
        knowledge_store,
        "checkout-api",
    )
    assert shared_knowledge_message is not None

    model = ScriptedModel(
        responses=[AIMessage(content="I will involve the Payments team.")]
    )
    graph = checkpoint_build_resumable_agent(model)
    await thread_continue(
        graph,
        "thread-checkout-002",
        "Who owns this incident?",
        context_messages=[shared_knowledge_message],
    )

    assert [type(message) for message in model.calls[0]] == [
        SystemMessage,
        SystemMessage,
        HumanMessage,
    ]
    assert model.calls[0][1].content == (
        "Shared service knowledge for checkout-api:\n"
        "- The Payments team owns checkout-api incidents. "
        "(source thread: thread-checkout-001)"
    )
