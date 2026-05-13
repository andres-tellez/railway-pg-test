"""
HTTP API for SmartCoach mobile Coach tab — agent tool loop only.

POST /api/conversations/<conversation_id>/agent-messages
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from flask import Blueprint, jsonify, request

from src.db.db_session import get_session
from src.db.models.conversations import Conversation, ConversationMessage
from src.db.models.user_athletes import UserAthleteLink
from src.routes.conversation_routes import get_user_from_auth
from src.services.security.external_apis.openai_service import (
    CostLimitExceededError,
    RateLimitExceededError,
)
from src.smartcoach_mobile_coach.config import SMARTCOACH_MOBILE_AGENT_ENABLED
from src.smartcoach_mobile_coach.http_rate_limit import (
    can_make_agent_http_request,
    record_agent_http_request,
)
from src.smartcoach_mobile_coach.orchestrator import run_mobile_agent_turn
from src.smartcoach_mobile_coach.agent_tools import tool_update_plan_intake
from src.smartcoach_mobile_coach.plan_intake_flow import (
    structured_intake_core_v1_enabled,
)
from src.smartcoach_mobile_coach.thread_derived_context import (
    DerivedThreadCoachContext,
    derive_thread_coach_context,
)
from src.utils.date_helpers import DAY_NAMES_ABBREV
from src.services.coach_strava_readiness_service import (
    evaluate_coach_strava_data_readiness,
)
from src.utils.response_utils import error_response

logger = logging.getLogger("smartcoach_mobile_coach")

_EVAL_MODEL_ALLOWLIST = frozenset(
    {"gpt-4o", "gpt-4o-mini", "gpt-4o-2024-08-06"},
)


def _eval_model_override_enabled() -> bool:
    v = (os.getenv("SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _eval_request_secret_configured() -> str:
    """Shared secret for scripted eval (optional alternative to override flag)."""
    return (os.getenv("SMARTCOACH_COACH_EVAL_REQUEST_SECRET") or "").strip()


def _eval_request_secret_matches() -> bool:
    """True when client sent X-SmartCoach-Eval-Secret matching SMARTCOACH_COACH_EVAL_REQUEST_SECRET."""
    secret = _eval_request_secret_configured()
    if not secret:
        return False  # never treat empty server secret as valid
    hdr = (request.headers.get("X-SmartCoach-Eval-Secret") or "").strip()
    if len(hdr) != len(secret):
        return False
    return hmac.compare_digest(hdr, secret)


def _eval_headers_allowed() -> bool:
    """
    Allow X-SmartCoach-Eval-Model when either:
    - SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE is on, or
    - SMARTCOACH_COACH_EVAL_REQUEST_SECRET is set on the server and the request
      includes matching X-SmartCoach-Eval-Secret (for local/staging eval scripts).
    """
    return _eval_model_override_enabled() or _eval_request_secret_matches()


def _coerce_eval_model_header() -> Optional[str]:
    """Honor X-SmartCoach-Eval-Model when eval headers are allowed (override or secret)."""
    if not _eval_headers_allowed():
        return None
    raw = request.headers.get("X-SmartCoach-Eval-Model")
    if not raw or not isinstance(raw, str):
        return None
    name = raw.strip()
    if name in _EVAL_MODEL_ALLOWLIST:
        return name
    logger.warning(
        "[smartcoach_mobile_coach] ignored X-SmartCoach-Eval-Model=%r (not in allowlist)",
        name[:80],
    )
    return None


def _log_agent_messages_response_audit(gpt_response: Any) -> None:
    """
    Temporary Phase 1 validation: outbound assistant payload summary only (no PII).
    WARNING so it stays visible if Railway suppresses INFO.
    """
    if not isinstance(gpt_response, dict):
        logger.warning(
            "[agent_messages_response] response_type=%s has_data=0 has_sections=0 "
            "content_len=0 sections_fields_present= grounding_count=0 has_close=0",
            type(gpt_response).__name__,
        )
        return

    rtype = str(gpt_response.get("type") or "").strip() or "unknown"
    has_data = 1 if gpt_response.get("data") is not None else 0
    sections = gpt_response.get("sections")
    has_sections = 1 if isinstance(sections, dict) else 0
    raw_content = gpt_response.get("content")
    content_len = len(raw_content) if isinstance(raw_content, str) else 0

    fields_present: list[str] = []
    grounding_count = 0
    has_close = 0
    if isinstance(sections, dict):
        if str(sections.get("interpretation") or "").strip():
            fields_present.append("interpretation")
        grounding = sections.get("grounding") or []
        grounding_count = sum(1 for g in grounding if isinstance(g, str) and g.strip())
        if grounding_count:
            fields_present.append("grounding")
        close_raw = sections.get("close")
        has_close = 1 if isinstance(close_raw, str) and close_raw.strip() else 0
        if has_close:
            fields_present.append("close")
        nudge_raw = sections.get("nudge")
        if isinstance(nudge_raw, str) and nudge_raw.strip():
            fields_present.append("nudge")

    logger.warning(
        "[agent_messages_response] response_type=%s has_data=%s has_sections=%s "
        "content_len=%s sections_fields_present=%s grounding_count=%s has_close=%s",
        rtype,
        has_data,
        has_sections,
        content_len,
        ",".join(fields_present),
        grounding_count,
        has_close,
    )


def _llm_plain_text_from_stored_message(role: str, content: str) -> str:
    """
    Assistant rows may store JSON for structured mobile payloads; the agent only sees plain insight text.
    """
    if role != "assistant" or not content:
        return content
    stripped = content.strip()
    if not stripped.startswith("{"):
        return content
    try:
        obj: Any = json.loads(stripped)
    except json.JSONDecodeError:
        return content
    if isinstance(obj, dict):
        inner = obj.get("content")
        if isinstance(inner, str):
            return inner
    return content


def _resolve_anchor_local_date(payload: dict) -> Tuple[str, Optional[str]]:
    """
    Prefer client_local_date / clientLocalDate (YYYY-MM-DD) from the mobile app.
    Fall back to UTC calendar date if missing or invalid (logged).
    Returns (anchor_date_str, timezone_str_or_none).
    """
    raw = payload.get("client_local_date")
    if raw is None:
        raw = payload.get("clientLocalDate")
    tz_raw = payload.get("client_timezone")
    if tz_raw is None:
        tz_raw = payload.get("clientTimezone")

    tz = None
    if isinstance(tz_raw, str) and tz_raw.strip():
        tz = tz_raw.strip()[:120]

    if isinstance(raw, str) and raw.strip():
        candidate = raw.strip()
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
            return candidate, tz
        except ValueError:
            logger.warning(
                "[smartcoach_mobile_coach] invalid client_local_date=%r; using UTC fallback",
                candidate[:48],
            )

    anchor = datetime.now(timezone.utc).date().isoformat()
    logger.info(
        "[smartcoach_mobile_coach] missing client_local_date; using UTC date fallback %s",
        anchor,
    )
    return anchor, tz


def _coerce_last_activity_id(payload: dict) -> Optional[int]:
    """
    Optional fastpath hint from client.

    Accepts `last_activity_id` or `lastActivityId` as a positive integer.
    """
    raw = payload.get("last_activity_id")
    if raw is None:
        raw = payload.get("lastActivityId")
    if raw is None:
        return None
    try:
        aid = int(raw)
    except (TypeError, ValueError):
        return None
    return aid if aid > 0 else None


def _coerce_readiness_trace_id(payload: dict) -> Optional[str]:
    raw = payload.get("readiness_trace_id")
    if raw is None:
        raw = payload.get("readinessTraceId")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:200]
    return None


def _coerce_require_fresh_strava_data(payload: dict) -> bool:
    """True when client asks to gate until Strava coach-data-ready."""
    raw = payload.get("require_fresh_strava_data")
    if raw is None:
        raw = payload.get("requireFreshStravaData")
    if raw is True:
        return True
    if isinstance(raw, str) and raw.strip().lower() in ("true", "1", "yes"):
        return True
    return False


_VALID_STRUCTURED_PRIMARY_GOALS = frozenset({"Just Finish", "Target Time"})

_VALID_STRUCTURED_RUNNER_TRADEOFF_CHOICES = frozenset(
    {
        "expand_running_days",
        "continue_tradeoff",
        "adjust_goal",
        "adjust_timeline",
        "build_base_first",
    }
)


def _coerce_structured_intake_updates(payload: dict) -> Optional[dict]:
    raw = payload.get("structured_input")
    if not isinstance(raw, dict):
        return None
    if str(raw.get("kind") or "").strip() != "update_plan_intake":
        return None
    updates = raw.get("updates")
    if not isinstance(updates, dict):
        return None
    out: dict = {}
    if "alignment_frequency_flexible" in updates:
        v = updates.get("alignment_frequency_flexible")
        if isinstance(v, bool):
            out["alignment_frequency_flexible"] = v
    if "alignment_posture_priority" in updates:
        v = updates.get("alignment_posture_priority")
        if isinstance(v, str) and v.strip().lower() in (
            "performance",
            "balanced",
            "durability",
        ):
            out["alignment_posture_priority"] = v.strip().lower()

    _apply_suggested = (
        isinstance(updates, dict) and updates.get("apply_coach_suggested_goal") is True
    )
    if structured_intake_core_v1_enabled() or _apply_suggested:
        if "race_distance" in updates:
            v = updates.get("race_distance")
            if isinstance(v, str) and v.strip():
                out["race_distance"] = v.strip()
        if "race_date" in updates:
            v = updates.get("race_date")
            if isinstance(v, str) and v.strip():
                out["race_date"] = v.strip()
        if "primary_goal" in updates:
            v = updates.get("primary_goal")
            if isinstance(v, str) and v.strip() in _VALID_STRUCTURED_PRIMARY_GOALS:
                out["primary_goal"] = v.strip()
        if "target_time" in updates:
            v = updates.get("target_time")
            if v is None:
                out["target_time"] = None
            elif isinstance(v, str) and v.strip():
                out["target_time"] = v.strip()
        if "training_days" in updates:
            v = updates.get("training_days")
            if isinstance(v, list):
                days: list[str] = []
                for x in v:
                    if isinstance(x, str) and x in DAY_NAMES_ABBREV:
                        days.append(x)
                if days:
                    seen: set[str] = set()
                    uniq: list[str] = []
                    for d in days:
                        if d not in seen:
                            seen.add(d)
                            uniq.append(d)
                    out["training_days"] = uniq
        if "long_run_day" in updates:
            v = updates.get("long_run_day")
            if isinstance(v, str) and v.strip() in DAY_NAMES_ABBREV:
                out["long_run_day"] = v.strip()

    if "schedule_days_confirmed" in updates:
        v = updates.get("schedule_days_confirmed")
        if isinstance(v, bool):
            out["schedule_days_confirmed"] = v

    if "runner_tradeoff_choice" in updates:
        v = updates.get("runner_tradeoff_choice")
        if isinstance(v, str):
            choice = v.strip().lower()
            if choice in _VALID_STRUCTURED_RUNNER_TRADEOFF_CHOICES:
                out["runner_tradeoff_choice"] = choice

    if "plan_generation_confirmed" in updates:
        v = updates.get("plan_generation_confirmed")
        if isinstance(v, bool):
            out["plan_generation_confirmed"] = v

    if "apply_coach_suggested_goal" in updates:
        v = updates.get("apply_coach_suggested_goal")
        if v is True:
            out["apply_coach_suggested_goal"] = True

    return out or None


def _apply_structured_intake_updates(
    session: Any,
    internal_user_id: str,
    *,
    thread_ctx: DerivedThreadCoachContext,
    updates: Optional[dict],
    source_user_message: str,
) -> DerivedThreadCoachContext:
    if not isinstance(updates, dict) or not updates:
        return thread_ctx
    prior_state = thread_ctx.latest_plan_intake_state
    if not isinstance(prior_state, dict):
        return thread_ctx
    try:
        out = tool_update_plan_intake(
            session,
            str(internal_user_id),
            {"updates": updates},
            current_state=prior_state,
            source_user_message=source_user_message,
        )
        merged = out.get("plan_intake_state")
        if isinstance(merged, dict):
            logger.info(
                "[smartcoach_mobile_coach] structured_intake_updates applied user=%s fields=%s",
                str(internal_user_id)[:8],
                sorted(list(updates.keys())),
            )
            return replace(thread_ctx, latest_plan_intake_state=merged)
    except Exception:
        logger.warning(
            "[smartcoach_mobile_coach] structured_intake_updates_failed user=%s",
            str(internal_user_id)[:8],
            exc_info=True,
        )
    return thread_ctx


smartcoach_mobile_coach_bp = Blueprint(
    "smartcoach_mobile_coach",
    __name__,
    url_prefix="/api",
)


@smartcoach_mobile_coach_bp.route(
    "/conversations/<conversation_id>/agent-messages",
    methods=["POST"],
)
def agent_messages(conversation_id):
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    if not SMARTCOACH_MOBILE_AGENT_ENABLED:
        logger.info(
            "[smartcoach_mobile_coach] agent disabled correlation_id=%s", correlation_id
        )
        return (
            jsonify(
                {
                    "error": "agent_disabled",
                    "message": "Mobile coach agent is not enabled on this server.",
                }
            ),
            503,
        )

    if not request.is_json:
        return jsonify({"error": "Request content-type must be application/json"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Invalid or missing 'message'"}), 400

    readiness_tid_for_log = _coerce_readiness_trace_id(data)

    user_id, err_resp, err_code = get_user_from_auth()
    if err_resp:
        return err_resp, err_code

    uid_str = str(user_id)
    allowed, retry_after = can_make_agent_http_request(uid_str)
    if not allowed:
        return (
            jsonify(
                {
                    "error": "rate_limited",
                    "message": "Too many agent requests. Please wait and try again.",
                    "retry_after_seconds": int(max(1, round(retry_after))),
                }
            ),
            429,
        )

    session = get_session()
    start = time.time()
    t_route0 = time.perf_counter()
    try:
        conversation = (
            session.query(Conversation)
            .filter_by(id=conversation_id, user_id=user_id)
            .first()
        )
        t_route1 = time.perf_counter()
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        require_fresh = _coerce_require_fresh_strava_data(data)
        if require_fresh:
            link = session.query(UserAthleteLink).filter_by(user_id=uid_str).first()
            if link:
                readiness = evaluate_coach_strava_data_readiness(
                    session, uid_str, link.athlete_id
                )
                if not readiness.coach_data_ready:
                    logger.info(
                        "[smartcoach_mobile_coach] coach data not ready correlation_id=%s "
                        "user=%s pending_enrichment=%s sync_status=%s",
                        correlation_id,
                        uid_str,
                        readiness.pending_detail_enrichment,
                        readiness.sync_status,
                    )
                    return (
                        jsonify(
                            {
                                "code": "STRAVA_REFRESH_IN_PROGRESS",
                                "message": (
                                    "Your recent run data is still updating. "
                                    "Please try again in a few seconds."
                                ),
                                "retry_after_seconds": 5,
                                "sync_status": readiness.sync_status,
                                "pending_detail_enrichment_count": (
                                    readiness.pending_detail_enrichment
                                ),
                            }
                        ),
                        425,
                    )

        record_agent_http_request(uid_str)

        prior = (
            session.query(ConversationMessage)
            .filter_by(conversation_id=conversation_id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        t_route2 = time.perf_counter()
        raw_history = [{"role": m.role, "content": m.content or ""} for m in prior]
        history = [
            {
                "role": m.role,
                "content": _llm_plain_text_from_stored_message(m.role, m.content),
            }
            for m in prior
        ]
        thread_ctx_raw = derive_thread_coach_context(raw_history)
        structured_updates = _coerce_structured_intake_updates(data)
        thread_ctx_for_turn = _apply_structured_intake_updates(
            session,
            uid_str,
            thread_ctx=thread_ctx_raw,
            updates=structured_updates,
            source_user_message=message.strip(),
        )
        hint_activity_id = _coerce_last_activity_id(data)
        if hint_activity_id is None:
            hint_activity_id = thread_ctx_for_turn.last_structured_run_activity_id
        t_route3 = time.perf_counter()
        anchor_date, client_tz = _resolve_anchor_local_date(data)

        user_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content=message.strip(),
        )
        session.add(user_msg)

        if len(prior) == 0:
            conversation.title = message.strip()[:50] + (
                "..." if len(message) > 50 else ""
            )

        t_route4 = time.perf_counter()
        try:
            gpt_response, meta = run_mobile_agent_turn(
                session,
                uid_str,
                history,
                message.strip(),
                anchor_local_date=anchor_date,
                client_timezone=client_tz,
                eval_model_override=_coerce_eval_model_header(),
                last_activity_id_hint=hint_activity_id,
                thread_derived_context=thread_ctx_for_turn,
            )
        except RateLimitExceededError as e:
            session.rollback()
            return error_response(
                message=f"Rate limit exceeded. Please try again in {int(e.retry_after)} seconds.",
                status_code=429,
                error_code="OPENAI_RATE_LIMIT_EXCEEDED",
                details={
                    "retry_after_seconds": int(e.retry_after),
                },
            )
        except CostLimitExceededError as e:
            session.rollback()
            return error_response(
                message=e.message or "Daily cost limit exceeded.",
                status_code=429,
                error_code="OPENAI_COST_LIMIT_EXCEEDED",
                details={"limit_type": "daily_cost"},
            )

        assistant_content = (
            json.dumps(gpt_response, separators=(",", ":"))
            if isinstance(gpt_response, dict)
            else gpt_response
        )
        t_route5 = time.perf_counter()
        assistant_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
        )
        session.add(assistant_msg)
        conversation.updated_at = datetime.utcnow()
        session.commit()
        t_route6 = time.perf_counter()

        # Phase F 3F.1 — Layer B session summary (separate session; failures never affect UX).
        try:
            from src.db.db_session import SessionLocal
            from src.services.coach.session_summary_write import (
                maybe_write_session_summary_after_turn,
            )
            from src.smartcoach_mobile_coach import user_context_cache

            w_session = SessionLocal()
            try:
                maybe_write_session_summary_after_turn(
                    w_session,
                    internal_user_id=uid_str,
                    conversation_id=uuid.UUID(str(conversation_id)),
                    user_message=message.strip(),
                    assistant_reply=gpt_response,
                    meta=meta,
                )
                w_session.commit()
                user_context_cache.invalidate_user_context(uid_str)
            except Exception:
                logger.warning(
                    "[smartcoach_mobile_coach] session_summary_write failed",
                    exc_info=True,
                )
                try:
                    w_session.rollback()
                except Exception:
                    pass
            finally:
                w_session.close()
        except Exception:
            logger.debug(
                "[smartcoach_mobile_coach] session_summary_write bootstrap skipped",
                exc_info=True,
            )

        elapsed = time.time() - start
        route_timings_ms = {
            "db_conversation_ms": round((t_route1 - t_route0) * 1000, 2),
            "db_prior_messages_ms": round((t_route2 - t_route1) * 1000, 2),
            "build_history_ms": round((t_route3 - t_route2) * 1000, 2),
            "prepare_user_turn_ms": round((t_route4 - t_route3) * 1000, 2),
            "coach_orchestrator_ms": round((t_route5 - t_route4) * 1000, 2),
            "serialize_persist_commit_ms": round((t_route6 - t_route5) * 1000, 2),
            "http_handler_total_ms": round((t_route6 - t_route0) * 1000, 2),
        }
        response_shape = (
            gpt_response.get("type") if isinstance(gpt_response, dict) else "text"
        )
        logger.info(
            "[smartcoach_mobile_coach] ok correlation_id=%s user=%s conversation=%s "
            "loops=%s max_loops=%s truncated=%s cost=%.6f tokens=%s duration_ms=%d response_shape=%s "
            "route_timings_ms=%s agent_timings_ms=%s readiness_trace_id=%s",
            correlation_id,
            uid_str,
            conversation_id,
            meta.get("loops"),
            meta.get("max_loops"),
            meta.get("truncated", False),
            meta.get("cost", 0),
            meta.get("usage", {}).get("total_tokens", 0),
            int(elapsed * 1000),
            response_shape,
            json.dumps(route_timings_ms, separators=(",", ":")),
            json.dumps(
                meta.get("timings_ms") or {}, default=str, separators=(",", ":")
            ),
            readiness_tid_for_log or "",
        )

        model_used = str(meta.get("model") or "")
        resp_headers = {}
        if model_used:
            resp_headers["X-SmartCoach-Model-Used"] = model_used

        _log_agent_messages_response_audit(gpt_response)

        return (
            jsonify(
                {
                    "message": "Message sent successfully",
                    "response": gpt_response,
                    "message_id": str(user_msg.id),
                    "response_time": elapsed,
                    "token_usage": {
                        "prompt_tokens": meta.get("usage", {}).get("prompt_tokens", 0),
                        "completion_tokens": meta.get("usage", {}).get(
                            "completion_tokens", 0
                        ),
                        "total_tokens": meta.get("usage", {}).get("total_tokens", 0),
                        "model": model_used,
                    },
                }
            ),
            200,
            resp_headers,
        )

    except Exception as e:
        logger.exception(
            "[smartcoach_mobile_coach] error correlation_id=%s: %s",
            correlation_id,
            e,
        )
        session.rollback()
        return jsonify({"error": f"Failed to process agent message: {str(e)}"}), 500
    finally:
        session.close()
