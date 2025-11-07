# @file gpt_ops.py
# @component GPTOps
# @description GPT logic for generating plans and answering questions
# @features: Prompt formatting, GPT calls (plain + structured), JSON-safe plan generation
# @integration-points: training_plan_service.py, conversation_routes.py
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

# Model configuration with cost-friendly defaults
# Using gpt-4o for training plans, gpt-3.5-turbo for conversations
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
TRAINING_PLAN_MODEL = os.getenv("OPENAI_TRAINING_PLAN_MODEL", "gpt-4o")
CONVERSATION_MODEL = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-3.5-turbo")
print(
    f"[INFO] OpenAI models => DEFAULT_MODEL={DEFAULT_MODEL}, TRAINING_PLAN_MODEL={TRAINING_PLAN_MODEL}, CONVERSATION_MODEL={CONVERSATION_MODEL}"
)

# Jack Daniels methodology system prompt for training plan generation
JACK_DANIELS_SYSTEM_PROMPT = """
You are an expert running coach generating training plans strictly using the Jack Daniels Running Formula.

Principles you MUST follow:
- Long Run occurs on the weekend: prefer Saturday; if Saturday is not a training day, use Sunday. Do not schedule the Long Run on weekdays. No long run in race week
- Respect the provided training days; schedule workouts only on those dates

Output should follow the caller's instructions precisely.
"""


