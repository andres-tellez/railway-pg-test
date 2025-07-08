import openai
import os
from datetime import datetime

openai.api_key = os.getenv("OPENAI_API_KEY")


def parse_date_safe(date_str: str) -> datetime:
    """
    Parses a date string that may or may not include time.
    Accepts formats like '2025-06-24' or '2025-06-24 13:45:00'
    """
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {date_str}")


def format_prompt(user_question: str, activities: list[dict]) -> str:
    """
    Format a prompt string for GPT using the user's question and a list of activity records.
    Always returns structured prompt for coaching assistant, even if empty input.
    """
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
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful fitness assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        import traceback
        print("GPT API call failed:", e)
        traceback.print_exc()
        return f"❌ GPT error: {e}"
