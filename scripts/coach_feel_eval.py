#!/usr/bin/env python3
"""
Coach “feel” eval — two passes (gpt-4o-mini vs gpt-4o), one workbook.

Responses are **only** from SmartCoach `POST /api/conversations/.../agent-messages`
(verbatim JSON/text in the spreadsheet). You rate empty columns yourself.

Prerequisites
-------------
1. API must accept per-request eval models:
     export SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE=1
   on the **API** server (use **staging**; leave **off** in prod unless you trust callers).

2. A valid Auth0 (or SmartCoach) **Bearer** token for a real user with coach data:
     export SMARTCOACH_EVAL_BEARER_TOKEN="eyJ..."
     export SMARTCOACH_EVAL_API_BASE_URL="https://api.your-host.example"

3. Run:
     python scripts/coach_feel_eval.py --output coach_feel_eval.xlsx

The script creates **two worksheets** (sheet names: ``gpt-4o-mini`` and ``gpt-4o``).
Each sheet is one **continuous** conversation (same prompt order as below).

If ``X-SmartCoach-Model-Used`` does not match the requested pass model, the script
prints a warning (usually means ``SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE`` is off).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from typing import Any, Dict, List, Tuple

import requests
import xlsxwriter

# Fixed prompt order (single thread per pass).
PROMPTS: List[str] = [
    # Core run feedback
    "How was my run?",
    "That felt really easy — is that okay?",
    "That run was really hard",
    "I think I went too fast",
    "My heart rate drifted — is that bad?",
    # Coaching / teaching
    "What is a threshold run?",
    "How do I improve endurance?",
    "Should I run every day?",
    "What should I focus on this week?",
    "How do I know if I'm improving?",
    # Pushback / correction
    "I skipped my run today",
    "I want to run hard every day",
    "I don't think easy runs do anything",
    "I feel like I'm not getting better",
    # Emotional / human tone
    "I feel slow",
    "That was a great run",
    "I'm tired today",
    "I'm losing motivation",
    # Follow-ups
    "Ok but what should I do tomorrow?",
    "Can you simplify that?",
]

PASS_CONFIG: List[Tuple[str, str]] = [
    (
        "gpt-4o-mini",
        "Pass 1 — OpenAI gpt-4o-mini (rate empty columns yourself)",
    ),
    (
        "gpt-4o",
        "Pass 2 — OpenAI gpt-4o / GPT-4o full (rate empty columns yourself)",
    ),
]


def _format_assistant_response(payload: Any) -> str:
    """Verbatim assistant payload for the spreadsheet cell."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False)
    return json.dumps(payload, default=str, ensure_ascii=False)


