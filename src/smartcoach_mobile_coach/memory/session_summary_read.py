"""Conversation history helpers for memory prompt gating."""

from __future__ import annotations


def has_prior_assistant_message(
    conversation_history,
) -> bool:
    if not isinstance(conversation_history, list):
        return False
    for msg in conversation_history:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role == "assistant" and isinstance(content, str) and content.strip():
            return True
    return False
