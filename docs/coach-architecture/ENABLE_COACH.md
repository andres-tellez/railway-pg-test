# Enable the New Coach System

## Quick Start

To use the new Coach system in the app, set this environment variable:

```bash
COACH_V2_ENABLED=true
```

## How It Works

When enabled, the existing conversation endpoint (`/api/conversations/<conversation_id>/messages`) will automatically use the new Coach system instead of the old one.

**No changes to the frontend needed!** It uses the same API endpoint you're already using.

## Enable for Testing

### Option 1: Set in .env.local

Add to your `.env.local` file:

```
COACH_V2_ENABLED=true
```

Then restart your Flask server.

### Option 2: Set as Environment Variable

```bash
# Windows PowerShell
$env:COACH_V2_ENABLED="true"

# Linux/Mac
export COACH_V2_ENABLED=true
```

### Option 3: Set in Railway/Production

Set the environment variable in your Railway project settings.

## What Happens

When `COACH_V2_ENABLED=true`:

1. Your questions go through the new Coach system:
   - Intent classification
   - Safety scanning
   - RunnerState building
   - QuestionContext building
   - Smart prompt building
   - LLM response
   - Response formatting

2. The response format is the same (backward compatible)

3. If the new system fails, it automatically falls back to the old system

## Test It Now

1. Set `COACH_V2_ENABLED=true` in your environment
2. Restart your Flask server
3. Open the app and ask the coach a question (use the normal UI)
4. Check the logs - you should see "Coach metadata: intent=..." messages

## Example Questions to Test

- "How did my run go yesterday?" (workout_review)
- "What's my plan for this week?" (this_week_plan)
- "How am I doing?" (progress_check)
- "I have knee pain" (injury_or_symptom - should trigger safety flags)

## Disable

Set `COACH_V2_ENABLED=false` or remove the variable to go back to the old system.
