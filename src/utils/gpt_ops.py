# @file gpt_ops.py
# @component GPTOps
# @description GPT logic for generating plans and answering questions
# @features: Prompt formatting, GPT calls (plain + structured), JSON-safe plan generation
# @integration-points: training_plan_service.py, conversation_routes.py
# @usage: Used to generate plans or answer user questions
# @prerequisites: OPENAI_API_KEY set in .env.local
#
# NOTE: This module is being migrated to use OpenAIService from
# src/services/security/external_apis/openai_service.py for centralized
# security controls (rate limiting, cost tracking, etc.)

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Tuple

# Import unified OpenAI service
from src.services.security.external_apis.openai_service import (
    OpenAIService,
    RateLimitExceededError,
    CostLimitExceededError,
    get_openai_service,
)

# Model configuration with cost-friendly defaults
# Using gpt-4o for training plans and conversations
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
TRAINING_PLAN_MODEL = os.getenv("OPENAI_TRAINING_PLAN_MODEL", "gpt-4o")
CONVERSATION_MODEL = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")
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
    messages: List[Dict],
    user_id: str,
    require_json: bool = False,
    question: str = None,
) -> Tuple[str, Dict]:
    """
    Calls GPT with conversation history for chat-like interactions.

    Uses unified OpenAIService with automatic rate limiting and cost tracking.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        user_id: User identifier (REQUIRED for security tracking)
        require_json: If True, enforces JSON response format
        question: The user's question (unused, kept for backward compatibility)

    Returns:
        Tuple of (content: str, usage_info: Dict)

    Raises:
        RateLimitExceededError: If rate limit exceeded
        CostLimitExceededError: If cost limit exceeded
        ValueError: If request is invalid
        Exception: For OpenAI API errors
    """
    try:
        # Use unified OpenAI service (automatic rate limiting + cost tracking)
        service = get_openai_service()

        response = service.chat_completion(
            messages=messages,
            user_id=user_id,
            model=CONVERSATION_MODEL,
            temperature=0.7,
            max_tokens=800,
            timeout=30.0,
            require_json=require_json,
        )

        # Convert to expected format (backward compatibility)
        usage_info = {
            **response.usage,
            "model": response.model,
            "cost": response.cost,  # Include cost from service response
        }

        return response.content, usage_info

    except RateLimitExceededError as e:
        # Re-raise with original error (caller should handle)
        raise
    except CostLimitExceededError as e:
        # Re-raise with original error (caller should handle)
        raise
    except Exception as e:
        print(f"GPT conversation API call failed: {e}")
        # Return error in same format as before for backward compatibility
        return f"[ERROR] GPT error: {e}", {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": CONVERSATION_MODEL,
            "cost": 0.0,  # Include cost for consistency
        }


async def get_conversation_response_async(
    messages: List[Dict],
    user_id: str,
    require_json: bool = False,
) -> Tuple[str, Dict]:
    """
    Async version of GPT conversation response.

    NOTE: Currently uses synchronous service (OpenAIService is sync).
    For true async support, OpenAIService would need async implementation.
    This maintains backward compatibility but delegates to sync service.

    TODO: Implement async version of OpenAIService if needed for performance.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        user_id: User identifier (REQUIRED for security tracking)
        require_json: If True, enforces JSON response format

    Returns:
        Tuple of (content: str, usage_info: Dict) - matches sync version for consistency
    """
    # For now, delegate to sync version (maintains consistency)
    # In the future, if async performance is critical, implement async OpenAIService
    return get_conversation_response(
        messages=messages,
        user_id=user_id,
        require_json=require_json,
    )


def get_gpt_response(prompt: str, user_id: str, require_json: bool = True) -> str:
    """
    Calls GPT with a generic coaching prompt. Returns plain text.

    Uses unified OpenAIService with automatic rate limiting and cost tracking.

    Args:
        prompt: The user prompt to send to GPT
        user_id: User identifier (REQUIRED for security tracking)
        require_json: If True, enforces JSON response format (default). Set to False for plain text responses.

    Returns:
        Response content as string

    Raises:
        RateLimitExceededError: If rate limit exceeded
        CostLimitExceededError: If cost limit exceeded
        ValueError: If request is invalid
        Exception: For OpenAI API errors
    """
    try:
        # Use unified OpenAI service (automatic rate limiting + cost tracking)
        service = get_openai_service()

        response = service.chat_completion(
            messages=[
                {"role": "system", "content": JACK_DANIELS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            user_id=user_id,
            model=DEFAULT_MODEL,
            temperature=0.25,
            timeout=60.0,
            require_json=require_json,
        )

        return response.content

    except (RateLimitExceededError, CostLimitExceededError):
        # Re-raise security errors (caller should handle)
        raise
    except Exception as e:
        print(f"GPT API call failed: {e}")
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