def parse_date_safe(date_str: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {date_str}")


def get_conversation_response(
    messages: List[Dict], require_json: bool = False, question: str = None
) -> str:
    """
    Calls GPT with conversation history for chat-like interactions.
    Uses our new strategic conversation service approach.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        require_json: If True, enforces JSON response format
        question: The user's question (unused in new system)
    """
    try:
        # Use our new system - always use GPT-3.5-turbo for conversations
        selected_model = CONVERSATION_MODEL

        if client is not None:
            # New OpenAI API with optimized parameters
            call_params = {
                "model": selected_model,
                "temperature": 0.7,  # Slightly higher for more natural conversation
                "timeout": 30.0,  # Reduced timeout for faster response
                "messages": messages,
                "max_tokens": 800,  # Increased for more comprehensive responses
            }
            # Only add response_format if JSON is required
            if require_json:
                call_params["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**call_params)
            # Token usage logging
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    print(
                        f"[DEBUG] Token usage (conversation): prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}"
                    )
            except Exception:
                pass

            # Check if response is valid
            if not response or not response.choices:
                raise ValueError("Empty response from GPT API")

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("GPT returned None content - possibly hit token limit")

            return content.strip()
        else:
            # Old OpenAI API
            response = openai.ChatCompletion.create(
                model=CONVERSATION_MODEL,
                temperature=0.7,
                messages=messages,
                max_tokens=800,  # Increased for more comprehensive responses
            )
            # Token usage logging (legacy)
            try:
                usage = (
                    response.get("usage")
                    if isinstance(response, dict)
                    else getattr(response, "usage", None)
                )
                if usage:
                    print(
                        f"[DEBUG] Token usage (conversation): prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')} total={usage.get('total_tokens')}"
                    )
            except Exception:
                pass

            # Check if response is valid
            if not response or not response.get("choices"):
                raise ValueError("Empty response from GPT API")

            content = response["choices"][0]["message"]["content"]
            if content is None:
                raise ValueError("GPT returned None content - possibly hit token limit")

            return content.strip()
    except Exception as e:
        print("GPT conversation API call failed:", e)
        return f"[ERROR] GPT error: {e}"


async def get_conversation_response_async(
    messages: List[Dict], require_json: bool = False
) -> str:
    """
    Async version of GPT conversation response for faster performance.
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CONVERSATION_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500,
                    "response_format": (
                        {"type": "json_object"} if require_json else None
                    ),
                },
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("choices"):
                raise ValueError("Empty response from GPT API")

            content = data["choices"][0]["message"]["content"]
            if content is None:
                raise ValueError("GPT returned None content")

            return content.strip()

    except Exception as e:
        print("Async GPT conversation API call failed:", e)
        return f"[ERROR] GPT error: {e}"


def get_gpt_response(prompt: str, require_json: bool = True) -> str:
    """
    Calls GPT with a generic coaching prompt. Returns plain text.

    Args:
        prompt: The user prompt to send to GPT
        require_json: If True, enforces JSON response format (default). Set to False for plain text responses.
    """
    try:
        if client is not None:
            # New OpenAI API
            call_params = {
                "model": DEFAULT_MODEL,
                "temperature": 0.25,
                "timeout": 60.0,  # 60 second timeout
                "messages": [
                    {"role": "system", "content": JACK_DANIELS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            }
            # Only add response_format if JSON is required
            if require_json:
                call_params["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**call_params)
            # Token usage logging (new OpenAI client)
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    print(
                        f"[DEBUG] Token usage (get_gpt_response): prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}"
                    )
            except Exception:
                pass

            # Check if response is valid
            if not response or not response.choices:
                raise ValueError("Empty response from GPT API")

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("GPT returned None content - possibly hit token limit")

            return content.strip()
        else:
            # Old OpenAI API
            response = openai.ChatCompletion.create(
                model=DEFAULT_MODEL,
                temperature=0.25,
                messages=[
                    {"role": "system", "content": JACK_DANIELS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            # Token usage logging (legacy OpenAI client)
            try:
                usage = (
                    response.get("usage")
                    if isinstance(response, dict)
                    else getattr(response, "usage", None)
                )
                if usage:
                    print(
                        f"[DEBUG] Token usage (get_gpt_response): prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')} total={usage.get('total_tokens')}"
                    )
            except Exception:
                pass

            # Check if response is valid
            if not response or not response.get("choices"):
                raise ValueError("Empty response from GPT API")

            content = response["choices"][0]["message"]["content"]
            if content is None:
                raise ValueError("GPT returned None content - possibly hit token limit")

            return content.strip()
    except Exception as e:
        print("GPT API call failed:", e)
        return f"[ERROR] GPT error: {e}"


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
            print(f"[WARNING] JSON parsing failed: {e}")
            print(f"[WARNING] Attempting to fix incomplete JSON...")

            # Try to complete the JSON by finding the last complete object
            fixed_json = _try_fix_incomplete_json(candidate)
            if fixed_json:
                try:
                    json.loads(fixed_json)
                    print("[SUCCESS] Successfully fixed incomplete JSON")
                    return fixed_json
                except json.JSONDecodeError as fix_error:
                    print(f"[ERROR] Could not fix incomplete JSON: {fix_error}")
                    # Try a simpler approach - just truncate at the last complete workout
                    simple_fix = _simple_truncate_json(candidate)
                    if simple_fix:
                        try:
                            json.loads(simple_fix)
                            print("[SUCCESS] Successfully fixed with simple truncation")
                            return simple_fix
                        except json.JSONDecodeError:
                            pass

    raise ValueError(f"Could not extract valid JSON from GPT response: {text[:200]}...")


def _try_fix_incomplete_json(incomplete_json: str) -> str:
    """Try to fix incomplete JSON by finding where it was cut off."""
    if not incomplete_json.strip().endswith("}"):
        # Find the last complete object in the workouts array
        if '"workouts"' in incomplete_json and "[" in incomplete_json:
            # Find the workouts array
            workouts_start = incomplete_json.find('"workouts"')
            if workouts_start != -1:
                # Find the opening bracket
                bracket_start = incomplete_json.find("[", workouts_start)
                if bracket_start != -1:
                    # Look for the last complete workout object
                    last_complete_pos = -1
                    brace_count = 0
                    in_workout_object = False

                    for i, char in enumerate(
                        incomplete_json[bracket_start:], bracket_start
                    ):
                        if char == "{" and not in_workout_object:
                            # Start of a new workout object
                            brace_count = 1
                            in_workout_object = True
                        elif char == "{" and in_workout_object:
                            # Nested brace (like in description strings)
                            brace_count += 1
                        elif char == "}" and in_workout_object:
                            brace_count -= 1
                            if brace_count == 0:
                                # End of complete workout object
                                last_complete_pos = i + 1
                                in_workout_object = False

                    if last_complete_pos > 0:
                        # Truncate at the last complete object and close arrays/objects
                        fixed = incomplete_json[:last_complete_pos] + "]}"
                        print(
                            f"[DEBUG] Fixed incomplete JSON by truncating at position {last_complete_pos}"
                        )
                        return fixed

    return None


def _simple_truncate_json(incomplete_json: str) -> str:
    """Simple approach: find the last complete workout and truncate there."""
    if '"workouts"' in incomplete_json:
        # Find the workouts array
        workouts_start = incomplete_json.find('"workouts"')
        if workouts_start != -1:
            # Find the opening bracket
            bracket_start = incomplete_json.find("[", workouts_start)
            if bracket_start != -1:
                # Look for the last complete workout object
                # Find the last occurrence of a complete workout pattern
                last_complete_pattern = incomplete_json.rfind('"description":')
                if last_complete_pattern != -1:
                    # Find the closing brace for this workout
                    # Start from the beginning of the workout object
                    workout_start = incomplete_json.rfind("{", 0, last_complete_pattern)
                    if workout_start != -1:
                        brace_count = 0
                        for i in range(workout_start, len(incomplete_json)):
                            if incomplete_json[i] == "{":
                                brace_count += 1
                            elif incomplete_json[i] == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    # Found the end of the last complete workout
                                    truncate_pos = i + 1
                                    # Close the workouts array and main object
                                    fixed = incomplete_json[:truncate_pos] + "]}"
                                    print(
                                        f"[DEBUG] Simple truncation at position {truncate_pos}"
                                    )
                                    return fixed

                # Fallback: if we can't find complete workouts, just truncate at a reasonable point
                # Find the last complete workout by looking for the pattern
                last_comma = incomplete_json.rfind(",")
                if last_comma != -1:
                    # Find the start of the last workout object
                    last_brace = incomplete_json.rfind("{", 0, last_comma)
                    if last_brace != -1:
                        # Try to find the end of this workout
                        brace_count = 0
                        for i in range(last_brace, len(incomplete_json)):
                            if incomplete_json[i] == "{":
                                brace_count += 1
                            elif incomplete_json[i] == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    truncate_pos = i + 1
                                    fixed = incomplete_json[:truncate_pos] + "]}"
                                    print(
                                        f"[DEBUG] Fallback truncation at position {truncate_pos}"
                                    )
                                    return fixed
    return None