def _create_conversation(sess: requests.Session, base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/api/conversations"
    r = sess.post(url, json={}, timeout=300)
    if r.status_code == 401:
        raise SystemExit(
            "POST /api/conversations returned 401 — token expired or invalid."
        )
    r.raise_for_status()
    data = r.json()
    cid = data.get("id") or data.get("conversation_id") or data.get("conversationId")
    if not cid:
        raise SystemExit(f"Could not parse conversation id from: {data!r}")
    return str(cid)


def _post_agent_message(
    sess: requests.Session,
    base_url: str,
    conversation_id: str,
    message: str,
    eval_model: str,
) -> Tuple[Dict[str, Any], str]:
    url = f"{base_url.rstrip('/')}/api/conversations/{conversation_id}/agent-messages"
    body = {
        "message": message,
        "client_local_date": date.today().isoformat(),
    }
    headers = {
        "X-SmartCoach-Client": "mobile",
        "X-SmartCoach-Eval-Model": eval_model,
    }
    r = sess.post(url, json=body, headers=headers, timeout=300)
    text = r.text
    try:
        data = r.json()
    except json.JSONDecodeError:
        data = None
    if r.status_code != 200:
        raise RuntimeError(f"agent-messages HTTP {r.status_code}: {text[:800]}")
    if not isinstance(data, dict):
        raise RuntimeError(f"agent-messages: expected JSON object, got {text[:400]!r}")
    model_hdr = r.headers.get("X-SmartCoach-Model-Used", "")
    return data, model_hdr


def run_pass(
    sess: requests.Session,
    base_url: str,
    eval_model: str,
    pause_s: float,
) -> List[Tuple[int, str, str, str, str]]:
    """
    Returns rows: (#, prompt, response_text, model_header, mismatch_note)
    """
    cid = _create_conversation(sess, base_url)
    rows: List[Tuple[int, str, str, str, str]] = []
    for i, prompt in enumerate(PROMPTS, start=1):
        data, model_hdr = _post_agent_message(sess, base_url, cid, prompt, eval_model)
        raw_resp = data.get("response")
        cell = _format_assistant_response(raw_resp)
        note = ""
        if model_hdr and model_hdr != eval_model:
            note = f"WARN: header model {model_hdr!r} != requested {eval_model!r}"
        elif not model_hdr:
            note = "WARN: no X-SmartCoach-Model-Used (SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE off?)"
        rows.append((i, prompt, cell, model_hdr, note))
        if pause_s > 0:
            time.sleep(pause_s)
    return rows


def write_workbook(
    output_path: str,
    all_rows: Dict[str, List[Tuple[int, str, str, str, str]]],
    pass_titles: Dict[str, str],
) -> None:
    workbook = xlsxwriter.Workbook(output_path)
    title_fmt = workbook.add_format({"bold": True, "font_size": 11})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2"})
    wrap = workbook.add_format({"text_wrap": True, "valign": "top"})

    headers = [
        "#",
        "Prompt",
        "Response (verbatim SmartCoach)",
        "Brevity (1–5)",
        "Human / natural (1–5)",
        "Engaging (1–5)",
        "Worth continuing chat (1–5)",
        "Notes",
    ]

    for model_id, rows in all_rows.items():
        sheet_name = model_id[:31]
        ws = workbook.add_worksheet(sheet_name)
        title = pass_titles.get(model_id, model_id)
        ws.merge_range(0, 0, 0, len(headers) - 1, title, title_fmt)
        for col, h in enumerate(headers):
            ws.write(1, col, h, header_fmt)

        ws.set_column(0, 0, 5)
        ws.set_column(1, 1, 44)
        ws.set_column(2, 2, 85, wrap)
        ws.set_column(3, 7, 16)

        for ridx, (num, prompt, response, _hdr, meta_note) in enumerate(rows, start=2):
            ws.write(ridx, 0, num)
            ws.write(ridx, 1, prompt)
            ws.write(ridx, 2, response, wrap)
            # rating columns left blank for you
            if meta_note:
                ws.write(ridx, 7, meta_note, wrap)

    workbook.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coach feel eval → Excel (two model passes)."
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="API base URL (default: env SMARTCOACH_EVAL_API_BASE_URL)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token (default: env SMARTCOACH_EVAL_BEARER_TOKEN)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="coach_feel_eval.xlsx",
        help="Output .xlsx path",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.75,
        help="Seconds between agent-messages calls (rate limits / server breathing room)",
    )
    args = parser.parse_args()

    base_url = (args.base_url or "").strip() or (
        os.environ.get("SMARTCOACH_EVAL_API_BASE_URL") or ""
    ).strip()
    token = (args.token or "").strip() or (
        os.environ.get("SMARTCOACH_EVAL_BEARER_TOKEN") or ""
    ).strip()

    if not base_url:
        print("Set --base-url or SMARTCOACH_EVAL_API_BASE_URL", file=sys.stderr)
        sys.exit(2)
    if not token:
        print("Set --token or SMARTCOACH_EVAL_BEARER_TOKEN", file=sys.stderr)
        sys.exit(2)

    sess = requests.Session()
    sess.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    all_rows: Dict[str, List[Tuple[int, str, str, str, str]]] = {}
    pass_titles = {mid: title for mid, title in PASS_CONFIG}

    for eval_model, _title in PASS_CONFIG:
        print(
            f"--- Running pass: {eval_model} ({len(PROMPTS)} prompts) ---", flush=True
        )
        try:
            rows = run_pass(sess, base_url, eval_model, args.pause)
        except Exception as exc:
            print(f"ERROR pass {eval_model}: {exc}", file=sys.stderr)
            sys.exit(1)
        all_rows[eval_model] = rows
        for num, _p, _c, hdr, note in rows[:1]:
            if note:
                print(note, flush=True)

    write_workbook(args.output, all_rows, pass_titles)
    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
