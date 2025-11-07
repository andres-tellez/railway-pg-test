# AI Guardrails

## GPT Architecture - DO NOT DEVIATE

### Current Process Flow

1. **User asks question** → Frontend sends to Flask backend
2. **SmartDataService** → Analyzes question and fetches relevant data from database
3. **Data sent to GPT** → GPT receives structured data and answers naturally
4. **GPT response** → Returns to user through Flask backend

### Critical Rules - NEVER CHANGE

- **SmartDataService**: ONLY fetches data from database using natural language understanding
- **GPT Operations**: ONLY calls GPT API with the data provided
- **NO SQL generation**: GPT does NOT generate SQL queries
- **NO approach changes**: Do NOT switch to different architectural patterns without explicit permission

### What Each Component Does

- **SmartDataService**: Determines what data to fetch based on question keywords, returns structured data
- **GPT**: Receives data and answers questions naturally using the provided data
- **Database Views**: Provide clean data access (v_completed_activities, v_planned_activities, user_profile)

### When Making Changes

1. **ALWAYS confirm current approach first**
2. **Explain why change is needed**
3. **Get explicit approval before proceeding**
4. **Maintain separation of concerns**

## Clarifying Questions Feature

### How It Works

- **Vague questions** (e.g., "How am I doing?") → GPT asks clarifying questions
- **Clear questions** (e.g., "What's my race date?") → GPT answers directly
- **Question analysis** provided by SmartDataService to GPT
- **GPT uses context** to ask targeted clarifying questions

### Implementation

- SmartDataService analyzes question clarity
- Provides available data context to GPT
- GPT follows system prompt for vague vs clear questions
- Maintains helpful, encouraging tone

## CRITICAL GUARDRAILS - NEVER VIOLATE

### ❌ DO NOT: Over-Engineer Question Categorization

- **NEVER** try to pre-categorize or pre-filter questions for GPT
- **NEVER** create keyword matching systems for question types
- **NEVER** try to "optimize" by giving GPT less data
- **NEVER** assume GPT needs help understanding natural language

### ✅ DO: Trust GPT's Natural Language Capabilities

- **ALWAYS** provide comprehensive, clean data to GPT
- **ALWAYS** let GPT decide what data to use for each question
- **ALWAYS** focus on data quality and structure, not question categorization
- **ALWAYS** remember: GPT is designed for natural language understanding

### Why This Matters

- GPT's strength is natural language understanding - don't work against it
- Pre-filtering data actually makes GPT less capable
- Keyword matching is unnecessary complexity that limits flexibility
- Simple + comprehensive data = better results than complex + filtered data

### Red Flags to Watch For

- "Let's add keyword matching for..."
- "We should pre-filter data based on question type..."
- "Let's optimize by only sending relevant data..."
- "We need to categorize questions before sending to GPT..."

## Future Sections

- [ ] Database Architecture
- [ ] Frontend Integration
- [ ] Error Handling
- [ ] Performance Optimization
