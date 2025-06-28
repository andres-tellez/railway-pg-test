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
    """
    header = "You are a smart coaching assistant. Answer the question using only the provided data."
    activity_section = "\n\nACTIVITIES:\n"

    # Define date range
    start_date = datetime(2025, 6, 23).date()
    end_date = datetime(2025, 6, 26).date()

    # Filter activities based on parsed dates
    filtered_activities = []
    for activity in activities:
        try:
            activity_date = parse_date_safe(activity.get('start_date', '')).date()
            if start_date <= activity_date <= end_date:
                filtered_activities.append(activity)
        except ValueError:
            continue  # skip invalid dates

    if not filtered_activities:
        return "No activities found for the selected date range."

    for i, activity in enumerate(filtered_activities, start=1):
        summary = f"[{i}] Date: {activity['start_date']}, Distance: {activity['conv_distance']} miles, Duration: {activity.get('duration', 'N/A')}"
        activity_section += summary + "\n"

    question_section = f"\nUSER QUESTION:\n{user_question.strip()}\n"

    clarification_prompt = (
        "Please provide a detailed breakdown for the total distance calculation, "
        "explaining which activities contributed to the total distance. "
        "Include both the individual activity distances in miles, along with the running time for each activity. "
        "Do not perform any conversion from kilometers to miles. Use the provided `conv_distance` values."
    )

    return f"{header}{activity_section}{question_section}{clarification_prompt}"

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
