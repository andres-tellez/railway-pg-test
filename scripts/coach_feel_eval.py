#!/usr/bin/env python3
"""
Coach "feel" eval — two passes (gpt-4o-mini vs gpt-4o), one workbook.

Responses are **only** from SmartCoach `POST /api/conversations/.../agent-messages`
(verbatim JSON/text in the spreadsheet). You rate empty columns yourself.

Prerequisites
-------------
1. API must allow eval model header (pick one on the **API** server — staging recommended):

   **Option A — override flag** (any authenticated client can pick allowlisted models):

     export SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE=1

   **Option B — shared secret** (script sends ``X-SmartCoach-Eval-Secret``):

     export SMARTCOACH_COACH_EVAL_REQUEST_SECRET="your-long-random-string"

   Set the **same** ``SMARTCOACH_COACH_EVAL_REQUEST_SECRET`` in your shell or ``.env.local``
   when running this script so it can send the header.

2. A valid Auth0 (or SmartCoach) **Bearer** token for a real user with coach data:
     export SMARTCOACH_EVAL_BEARER_TOKEN="eyJ..."
     export SMARTCOACH_EVAL_API_BASE_URL="https://api.your-host.example"

3. Run:
     python scripts/coach_feel_eval.py --output coach_feel_eval.xlsx

   Rate limits: use ``--pause`` and/or a subset, e.g. first 5 prompts only:
     python scripts/coach_feel_eval.py -o coach_feel_eval.xlsx --max-prompts 5 --pause 15

   One question at a time (mini only), print coach text (not one-line JSON):
     python scripts/coach_feel_eval.py --pass-models gpt-4o-mini --prompt-index 1 --print

   Same plus indented full payload:
     python scripts/coach_feel_eval.py --pass-models gpt-4o-mini --prompt-index 1 --print --print-json

The script creates **two worksheets** (sheet names: ``gpt-4o-mini`` and ``gpt-4o``).
Each sheet is one **continuous** conversation (same prompt order as below).

If ``X-SmartCoach-Model-Used`` does not match the requested pass model, the script
prints a warning (eval headers not enabled on API, or secret/env mismatch).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
import xlsxwriter

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


def _load_local_dotenv() -> None:
    """Load repo-root `.env.local` if present (does not override existing env)."""
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env.local"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        pass


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
    headers: Dict[str, str] = {
        "X-SmartCoach-Client": "mobile",
        "X-SmartCoach-Eval-Model": eval_model,
    }
    eval_secret = (os.environ.get("SMARTCOACH_COACH_EVAL_REQUEST_SECRET") or "").strip()
    if eval_secret:
        headers["X-SmartCoach-Eval-Secret"] = eval_secret
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
    prompts: List[str],
    first_row_num: int = 1,
) -> List[Tuple[int, str, str, str, str]]:
    """
    Returns rows: (#, prompt, response_text, model_header, mismatch_note).
    ``first_row_num`` is the display index for the first prompt (e.g. 7 for Q7 only).
    """
    cid = _create_conversation(sess, base_url)
    rows: List[Tuple[int, str, str, str, str]] = []
    for i, prompt in enumerate(prompts, start=first_row_num):
        data, model_hdr = _post_agent_message(sess, base_url, cid, prompt, eval_model)
        raw_resp = data.get("response")
        cell = _format_assistant_response(raw_resp)
        note = ""
        if model_hdr and model_hdr != eval_model:
            note = f"WARN: header model {model_hdr!r} != requested {eval_model!r}"
        elif not model_hdr:
            note = (
                "WARN: no X-SmartCoach-Model-Used — set SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE=1 "
                "on API, or SMARTCOACH_COACH_EVAL_REQUEST_SECRET on API and the same env var "
                "when running this script."
            )
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
            if meta_note:
                ws.write(ridx, 7, meta_note, wrap)

    workbook.close()


def _coach_clipboard_parts(cell: str) -> Tuple[str, str | None]:
    """
    Prefer the human coach string (``content``) for copy/paste; keep full pretty
    JSON available when the payload is a JSON object.
    """
    try:
        obj = json.loads(cell)
    except (json.JSONDecodeError, TypeError):
        return cell, None
    if isinstance(obj, dict):
        pretty = json.dumps(obj, ensure_ascii=False, indent=2)
        c = obj.get("content")
        if isinstance(c, str) and c.strip():
            return c.strip(), pretty
        return pretty, None
    if isinstance(obj, str):
        return obj, None
    return json.dumps(obj, ensure_ascii=False, indent=2), None


def _print_stdout_copypaste(
    all_rows: Dict[str, List[Tuple[int, str, str, str, str]]],
    *,
    include_full_json: bool,
) -> None:
    """Blocks for pasting: coach text first; optional pretty JSON; meta on stderr."""
    for eval_model, rows in all_rows.items():
        for num, prompt, cell, _hdr, note in rows:
            primary, full_pretty = _coach_clipboard_parts(cell)
            print(f"=== Q{num} | {eval_model} ===", flush=True)
            print("Prompt:", flush=True)
            print(prompt, flush=True)
            print("---", flush=True)
            print("Coach:", flush=True)
            print(primary, flush=True)
            if include_full_json:
                print("", flush=True)
                print("Full JSON:", flush=True)
                if full_pretty is not None:
                    print(full_pretty, flush=True)
                else:
                    try:
                        obj = json.loads(cell)
                        print(
                            json.dumps(obj, ensure_ascii=False, indent=2),
                            flush=True,
                        )
                    except (json.JSONDecodeError, TypeError):
                        print(cell, flush=True)
            if note:
                print(note, file=sys.stderr, flush=True)
            print(flush=True)


def main() -> None:
    _load_local_dotenv()

    known_models = [m for m, _ in PASS_CONFIG]
    parser = argparse.ArgumentParser(
        description="Coach feel eval to Excel (two model passes) or stdout (--print)."
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
    sel = parser.add_mutually_exclusive_group()
    sel.add_argument(
        "--max-prompts",
        type=int,
        default=None,
        metavar="N",
        help="Only the first N prompts in order (default: all %d)." % len(PROMPTS),
    )
    sel.add_argument(
        "--prompt-index",
        type=int,
        default=None,
        metavar="N",
        help="Run only prompt N from the fixed list (1-based, e.g. 1 for Q1).",
    )
    parser.add_argument(
        "--pass-models",
        default=None,
        metavar="LIST",
        help=(
            "Comma-separated models to run, in order (default: %s). "
            "Example: gpt-4o-mini to skip gpt-4o and reduce TPM."
            % ",".join(known_models)
        ),
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print Q blocks to stdout for copy/paste; do not write Excel.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="With --print, also print pretty-printed full JSON after coach text.",
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

    n_all = len(PROMPTS)
    first_row_num = 1
    if args.prompt_index is not None:
        if args.prompt_index < 1 or args.prompt_index > n_all:
            print(
                f"--prompt-index must be between 1 and {n_all} (got {args.prompt_index})",
                file=sys.stderr,
            )
            sys.exit(2)
        prompts_run = [PROMPTS[args.prompt_index - 1]]
        first_row_num = args.prompt_index
    elif args.max_prompts is None:
        prompts_run = PROMPTS
    else:
        if args.max_prompts < 1 or args.max_prompts > n_all:
            print(
                f"--max-prompts must be between 1 and {n_all} (got {args.max_prompts})",
                file=sys.stderr,
            )
            sys.exit(2)
        prompts_run = PROMPTS[: args.max_prompts]

    if args.pass_models is None:
        pass_plan: List[Tuple[str, str]] = list(PASS_CONFIG)
    else:
        raw = [p.strip() for p in args.pass_models.split(",") if p.strip()]
        if not raw:
            print("--pass-models must list at least one model.", file=sys.stderr)
            sys.exit(2)
        known_set = set(known_models)
        bad = [m for m in raw if m not in known_set]
        if bad:
            print(
                f"Unknown model(s) in --pass-models: {bad!r}. "
                f"Allowed: {', '.join(known_models)}",
                file=sys.stderr,
            )
            sys.exit(2)
        title_by_id = dict(PASS_CONFIG)
        pass_plan = [(m, title_by_id[m]) for m in raw]

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
    progress_out = sys.stderr if args.print else sys.stdout

    for eval_model, _title in pass_plan:
        print(
            f"--- Running pass: {eval_model} ({len(prompts_run)} prompts) ---",
            flush=True,
            file=progress_out,
        )
        try:
            rows = run_pass(
                sess,
                base_url,
                eval_model,
                args.pause,
                prompts_run,
                first_row_num,
            )
        except Exception as exc:
            print(f"ERROR pass {eval_model}: {exc}", file=sys.stderr)
            sys.exit(1)
        all_rows[eval_model] = rows
        for num, _p, _c, hdr, note in rows[:1]:
            if note:
                print(note, flush=True, file=progress_out)

    if args.print:
        _print_stdout_copypaste(all_rows, include_full_json=bool(args.print_json))
        print(
            "Done (--print: no Excel file written).",
            flush=True,
            file=sys.stderr,
        )
    else:
        write_workbook(args.output, all_rows, pass_titles)
        print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
