"""Phase F 3F.1 — session summary writer (Topic 6 Layer B)."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from src.db.models.memory.session_summaries import SessionSummary
from src.services.security.external_apis.openai_service import (
    CostLimitExceededError,
    RateLimitExceededError,
    get_openai_service,
)
from src.smartcoach_mobile_coach.memory.plan_memory_store import (
    MEMORY_SOURCE_SESSION_SUMMARY,
    append_plan_memory,
)

logger = logging.getLogger(__name__)

_SESSION_WRITER_VERSION = 1
_MAX_SUMMARY_STORE_CHARS = 2000
_MAX_TAGS = 12
_MAX_PLAN_MEMORIES_FROM_SUMMARY = 2
_MIN_EXTRACTED_MEMORY_LEN = 24

_GENERIC_CHAFF = (
    "thanks",
    "thank you",
    "good run",
    "great run",
    "great job",
    "awesome",
    "sounds good",
    "ok thanks",
    "okay thanks",
    "lol",
    "nice work",
    "well done",
)

_SIGNAL_RE = re.compile(
    r"\b(prefer|rather|only|can't|cannot|must|avoid|never|schedule|week|training|"
    r"long run|days per|injury|goal|marathon|half|easy|tempo|pace|mile|miles|rest|"
    r"recovery|knee|surf|morning|evening|saturday|sunday|monday|tuesday|wednesday|"
    r"thursday|friday|volume|intensity|double|doubles|work|travel|treadmill|running)\b",
    re.IGNORECASE,
)


def worth_persisting_extracted_plan_memory(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < _MIN_EXTRACTED_MEMORY_LEN:
        return False
    tl = t.lower()
    if any(s in tl for s in _GENERIC_CHAFF):
        return False
    if not _SIGNAL_RE.search(tl):
        return False
    return True


def filter_plan_memory_extractions(candidates: List[str]) -> List[str]:
    out: List[str] = []
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        s = " ".join(raw.split())
        if not worth_persisting_extracted_plan_memory(s):
            continue
        out.append(s)
    return out[:_MAX_PLAN_MEMORIES_FROM_SUMMARY]


def _writer_enabled() -> bool:
    v = (os.getenv("SMARTCOACH_SESSION_SUMMARY_WRITER_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _summary_model() -> str:
    return (
        os.getenv("SMARTCOACH_SESSION_SUMMARY_MODEL", "gpt-4o-mini").strip()
        or "gpt-4o-mini"
    )


def extract_assistant_plain_text(assistant_reply: Union[str, Dict[str, Any]]) -> str:
    if isinstance(assistant_reply, str):
        return assistant_reply.strip()
    if not isinstance(assistant_reply, dict):
        return ""
    inner = assistant_reply.get("content")
    if isinstance(inner, str) and inner.strip():
        return inner.strip()
    return ""


def collect_tool_names_from_agent_meta(meta: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(meta, dict):
        return []
    timings = meta.get("timings_ms")
    if not isinstance(timings, dict):
        return []
    loops = timings.get("agent_loop_rounds")
    if not isinstance(loops, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for loop in loops:
        if not isinstance(loop, dict):
            continue
        tools = loop.get("tools")
        if not isinstance(tools, list):
            continue
        for entry in tools:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            n = name.strip()
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out


def _sanitize_tags(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    tags: List[str] = []
    for item in raw[:_MAX_TAGS]:
        if not isinstance(item, str):
            continue
        t = re.sub(r"[^\w\- ]+", "", item, flags=re.UNICODE).strip()
        if not t:
            continue
        if len(t) > 48:
            t = t[:45].rstrip() + "…"
        tags.append(t)
    return tags


def _sanitize_plan_memories(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    mems: List[str] = []
    for item in raw[:_MAX_PLAN_MEMORIES_FROM_SUMMARY]:
        if not isinstance(item, str):
            continue
        t = " ".join(item.split())
        if not t:
            continue
        if len(t) > 200:
            t = t[:197].rstrip() + "…"
        mems.append(t)
    return mems


def _build_summarizer_messages(
    *,
    user_message: str,
    assistant_text: str,
    tool_names: List[str],
) -> List[Dict[str, str]]:
    tools_line = ", ".join(tool_names) if tool_names else "(none)"
    schema_hint = (
        '{"summary_text": string, "thread_tags": string[], '
        '"plan_memories": string[]}'
    )
    return [
        {
            "role": "system",
            "content": (
                "You write compact coaching session summaries for a running app. "
                "Output a single JSON object only (no markdown). "
                "Field rules:\n"
                "- summary_text: 2–5 sentences, past tense, curated for the next session. "
                "No quoted chat logs; no email addresses; no phone numbers.\n"
                "- thread_tags: 0–8 short snake_case or lower-case labels describing topics "
                "(e.g. peak_volume, knee_concern, long_run_scheduling).\n"
                "- plan_memories: 0–2 durable **training** preferences or constraints the USER "
                "clearly stated (scheduling, volume limits, long-run day, injuries affecting training). "
                "Omit one-off chat, generic praise, or vague statements under ~24 characters. "
                "Leave empty if none qualify.\n"
                f"Schema: {schema_hint}\n"
                f"session_summary_writer_version: {_SESSION_WRITER_VERSION}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Tools used this turn: {tools_line}\n\n"
                f"User message:\n{user_message[:4000]}\n\n"
                f"Assistant reply:\n{assistant_text[:8000]}\n"
            ),
        },
    ]


def maybe_write_session_summary_after_turn(
    session: Session,
    *,
    internal_user_id: str,
    conversation_id: uuid.UUID,
    user_message: str,
    assistant_reply: Union[str, Dict[str, Any]],
    meta: Optional[Dict[str, Any]],
) -> None:
    if not _writer_enabled():
        return
    try:
        uid = uuid.UUID(str(internal_user_id))
    except (ValueError, TypeError):
        return

    assistant_text = extract_assistant_plain_text(assistant_reply)
    if not user_message.strip() and not assistant_text.strip():
        return

    tool_names = collect_tool_names_from_agent_meta(meta)
    messages = _build_summarizer_messages(
        user_message=user_message,
        assistant_text=assistant_text,
        tool_names=tool_names,
    )

    try:
        svc = get_openai_service()
        resp = svc.chat_completion(
            messages=messages,
            user_id=str(uid),
            model=_summary_model(),
            temperature=0.2,
            max_tokens=500,
            timeout=25.0,
            require_json=True,
        )
    except (RateLimitExceededError, CostLimitExceededError) as exc:
        logger.info("[session_summary_write] skipped (limits): %s", exc)
        return
    except Exception:
        logger.warning("[session_summary_write] OpenAI call failed", exc_info=True)
        return

    try:
        data = json.loads(resp.content or "{}")
    except json.JSONDecodeError:
        logger.warning("[session_summary_write] invalid JSON from model")
        return

    summary_raw = data.get("summary_text") or data.get("summary")
    if not isinstance(summary_raw, str) or not summary_raw.strip():
        return
    summary = " ".join(summary_raw.split())
    if len(summary) > _MAX_SUMMARY_STORE_CHARS:
        summary = summary[: _MAX_SUMMARY_STORE_CHARS - 1].rstrip() + "…"

    tags = _sanitize_tags(data.get("thread_tags"))
    plan_memories = filter_plan_memory_extractions(
        _sanitize_plan_memories(data.get("plan_memories"))
    )

    row = SessionSummary(
        user_id=uid,
        conversation_id=conversation_id,
        summary_text=summary,
        thread_tags=tags,
    )
    session.add(row)
    session.flush()

    for mem in plan_memories:
        append_plan_memory(session, uid, mem, source=MEMORY_SOURCE_SESSION_SUMMARY)

    logger.info(
        "[session_summary_write] stored id=%s user=%s tags=%s extra_memories=%s",
        row.id,
        uid,
        len(tags),
        len(plan_memories),
    )
