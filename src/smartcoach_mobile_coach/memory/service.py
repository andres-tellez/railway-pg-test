"""
Purpose:
- MemoryService facade and baseline read/write orchestration.

Responsibilities:
- Declare service entrypoints for read/write memory operations.
- Centralize dependency injection for repos, policies, renderer, and telemetry.

Non-goals:
- No direct persistence or orchestrator imports.

Guardrails:
- Allowed imports/calls: memory ports + domain types only.
- Must keep concrete logic out until consumer wiring phase.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Mapping, Sequence

from src.smartcoach_mobile_coach.memory.domain.observation import Observation
from src.smartcoach_mobile_coach.memory.domain.scope import Scope
from src.smartcoach_mobile_coach.memory.domain.types import (
    Callback,
    DurableItem,
    InteractionRecord,
    Provenance,
    RecordResult,
    SessionSummaryItem,
)
from src.smartcoach_mobile_coach.memory.domain.view import MemoryView, ViewDiagnostics
from src.smartcoach_mobile_coach.memory.domain.vocab import (
    DurableType,
    InteractionFlag,
    MemoryKind,
    Source,
)
from src.smartcoach_mobile_coach.memory.policies.summarizer import (
    build_summarizer_messages,
    sanitize_summary_payload,
)
from src.smartcoach_mobile_coach.memory.ports import (
    DurableRepo,
    InteractionRepo,
    ObservationClassifier,
    PromptRenderer,
    ProactiveCallbackPolicy,
    StateRepo,
    SummaryRepo,
    SummarizerLLM,
    ThreadRepo,
)
from src.smartcoach_mobile_coach.memory.telemetry import (
    EVENT_MEMORY_RECORD,
    log_memory_event,
)


class MemoryService:
    """Facade for all memory reads/writes (Phase 1 skeleton only)."""

    def __init__(
        self,
        *,
        durable_repo: DurableRepo,
        state_repo: StateRepo,
        thread_repo: ThreadRepo,
        interaction_repo: InteractionRepo,
        summary_repo: SummaryRepo,
        summarizer_llm: SummarizerLLM,
        classifier: ObservationClassifier,
        callback_policy: ProactiveCallbackPolicy,
        prompt_renderer: PromptRenderer,
    ) -> None:
        self._durable_repo = durable_repo
        self._state_repo = state_repo
        self._thread_repo = thread_repo
        self._interaction_repo = interaction_repo
        self._summary_repo = summary_repo
        self._summarizer_llm = summarizer_llm
        self._classifier = classifier
        self._callback_policy = callback_policy
        self._prompt_renderer = prompt_renderer

    def record(self, obs: Observation) -> RecordResult:
        """Persist or dedupe one observation."""
        classified = self._classifier.classify(obs)
        kind = classified.kind
        if kind is None:
            return RecordResult(
                kind=MemoryKind.DURABLE,
                action="rejected",
                reason="missing_kind_after_classification",
            )
        if kind == MemoryKind.DURABLE:
            durable_type = _durable_type_from_hints(classified.hints)
            item = DurableItem(
                id=uuid.uuid4(),
                user_id=classified.user_id,
                text=(classified.text or "").strip(),
                durable_type=durable_type,
                provenance=classified.provenance,
            )
            if not item.text:
                return RecordResult(kind=kind, action="rejected", reason="empty_text")
            saved = self._durable_repo.append(item)
            return RecordResult(kind=kind, action="created", item_id=saved.id)
        if kind == MemoryKind.INTERACTION:
            flag, key, conversation_id = _interaction_from_hints(
                classified, fallback_conversation=classified.provenance.conversation_id
            )
            if flag is None or key is None or conversation_id is None:
                return RecordResult(
                    kind=kind,
                    action="rejected",
                    reason="interaction_missing_flag_key_or_conversation",
                )
            row = self._interaction_repo.record(
                InteractionRecord(
                    id=uuid.uuid4(),
                    user_id=classified.user_id,
                    conversation_id=conversation_id,
                    flag=flag,
                    key=key,
                    captured_at=classified.provenance.captured_at,
                )
            )
            return RecordResult(kind=kind, action="created", item_id=row.id)
        if kind == MemoryKind.SUMMARY:
            summary_text = (classified.text or "").strip()
            if not summary_text:
                return RecordResult(kind=kind, action="rejected", reason="empty_text")
            row = self._summary_repo.append(
                SessionSummaryItem(
                    id=uuid.uuid4(),
                    user_id=classified.user_id,
                    conversation_id=classified.provenance.conversation_id,
                    text=summary_text,
                    tags=tuple(),
                    created_at=classified.provenance.captured_at,
                )
            )
            return RecordResult(kind=kind, action="created", item_id=row.id)
        return RecordResult(
            kind=kind, action="rejected", reason="kind_not_enabled_in_v1"
        )

    def get_view(self, scope: Scope) -> MemoryView:
        """Compose a memory view for prompt injection."""
        durable = tuple(self._durable_repo.list_for_user(scope.user_id))
        state = tuple(self._state_repo.list_active(scope.user_id, scope.now))
        threads_due = tuple(self._thread_repo.list_due(scope.user_id, scope.now))
        interaction = tuple()
        if scope.conversation_id is not None:
            interaction = tuple(
                self._interaction_repo.list_recent(
                    user_id=scope.user_id,
                    conversation_id=scope.conversation_id,
                    since=scope.now - timedelta(days=30),
                )
            )
        summary = (
            self._summary_repo.read_latest(scope.user_id)
            if scope.opening_turn
            else None
        )
        provisional = MemoryView(
            durable=durable,
            state=state,
            threads_due=threads_due,
            interaction=interaction,
            summary=summary,
            diagnostics=ViewDiagnostics(
                schema_version=1,
                built_at=scope.now,
                kinds_included=(
                    MemoryKind.DURABLE,
                    MemoryKind.SUMMARY,
                    MemoryKind.INTERACTION,
                    MemoryKind.STATE,
                    MemoryKind.OPEN_THREAD,
                ),
                kinds_omitted_due_to_flag=tuple(),
                fields_omitted_due_to_budget=tuple(),
                chars_total=0,
                chars_budget=scope.budget_chars,
            ),
        )
        rendered = self.render_prompt_section(provisional)
        return replace(
            provisional,
            diagnostics=replace(
                provisional.diagnostics,
                chars_total=len(rendered),
            ),
        )

    def render_prompt_section(self, view: MemoryView) -> str:
        """Render a memory view into prompt-safe text."""
        try:
            out = self._prompt_renderer.render(view)
            if isinstance(out, str):
                return out
        except Exception:
            pass
        sections: list[str] = []
        if view.summary and view.summary.text.strip():
            sections.append(
                "## PRIOR SESSION SUMMARY\n" f"{view.summary.text.strip()}\n"
            )
        if view.durable:
            lines = ["## DURABLE MEMORY"]
            for item in view.durable[:5]:
                lines.append(f"- ({item.durable_type.value}) {item.text}")
            sections.append("\n".join(lines))
        if view.interaction:
            lines = ["## INTERACTION MEMORY"]
            for item in view.interaction[:5]:
                lines.append(f"- ({item.flag.value}) {item.key}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections).strip()

    def write_session_summary(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message: str,
        assistant_reply: str | dict[str, Any],
        tool_names: Sequence[str],
        timeout_s: float = 25.0,
    ) -> RecordResult:
        """LLM-summarize one turn and persist summary + durable memory candidates."""
        assistant_text = _assistant_plain_text(assistant_reply)
        if not (user_message or "").strip() and not assistant_text.strip():
            return RecordResult(
                kind=MemoryKind.SUMMARY,
                action="rejected",
                reason="empty_turn",
            )

        messages = build_summarizer_messages(
            user_message=(user_message or "").strip(),
            assistant_text=assistant_text,
            tool_names=tool_names,
        )
        try:
            llm_out = self._summarizer_llm.summarize(
                user_id=user_id,
                turns=messages,
                timeout_s=timeout_s,
            )
        except Exception:
            log_memory_event(
                EVENT_MEMORY_RECORD,
                {
                    "kind": MemoryKind.SUMMARY.value,
                    "action": "rejected",
                    "reason": "llm_failure",
                },
            )
            return RecordResult(
                kind=MemoryKind.SUMMARY,
                action="rejected",
                reason="llm_failure",
            )

        draft = sanitize_summary_payload(_mapping_str(llm_out, "content"))
        if draft is None:
            log_memory_event(
                EVENT_MEMORY_RECORD,
                {
                    "kind": MemoryKind.SUMMARY.value,
                    "action": "rejected",
                    "reason": "invalid_summary_payload",
                },
            )
            return RecordResult(
                kind=MemoryKind.SUMMARY,
                action="rejected",
                reason="invalid_summary_payload",
            )

        now_utc = datetime.now(timezone.utc)
        summary_row = self._summary_repo.append(
            SessionSummaryItem(
                id=uuid.uuid4(),
                user_id=user_id,
                conversation_id=conversation_id,
                text=draft.summary_text,
                tags=draft.thread_tags,
                created_at=now_utc,
            )
        )
        for memory_text in draft.plan_memories:
            self._durable_repo.append(
                DurableItem(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    text=memory_text,
                    durable_type=DurableType.OTHER,
                    provenance=Provenance(
                        source=Source.SUMMARIZER,
                        conversation_id=conversation_id,
                        captured_at=now_utc,
                    ),
                )
            )

        log_memory_event(
            EVENT_MEMORY_RECORD,
            {
                "kind": MemoryKind.SUMMARY.value,
                "action": "created",
                "item_id": str(summary_row.id),
                "plan_memories_extracted": len(draft.plan_memories),
                "model": _mapping_str(llm_out, "model"),
                "cost": _mapping_float(llm_out, "cost"),
            },
        )
        return RecordResult(
            kind=MemoryKind.SUMMARY,
            action="created",
            item_id=summary_row.id,
        )

    def proactive_callbacks(self, view: MemoryView) -> list[Callback]:
        """Return optional proactive callback hints."""
        try:
            return list(self._callback_policy.choose(view=view, budget=1))
        except Exception:
            return []

    def mark_interaction(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        flag: InteractionFlag,
        key: str,
        captured_at: datetime | None = None,
    ) -> RecordResult:
        """Idempotently record an interaction marker."""
        row = self._interaction_repo.record(
            InteractionRecord(
                id=uuid.uuid4(),
                user_id=user_id,
                conversation_id=conversation_id,
                flag=flag,
                key=str(key).strip(),
                captured_at=captured_at or datetime.now(timezone.utc),
            )
        )
        return RecordResult(
            kind=MemoryKind.INTERACTION, action="created", item_id=row.id
        )

    def has_interaction(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        flag: InteractionFlag,
        key: str,
        window_days: int = 30,
    ) -> bool:
        """True when a matching interaction marker exists in the window."""
        since = datetime.now(timezone.utc) - timedelta(days=max(1, int(window_days)))
        rows = self._interaction_repo.list_recent(
            user_id=user_id,
            conversation_id=conversation_id,
            since=since,
        )
        target_key = str(key).strip()
        for row in rows:
            if row.flag == flag and row.key == target_key:
                return True
        return False


def _durable_type_from_hints(hints: dict[str, object]) -> DurableType:
    raw = hints.get("durable_type")
    if isinstance(raw, str):
        val = raw.strip().lower()
        if val in (
            "goal",
            "constraint",
            "preference",
            "training_days",
            "long_run_day",
            "other",
        ):
            return DurableType(val)
    return DurableType.OTHER


def _interaction_from_hints(
    obs: Observation, *, fallback_conversation
) -> tuple[InteractionFlag | None, str | None, uuid.UUID | None]:
    hints = obs.hints
    flag_raw = hints.get("interaction_flag")
    key_raw = hints.get("interaction_key")
    conv_raw = hints.get("conversation_id")

    flag = None
    if isinstance(flag_raw, str):
        try:
            flag = InteractionFlag(flag_raw)
        except ValueError:
            flag = None
    key = str(key_raw).strip() if key_raw is not None else None
    if key == "":
        key = None
    conversation_id = None
    if isinstance(conv_raw, str):
        try:
            conversation_id = uuid.UUID(conv_raw)
        except ValueError:
            conversation_id = None
    elif isinstance(conv_raw, uuid.UUID):
        conversation_id = conv_raw
    elif isinstance(fallback_conversation, uuid.UUID):
        conversation_id = fallback_conversation
    return flag, key, conversation_id


def _assistant_plain_text(assistant_reply: str | dict[str, Any]) -> str:
    if isinstance(assistant_reply, str):
        return assistant_reply.strip()
    if not isinstance(assistant_reply, dict):
        return ""
    raw = assistant_reply.get("content")
    if isinstance(raw, str):
        return raw.strip()
    return ""


def _mapping_str(raw: Mapping[str, Any] | None, key: str) -> str:
    if not isinstance(raw, Mapping):
        return ""
    value = raw.get(key)
    return value if isinstance(value, str) else ""


def _mapping_float(raw: Mapping[str, Any] | None, key: str) -> float | None:
    if not isinstance(raw, Mapping):
        return None
    value = raw.get(key)
    if isinstance(value, (float, int)):
        return float(value)
    return None
