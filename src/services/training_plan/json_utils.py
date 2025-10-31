from __future__ import annotations

import json
from typing import Any, Optional


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # remove leading fence and any language tag
        t = t.lstrip("`\n ")
    if t.endswith("```"):
        t = t.rstrip("`\n ")
    return t


def parse_json_flexible(text: str) -> Any:
    """Parse JSON from an LLM response that may include code fences or prose.

    Strategy:
    - Strip code fences and whitespace
    - Find the first '{' or '[' and the last '}' or ']' accordingly
    - Attempt json.loads; if it fails, progressively narrow to common wrappers
    """
    if text is None:
        raise ValueError("Empty response from LLM")

    t = _strip_code_fences(text)
    # Find first opening brace/bracket
    first_obj = t.find("{")
    first_arr = t.find("[")
    starts = [i for i in [first_obj, first_arr] if i != -1]
    if not starts:
        # No JSON-looking content; raise
        raise ValueError("No JSON object or array found in response")
    start = min(starts)

    # Guess closing based on start char
    open_char = t[start]
    close_char = "}" if open_char == "{" else "]"
    end = t.rfind(close_char)
    if end == -1:
        end = len(t)

    candidate = t[start : end + 1]

    try:
        return json.loads(candidate)
    except Exception:
        # Last resort: scan for first valid JSON substring by moving end left
        for i in range(len(candidate), 0, -1):
            try:
                return json.loads(candidate[:i])
            except Exception:
                continue
        raise


def extract_first_list(obj: Any) -> Optional[list]:
    """Return the first list found in an object, decoding JSON strings if needed."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, str):
        s = obj.strip()
        if (s.startswith("[") and s.endswith("]")) or (
            s.startswith("{") and s.endswith("}")
        ):
            try:
                loaded = json.loads(s)
                return extract_first_list(loaded)
            except Exception:
                return None
        return None
    if isinstance(obj, dict):
        # Prefer common keys
        for key in ["weeks", "data", "result", "items", "output"]:
            if key in obj:
                lst = extract_first_list(obj[key])
                if isinstance(lst, list):
                    return lst
        # Fallback: scan values
        for v in obj.values():
            lst = extract_first_list(v)
            if isinstance(lst, list):
                return lst
    return None
