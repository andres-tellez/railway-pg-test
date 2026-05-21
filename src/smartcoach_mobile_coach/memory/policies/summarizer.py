"""
Summary-writing policy helpers for Memory v2.

Pure helpers only:
- Build summarizer prompts.
- Parse/sanitize summarizer output.
- Extract durable-memory candidates from summary payloads.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

_SESSION_WRITER_VERSION = 1
_MAX_SUMMARY_STORE_CHARS = 2000
_MAX_TAGS = 12
_MAX_PLAN_MEMORIES_FROM_SUMMARY = 2
_MIN_EXTRACTED_MEMORY_LEN = 24
_ELLIPSIS = "..."

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


@dataclass(frozen=True)
class SummaryDraft:
    summary_text: str
    thread_tags: tuple[str, ...]
    plan_memories: tuple[str, ...]


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


def filter_plan_memory_extractions(candidates: Sequence[str]) -> list[str]:
    out: list[str] = []
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        s = " ".join(raw.split())
        if not worth_persisting_extracted_plan_memory(s):
            continue
        out.append(s)
    return out[:_MAX_PLAN_MEMORIES_FROM_SUMMARY]


def extract_assistant_plain_text(assistant_reply: Union[str, Dict[str, Any]]) -> str:
    if isinstance(assistant_reply, str):
        return assistant_reply.strip()
    if not isinstance(assistant_reply, dict):
        return ""
    inner = assistant_reply.get("content")
    if isinstance(inner, str) and inner.strip():
        return inner.strip()
    return ""


def collect_tool_names_from_agent_meta(meta: Optional[Mapping[str, Any]]) -> list[str]:
    if not isinstance(meta, Mapping):
        return []
    timings = meta.get("timings_ms")
    if not isinstance(timings, Mapping):
        return []
    loops = timings.get("agent_loop_rounds")
    if not isinstance(loops, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for loop in loops:
        if not isinstance(loop, Mapping):
            continue
        tools = loop.get("tools")
        if not isinstance(tools, list):
            continue
        for entry in tools:
            if not isinstance(entry, Mapping):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            n = name.strip()
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out


def build_summarizer_messages(
    *,
    user_message: str,
    assistant_text: str,
    tool_names: Sequence[str],
) -> list[dict[str, str]]:
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
                "- summary_text: 2-5 sentences, past tense, curated for the next session. "
                "No quoted chat logs; no email addresses; no phone numbers.\n"
                "- thread_tags: 0-8 short snake_case or lower-case labels describing topics "
                "(e.g. peak_volume, knee_concern, long_run_scheduling).\n"
                "- plan_memories: 0-2 durable training preferences or constraints the USER "
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
                f"User message:\n{(user_message or '')[:4000]}\n\n"
                f"Assistant reply:\n{(assistant_text or '')[:8000]}\n"
            ),
        },
    ]


def sanitize_summary_payload(raw_json_str: str) -> SummaryDraft | None:
    try:
        data = json.loads(raw_json_str or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    summary_raw = data.get("summary_text") or data.get("summary")
    if not isinstance(summary_raw, str) or not summary_raw.strip():
        return None
    summary = " ".join(summary_raw.split())
    if len(summary) > _MAX_SUMMARY_STORE_CHARS:
        summary = _truncate(summary, _MAX_SUMMARY_STORE_CHARS)

    tags = _sanitize_tags(data.get("thread_tags"))
    plan_memories = filter_plan_memory_extractions(
        _sanitize_plan_memories(data.get("plan_memories"))
    )
    return SummaryDraft(
        summary_text=summary,
        thread_tags=tuple(tags),
        plan_memories=tuple(plan_memories),
    )


def _sanitize_tags(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    tags: list[str] = []
    for item in raw[:_MAX_TAGS]:
        if not isinstance(item, str):
            continue
        t = re.sub(r"[^\w\- ]+", "", item, flags=re.UNICODE).strip()
        if not t:
            continue
        if len(t) > 48:
            t = _truncate(t, 48)
        tags.append(t)
    return tags


def _sanitize_plan_memories(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    mems: list[str] = []
    for item in raw[:_MAX_PLAN_MEMORIES_FROM_SUMMARY]:
        if not isinstance(item, str):
            continue
        t = " ".join(item.split())
        if not t:
            continue
        if len(t) > 200:
            t = _truncate(t, 200)
        mems.append(t)
    return mems


def _truncate(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= len(_ELLIPSIS):
        return text[:limit]
    return text[: limit - len(_ELLIPSIS)].rstrip() + _ELLIPSIS
