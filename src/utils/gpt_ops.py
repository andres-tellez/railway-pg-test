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

# Handle both old and new OpenAI API versions
try:
    from openai import OpenAI

    client = OpenAI()  # Uses OPENAI_API_KEY from env
except ImportError:
    # Fallback for older openai versions
    import openai

    openai.api_key = os.getenv("OPENAI_API_KEY")
    client = None


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
        if client is not None:
            # New OpenAI API
            response = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful fitness assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        else:
            # Old OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful fitness assistant.",
                    },
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
        except json.JSONDecodeError as e:
            # Try to fix incomplete JSON
            print(f"⚠️ JSON parsing failed: {e}")
            print(f"⚠️ Attempting to fix incomplete JSON...")

            # Try to complete the JSON by finding the last complete object
            fixed_json = _try_fix_incomplete_json(candidate)
            if fixed_json:
                try:
                    json.loads(fixed_json)
                    print("✅ Successfully fixed incomplete JSON")
                    return fixed_json
                except json.JSONDecodeError as fix_error:
                    print(f"❌ Could not fix incomplete JSON: {fix_error}")
                    # Try a simpler approach - just truncate at the last complete workout
                    simple_fix = _simple_truncate_json(candidate)
                    if simple_fix:
                        try:
                            json.loads(simple_fix)
                            print("✅ Successfully fixed with simple truncation")
                            return simple_fix
                        except json.JSONDecodeError:
                            pass

    raise ValueError(f"Could not extract valid JSON from GPT response: {text[:200]}...")

def _try_fix_incomplete_json(incomplete_json: str) -> str:
    """Try to fix incomplete JSON by finding where it was cut off."""
    if not incomplete_json.strip().endswith('}'):
        # Find the last complete object in the workouts array
        if '"workouts"' in incomplete_json and '[' in incomplete_json:
            # Find the workouts array
            workouts_start = incomplete_json.find('"workouts"')
            if workouts_start != -1:
                # Find the opening bracket
                bracket_start = incomplete_json.find('[', workouts_start)
                if bracket_start != -1:
                    # Look for the last complete workout object
                    last_complete_pos = -1
                    brace_count = 0
                    in_workout_object = False

                    for i, char in enumerate(incomplete_json[bracket_start:], bracket_start):
                        if char == '{' and not in_workout_object:
                            # Start of a new workout object
                            brace_count = 1
                            in_workout_object = True
                        elif char == '{' and in_workout_object:
                            # Nested brace (like in description strings)
                            brace_count += 1
                        elif char == '}' and in_workout_object:
                            brace_count -= 1
                            if brace_count == 0:
                                # End of complete workout object
                                last_complete_pos = i + 1
                                in_workout_object = False

                    if last_complete_pos > 0:
                        # Truncate at the last complete object and close arrays/objects
                        fixed = incomplete_json[:last_complete_pos] + ']}'
                        print(f"🔧 Fixed incomplete JSON by truncating at position {last_complete_pos}")
                        return fixed

    return None

def _simple_truncate_json(incomplete_json: str) -> str:
    """Simple approach: find the last complete workout and truncate there."""
    if '"workouts"' in incomplete_json:
        # Find the workouts array
        workouts_start = incomplete_json.find('"workouts"')
        if workouts_start != -1:
            # Find the opening bracket
            bracket_start = incomplete_json.find('[', workouts_start)
            if bracket_start != -1:
                # Look for the last complete workout object
                # Find the last occurrence of a complete workout pattern
                last_complete_pattern = incomplete_json.rfind('"description":')
                if last_complete_pattern != -1:
                    # Find the closing brace for this workout
                    # Start from the beginning of the workout object
                    workout_start = incomplete_json.rfind('{', 0, last_complete_pattern)
                    if workout_start != -1:
                        brace_count = 0
                        for i in range(workout_start, len(incomplete_json)):
                            if incomplete_json[i] == '{':
                                brace_count += 1
                            elif incomplete_json[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    # Found the end of the last complete workout
                                    truncate_pos = i + 1
                                    # Close the workouts array and main object
                                    fixed = incomplete_json[:truncate_pos] + ']}'
                                    print(f"🔧 Simple truncation at position {truncate_pos}")
                                    return fixed

                # Fallback: if we can't find complete workouts, just truncate at a reasonable point
                # Find the last complete workout by looking for the pattern
                last_comma = incomplete_json.rfind(',')
                if last_comma != -1:
                    # Find the start of the last workout object
                    last_brace = incomplete_json.rfind('{', 0, last_comma)
                    if last_brace != -1:
                        # Try to find the end of this workout
                        brace_count = 0
                        for i in range(last_brace, len(incomplete_json)):
                            if incomplete_json[i] == '{':
                                brace_count += 1
                            elif incomplete_json[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    truncate_pos = i + 1
                                    fixed = incomplete_json[:truncate_pos] + ']}'
                                    print(f"🔧 Fallback truncation at position {truncate_pos}")
                                    return fixed
    return None


def generate_training_plan_chunk(prompt: str) -> list:
    """
    Generate a chunk of training plan workouts (just the workouts array).
    """
    try:
        if client is not None:
            # New OpenAI API
            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                response_format={"type": "json_object"},
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional running coach. "
                            "Return a JSON object with a 'workouts' array containing training plan workouts."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        else:
            # Old OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4-1106-preview",
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional running coach. "
                            "Return a JSON object with a 'workouts' array containing training plan workouts."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        raw = response.choices[0].message.content

        # Extract and parse JSON
        json_str = _extract_json_from_text(raw)
        parsed = json.loads(json_str)

        # Return just the workouts array
        return parsed.get("workouts", [])

    except Exception as e:
        print(f"❌ Error generating training plan chunk: {e}")
        return []

def generate_training_plan(prompt: str) -> Dict:
    """
    Calls GPT with a structured training plan prompt.
    Expects and returns parsed JSON with mandatory workouts list.
    """
    try:
        if client is not None:
            # New OpenAI API
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
        else:
            # Old OpenAI API - note: no response_format support
            response = openai.ChatCompletion.create(
                model="gpt-4-1106-preview",
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

        # 🔍 Debug log — raw GPT response (truncated for readability)
        print(f"\n================ RAW GPT RESPONSE ================")
        print(f"Response length: {len(raw)} characters")
        print(f"First 500 chars: {raw[:500]}...")
        print("=================================================\n")

        # Extract and parse JSON
        json_str = _extract_json_from_text(raw)
        parsed = json.loads(json_str)

        # 🔍 Debug log — parsed JSON (summary only)
        print(f"\n================ PARSED GPT JSON ================")
        print(f"Plan name: {parsed.get('plan_name', 'N/A')}")
        print(f"Workouts count: {len(parsed.get('workouts', []))}")
        if parsed.get('workouts'):
            first_workout = parsed['workouts'][0]
            last_workout = parsed['workouts'][-1]
            print(f"Date range: {first_workout.get('date')} to {last_workout.get('date')}")
        print("=================================================\n")

        return parsed

    except json.JSONDecodeError:
        raise RuntimeError("GPT response could not be parsed as JSON.")
    except Exception as e:
        raise RuntimeError(f"GPT training plan generation failed: {e}")
