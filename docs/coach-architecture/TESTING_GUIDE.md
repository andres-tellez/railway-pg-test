# Testing the Coach System

## Test Endpoint

The Coach system is available at:

```
POST /api/coach/test
```

## Request Format

```json
{
  "question": "How did my run go yesterday?",
  "conversation_history": []  // Optional
}
```

## Response Format

```json
{
  "response": "Formatted response from coach",
  "metadata": {
    "intent": "workout_review",
    "intent_confidence": 0.95,
    "safety_flags": [],
    "safety_has_red_flag": false,
    "safety_severity": null,
    "response_sections": {},
    "response_warnings": [],
    "response_is_valid": true
  },
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "cost": 0.001,
    "model": "gpt-4o"
  }
}
```

## Example: Using curl

```bash
curl -X POST http://localhost:5000/api/coach/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "question": "How did my run go yesterday?"
  }'
```

## Example: Using Python requests

```python
import requests

url = "http://localhost:5000/api/coach/test"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "question": "How did my run go yesterday?"
}

response = requests.post(url, json=data, headers=headers)
result = response.json()

print("Response:", result["response"])
print("Intent:", result["metadata"]["intent"])
print("Cost:", result["usage"]["cost"])
```

## Example Questions to Test

1. **Workout Review:**
   - "How did my run go yesterday?"
   - "Tell me about my long run last week"

2. **This Week Plan:**
   - "What's my plan for this week?"
   - "What should I run this week?"

3. **Progress Check:**
   - "How am I doing?"
   - "How is my training going?"

4. **Injury/Symptom:**
   - "I have knee pain when running"
   - "My chest hurts during runs"

5. **General Education:**
   - "What is VO2 max?"
   - "Explain heart rate zones"

6. **Motivation:**
   - "I need motivation to keep going"
   - "Help me stay motivated"

## Components Used

The test endpoint orchestrates all Coach components:

1. **IntentClassifier** - Classifies user intent
2. **SafetyScanner** - Detects safety flags
3. **RunnerStateBuilder** - Builds runner state
4. **QuestionContextBuilder** - Builds question context
5. **CoachPromptBuilder** - Builds LLM prompt
6. **LLMClient** - Gets LLM response
7. **ResponseFormatter** - Formats response

## Troubleshooting

- **401 Unauthorized**: Make sure you have a valid JWT token
- **500 Error**: Check server logs for details
- **Rate Limit**: Check usage limits in response metadata
