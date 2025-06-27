# src/utils/gpt_ops.py

def format_prompt(user_question: str, activities: list[dict]) -> str:
    """
    Format a prompt string for GPT using the user's question and a list of activity records.

    Args:
        user_question (str): The question posed by the user.
        activities (list[dict]): Cleaned activity data fetched from DB.

    Returns:
        str: A structured prompt string for GPT input.
    """
    header = "You are a smart coaching assistant. Answer the question using only the provided data."
    activity_section = "\n\nACTIVITIES:\n"

    for i, activity in enumerate(activities, start=1):
        summary = f"[{i}] " + ", ".join([
            f"{k}: {v}" for k, v in activity.items() if v is not None
        ])
        activity_section += summary + "\n"

    question_section = f"\nUSER QUESTION:\n{user_question.strip()}\n"

    return f"{header}{activity_section}{question_section}"
