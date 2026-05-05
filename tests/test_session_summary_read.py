"""
V1.6 Phase C 3C.10–3C.14 — session summary read path tests.

Covers every branch of the read-path contract:

* **3C.10** reader + injection on first-ever opening turn.
* **3C.11** privacy cap — the reader only queries
  ``session_summaries``; it never touches raw
  ``conversation_messages``, which is the structural guarantee
  behind "curated summary only, no raw messages".
* **3C.12** prompt-section labeling + do-not-invent instruction +
  §19.1 cross-reference + versioning anchor.
* **3C.13** graceful no-op when no summary exists (table missing,
  no rows, empty text, non-string, or user_id missing).
* **3C.14** this is the read path only — the reader never attempts
  to write a summary (enforced by the fact that the module never
  imports an INSERT / UPDATE / DELETE helper; surfaced explicitly
  as a docstring assertion).
* Orchestrator wiring: gated on opening + no prior assistant
  message + not plan-creation, suppressed otherwise, placed after
  :func:`coach_tone_contract_section`, and silently dropped by
  :func:`_join_nonempty_system_sections` when empty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from src.smartcoach_mobile_coach import session_summary_read
from src.smartcoach_mobile_coach.session_summary_read import (
    SESSION_SUMMARY_READER_VERSION,
    has_prior_assistant_message,
    read_most_recent_session_summary,
    session_summary_section,
)


# ---------------------------------------------------------------------------
# Module surface & version
# ---------------------------------------------------------------------------


def test_reader_version_is_int_and_v1() -> None:
    assert isinstance(SESSION_SUMMARY_READER_VERSION, int)
    assert SESSION_SUMMARY_READER_VERSION == 1


def test_module_surface_exports_expected_names() -> None:
    for name in (
        "SESSION_SUMMARY_READER_VERSION",
        "read_most_recent_session_summary",
        "session_summary_section",
        "has_prior_assistant_message",
    ):
        assert hasattr(
            session_summary_read, name
        ), f"public API symbol {name!r} disappeared"


def test_read_path_module_does_not_perform_writes() -> None:
    """3C.14 structural anchor — this module is read-only.

    The writer (Layer B) is Phase F work. The read module must
    never contain INSERT / UPDATE / DELETE / MERGE / UPSERT calls.
    We assert this textually so an accidental write-helper addition
    fails the contract tests loudly.
    """
    src = Path("src/smartcoach_mobile_coach/session_summary_read.py").read_text(
        encoding="utf-8"
    )
    # Guard against accidental write statements. We match on SQL
    # verb boundaries to avoid tripping on the word "insert" inside
    # prose.
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "UPSERT", "MERGE INTO"):
        assert verb not in src.upper(), (
            f"session_summary_read.py contains a write statement ({verb!r}); "
            "writer is Phase F — keep this module read-only"
        )


# ---------------------------------------------------------------------------
# read_most_recent_session_summary — reader behavior
# ---------------------------------------------------------------------------


def _mock_session_returning(row: Optional[Dict[str, Any]] | Exception) -> MagicMock:
    """Build a MagicMock SQLAlchemy session whose execute returns ``row``.

    ``row`` as ``None`` = no rows; as ``Exception`` = query raises.
    """
    session = MagicMock()
    if isinstance(row, Exception):
        session.execute.side_effect = row
        return session
    mappings = MagicMock()
    mappings.first.return_value = row
    result = MagicMock()
    result.mappings.return_value = mappings
    session.execute.return_value = result
    return session


def test_reader_returns_text_when_row_exists() -> None:
    session = _mock_session_returning(
        {"summary_text": "We discussed the taper plan and targeted 8:30/mi."}
    )
    out = read_most_recent_session_summary(session, "user-1")
    assert out == "We discussed the taper plan and targeted 8:30/mi."


def test_reader_returns_none_when_no_rows() -> None:
    session = _mock_session_returning(None)
    assert read_most_recent_session_summary(session, "user-1") is None


def test_reader_returns_none_when_table_missing_or_query_raises() -> None:
    # This is the V1.6 state — session_summaries table has not been
    # created by Phase F yet. The reader must degrade silently, not
    # bubble up a DB error that would break a turn.
    session = _mock_session_returning(RuntimeError("relation does not exist"))
    assert read_most_recent_session_summary(session, "user-1") is None
    # Swallowed SQL errors must not leave Postgres in
    # InFailedSqlTransaction — the shared request session needs a
    # rollback before any later query (e.g. user_profile).
    session.rollback.assert_called_once()


def test_reader_returns_none_when_summary_text_is_empty_or_whitespace() -> None:
    for payload in ("", "   ", "\n\t"):
        session = _mock_session_returning({"summary_text": payload})
        assert read_most_recent_session_summary(session, "user-1") is None


def test_reader_returns_none_when_summary_text_is_non_string() -> None:
    session = _mock_session_returning({"summary_text": 42})
    assert read_most_recent_session_summary(session, "user-1") is None


def test_reader_returns_none_when_user_id_missing() -> None:
    session = MagicMock()
    assert read_most_recent_session_summary(session, "") is None
    # Importantly, no DB call was made — structural guarantee that
    # anonymous/unknown users can't leak another user's summary.
    assert session.execute.called is False


def test_reader_truncates_overlong_summaries_with_ellipsis_and_preserves_words() -> (
    None
):
    # The V1.6 spec caps summary injection at ≤ 500 tokens. The
    # reader applies a defensive char cap (~2000 chars) so a
    # runaway summary row can't bloat every opening-turn prompt.
    long_summary = ("word " * 1000).strip()  # ~5000 chars
    session = _mock_session_returning({"summary_text": long_summary})
    out = read_most_recent_session_summary(session, "user-1")
    assert out is not None
    assert out.endswith(" …")
    assert len(out) <= 2100  # 2000 + small ellipsis margin
    # Word boundary check — the truncated tail should not end with
    # a partial word right before the ellipsis.
    pre_ellipsis = out[:-2].rstrip()
    assert not pre_ellipsis.endswith(
        "wor"
    ), "truncation cut mid-word; word-boundary guard regressed"


def test_reader_queries_only_session_summaries_table_3c11_privacy() -> None:
    """3C.11 — structural privacy guarantee.

    The reader must only query ``session_summaries``. It must never
    touch ``conversation_messages`` (raw messages) or any other
    table that holds un-curated user content. This test asserts
    the property textually.
    """
    src_lower = (
        Path("src/smartcoach_mobile_coach/session_summary_read.py")
        .read_text(encoding="utf-8")
        .lower()
    )
    assert "from session_summaries" in src_lower
    # The real privacy violation would be reading raw messages. The
    # module must never reference conversation_messages (the raw
    # message store) — curated summaries only.
    assert "conversation_messages" not in src_lower
    # Re-verify the helper name does appear (in has_prior_assistant_message).
    src_raw = Path("src/smartcoach_mobile_coach/session_summary_read.py").read_text(
        encoding="utf-8"
    )
    assert "def has_prior_assistant_message(" in src_raw


# ---------------------------------------------------------------------------
# session_summary_section — prompt formatting
# ---------------------------------------------------------------------------


def test_section_is_empty_when_summary_is_none_or_blank() -> None:
    # _join_nonempty_system_sections drops empty sections, so this
    # is the "no inject" code path for 3C.13.
    assert session_summary_section(None) == ""
    assert session_summary_section("") == ""
    assert session_summary_section("   ") == ""


def test_section_uses_canonical_prior_session_summary_header_3c12() -> None:
    out = session_summary_section("We talked about taper.")
    # 3C.12 locks the exact label so evals / logs can grep reliably.
    assert "## PRIOR SESSION SUMMARY" in out


def test_section_carries_versioning_anchor() -> None:
    out = session_summary_section("We talked about taper.")
    assert (
        f"<!-- session_summary_reader_version: {SESSION_SUMMARY_READER_VERSION} -->"
        in out
    )


def test_section_contains_do_not_invent_instruction_and_19_1_anchor_3c12() -> None:
    # 3C.12 — the coach must not invent details beyond the summary.
    # We lock the anti-invention instruction AND the §19.1 cross-ref
    # so a future edit can't quietly drop the guardrail.
    out = session_summary_section("We talked about taper.")
    assert "Do not invent" in out
    assert "§19.1" in out


def test_section_contains_summary_body_verbatim() -> None:
    body = "We discussed Tuesday's Tempo and you committed to Z3 on the main block."
    out = session_summary_section(body)
    assert body in out


def test_section_prefers_current_payload_over_summary_when_they_disagree() -> None:
    # Stale summaries must not outrank fresh tool output. This is
    # the resolution rule when the summary and the current turn's
    # data drift — keep the coach anchored in reality.
    out = session_summary_section("Last week you skipped Tuesday's Tempo.")
    assert "Prefer the current turn's tool payloads" in out


def test_section_is_labeled_as_reference_not_ground_truth() -> None:
    out = session_summary_section("Anything.")
    assert "**reference**" in out
    assert "not ground truth" in out


# ---------------------------------------------------------------------------
# has_prior_assistant_message — opening-turn gate
# ---------------------------------------------------------------------------


def test_prior_assistant_detector_false_on_empty_history() -> None:
    assert has_prior_assistant_message([]) is False


def test_prior_assistant_detector_false_when_only_user_messages() -> None:
    history = [{"role": "user", "content": "hi"}]
    assert has_prior_assistant_message(history) is False


def test_prior_assistant_detector_true_when_any_assistant_message_exists() -> None:
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hey, let's dig in."},
    ]
    assert has_prior_assistant_message(history) is True


def test_prior_assistant_detector_ignores_blank_assistant_content() -> None:
    # An empty/whitespace assistant message should not count — it's
    # a rendering artifact, not a real prior turn.
    history = [
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "   "},
    ]
    assert has_prior_assistant_message(history) is False


def test_prior_assistant_detector_handles_malformed_input_defensively() -> None:
    # Injection is missing-context-preferred: if history is malformed,
    # treat as "no prior assistant" so we don't accidentally suppress
    # a summary on a brand-new thread.
    assert has_prior_assistant_message(None) is False
    assert has_prior_assistant_message("not a list") is False
    assert has_prior_assistant_message([None, 42, "str"]) is False


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_orchestrator_imports_session_summary_readers() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "read_most_recent_session_summary")
    assert hasattr(orchestrator, "session_summary_section")
    assert hasattr(orchestrator, "has_prior_assistant_message")
    assert (
        orchestrator.read_most_recent_session_summary
        is read_most_recent_session_summary
    )


def test_orchestrator_defines_gating_injector_helper() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "_prior_session_summary_section"), (
        "orchestrator must expose _prior_session_summary_section so the gating "
        "logic is testable independently of full turn execution"
    )


def test_orchestrator_source_wires_summary_after_tone_contract() -> None:
    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    # Wired exactly once as a call (count == 2: 1 def + 1 call), and
    # after coach_tone_contract_section so it reads as a natural
    # continuation of the V1.6 coach contract.
    name_hits = src.count("_prior_session_summary_section(")
    def_hits = src.count("def _prior_session_summary_section(")
    assert (
        def_hits == 1
    ), "_prior_session_summary_section should be defined exactly once"
    assert name_hits - def_hits == 1, (
        "_prior_session_summary_section should be called exactly once from the "
        "system-prompt composition"
    )
    # Anchor on the composition call site (with leading newline in
    # the arg list) rather than the def (which appears earlier in
    # the file).
    tone_idx = src.index("coach_tone_contract_section(),")
    prose_idx = src.index("coach_turn_prose_shape_section(),")
    summary_idx = src.index("_prior_session_summary_section(\n                session,")
    assert tone_idx < prose_idx < summary_idx, (
        "system prompt order: coach_tone_contract_section, then "
        "coach_turn_prose_shape_section, then _prior_session_summary_section"
    )


def test_orchestrator_source_does_not_wire_summary_into_plan_creation_branch() -> None:
    # Plan-creation turns already have their own restricted prompt
    # and do not benefit from cross-session summary context.
    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    plan_creation_base_idx = src.index("PLAN_CREATION_SYSTEM_PROMPT_BASE")
    summary_idx = src.index("_prior_session_summary_section(")
    assert (
        plan_creation_base_idx < summary_idx
    ), "_prior_session_summary_section() must be wired in the non-plan-creation branch"


# ---------------------------------------------------------------------------
# _prior_session_summary_section — gating logic (independent of turn run)
# ---------------------------------------------------------------------------


class _FakeDirective:
    def __init__(self, turn_type: str) -> None:
        self.turn_type = turn_type


def _fake_session_with_summary(summary: Optional[str]) -> MagicMock:
    row = None if summary is None else {"summary_text": summary}
    return _mock_session_returning(row)


def test_injector_returns_block_on_opening_with_no_prior_assistant() -> None:
    from src.smartcoach_mobile_coach.orchestrator import (
        _prior_session_summary_section,
    )

    block = _prior_session_summary_section(
        _fake_session_with_summary("We talked about your Long Run progression."),
        "user-1",
        [{"role": "user", "content": "hi"}],
        _FakeDirective("opening"),
        plan_creation_mode=False,
    )
    assert "## PRIOR SESSION SUMMARY" in block
    assert "Long Run progression" in block


def test_injector_returns_empty_when_turn_type_is_not_opening() -> None:
    from src.smartcoach_mobile_coach.orchestrator import (
        _prior_session_summary_section,
    )

    assert (
        _prior_session_summary_section(
            _fake_session_with_summary("Summary body"),
            "user-1",
            [],
            _FakeDirective("follow_up"),
            plan_creation_mode=False,
        )
        == ""
    )


def test_injector_returns_empty_when_prior_assistant_message_exists() -> None:
    # Opening-classified topic reset INSIDE an existing thread — the
    # recent messages already provide continuity, so the summary is
    # redundant (and would confuse the coach by overlapping with
    # live history).
    from src.smartcoach_mobile_coach.orchestrator import (
        _prior_session_summary_section,
    )

    history: List[Dict[str, str]] = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello again."},
        {"role": "user", "content": "new question"},
    ]
    assert (
        _prior_session_summary_section(
            _fake_session_with_summary("Summary body"),
            "user-1",
            history,
            _FakeDirective("opening"),
            plan_creation_mode=False,
        )
        == ""
    )


def test_injector_returns_empty_in_plan_creation_mode() -> None:
    from src.smartcoach_mobile_coach.orchestrator import (
        _prior_session_summary_section,
    )

    assert (
        _prior_session_summary_section(
            _fake_session_with_summary("Summary body"),
            "user-1",
            [],
            _FakeDirective("opening"),
            plan_creation_mode=True,
        )
        == ""
    )


def test_injector_returns_empty_when_no_summary_exists_3c13() -> None:
    # 3C.13 — brand-new user with no prior summary → no injection.
    # Coach starts fresh, no artifacts in the prompt.
    from src.smartcoach_mobile_coach.orchestrator import (
        _prior_session_summary_section,
    )

    assert (
        _prior_session_summary_section(
            _fake_session_with_summary(None),
            "user-1",
            [],
            _FakeDirective("opening"),
            plan_creation_mode=False,
        )
        == ""
    )


def test_injector_returns_empty_when_user_id_is_missing() -> None:
    # Defensive — anonymous / unknown turns cannot leak another
    # user's summary.
    from src.smartcoach_mobile_coach.orchestrator import (
        _prior_session_summary_section,
    )

    session = _fake_session_with_summary("Anything")
    assert (
        _prior_session_summary_section(
            session,
            "",
            [],
            _FakeDirective("opening"),
            plan_creation_mode=False,
        )
        == ""
    )
    # The gating must short-circuit BEFORE hitting the DB.
    assert session.execute.called is False


@pytest.mark.parametrize(
    "turn_type,history,plan_creation,expect_inject",
    [
        ("opening", [], False, True),
        ("opening", [{"role": "user", "content": "hi"}], False, True),
        (
            "opening",
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hey"},
            ],
            False,
            False,
        ),
        ("follow_up", [], False, False),
        ("drill_down", [], False, False),
        ("new_topic", [], False, False),
        ("opening", [], True, False),
    ],
)
def test_injector_gating_matrix(
    turn_type: str,
    history: List[Dict[str, str]],
    plan_creation: bool,
    expect_inject: bool,
) -> None:
    # End-to-end gating contract in one table. Any change to the
    # gates shows up here immediately.
    from src.smartcoach_mobile_coach.orchestrator import (
        _prior_session_summary_section,
    )

    block = _prior_session_summary_section(
        _fake_session_with_summary("SUMMARY_BODY"),
        "user-1",
        history,
        _FakeDirective(turn_type),
        plan_creation_mode=plan_creation,
    )
    injected = bool(block)
    assert injected is expect_inject, (
        f"gating failed for turn_type={turn_type!r} "
        f"history_len={len(history)} plan_creation={plan_creation}; "
        f"expected inject={expect_inject} got inject={injected}"
    )
