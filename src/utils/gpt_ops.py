# @file gpt_ops.py
# @component GPTOps
# @description GPT logic for generating plans and answering questions
# @features: Prompt formatting, GPT calls (plain + structured), JSON-safe plan generation
# @integration-points: training_plan_service.py, ask_routes.py
# @usage: Used to generate plans or answer user questions
# @prerequisites: OPENAI_API_KEY set in .env.local

import os
import re
import json
from datetime import datetime
from typing import Dict, List
from openai import OpenAI

client = OpenAI()  # Uses OPENAI_API_KEY from env


def parse_date_safe(date_str: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {date_str}")


def format_prompt(user_question: str, activities: List[Dict]) -> str:
    prompt = "You are a smart coaching assistant helping a runner improve.\n\n"
    prompt += "ACTIVITIES:\n"

    if not activities:
        prompt += "[No activities available]\n"
    else:
        for i, a in enumerate(activities, start=1):
            prompt += f"[{i}] date: {a['date']}, distance_km: {a['distance_km']}, duration_min: {a['duration_min']}\n"

    prompt += "\nUSER QUESTION:\n"
    prompt += user_question.strip()

    return prompt


def get_gpt_response(prompt: str) -> str:
    """
    Calls GPT with a generic coaching prompt. Returns plain text.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.7,
            messages=[
                {"role": "system", "content": "You are a helpful fitness assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("GPT API call failed:", e)
        return f"❌ GPT error: {e}"


def _extract_json_from_text(text: str) -> str:
    """
    Cleans GPT output and extracts valid JSON if wrapped in markdown or extra text.
    """
    if not text:
        raise ValueError("Empty GPT response")

    # Remove markdown fences ```json ... ```
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.MULTILINE).strip()

    # Try direct parse
    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        pass

    # Fallback: extract first {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    raise ValueError(f"Could not extract valid JSON from GPT response: {text[:200]}...")


def generate_training_plan(prompt: str) -> Dict:
    """
    Calls GPT with a structured training plan prompt.
    Expects and returns parsed JSON with mandatory workouts list.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            response_format={"type": "json_object"},  # ✅ enforce JSON
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional running coach. "
                        "Always return a JSON object with fields:\n"
                        "- plan_name (string)\n"
                        "- notes (string)\n"
                        "- workouts (non-empty list of objects)\n\n"
                        "Each workout object must include:\n"
                        "- date (YYYY-MM-DD)\n"
                        "- miles (number ≥ 0)\n"
                        "- workout_type (one of: Rest, Easy, Long Run, Tempo, Intervals)\n"
                        "- intensity (string)\n"
                        "- description (string)"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content

        # 🔍 Debug log — raw GPT response
        print("\n================ RAW GPT RESPONSE ================\n")
        print(raw)
        print("\n=================================================\n")

        # Extract and parse JSON
        json_str = _extract_json_from_text(raw)
        parsed = json.loads(json_str)

        # 🔍 Debug log — parsed JSON
        print("\n================ PARSED GPT JSON ================\n")
        print(json.dumps(parsed, indent=2))
        print("\n=================================================\n")

        return parsed

    except json.JSONDecodeError:
        raise RuntimeError("GPT response could not be parsed as JSON.")
    except Exception as e:
        raise RuntimeError(f"GPT training plan generation failed: {e}")
