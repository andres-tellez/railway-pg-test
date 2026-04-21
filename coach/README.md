# Coach Architecture

**Not the production mobile Coach tab agent.** This package (`coach/`) and `tests/coach/` are the **experimental / v2** modular coach stack. For the **shipped** Flask chat agent (`src/smartcoach_mobile_coach/`), see **`docs/SMARTCOACH_SYSTEM_SPEC_V1.md`** (product and LLM boundary) and **`docs/API_DOCUMENTATION.md`** (HTTP contract).

---

AI-powered running coach system with modular architecture.

## Structure

```
coach/
├── builders/          # State and context builders
├── utils/             # Utilities (schema validation, error handling, config)
├── llm/               # LLM client and prompt building
├── safety/            # Safety scanner
└── __init__.py
```

## Components

### Builders (`coach/builders/`)

- `RunnerStateBuilder`: Builds canonical runner state
- `QuestionContextBuilder`: Builds intent-specific context
- `ActivitySummarizer`: Compresses activity data
- `ContextCompressor`: Manages token limits

### Utilities (`coach/utils/`)

- `schema_validator.py`: JSON schema validation
- `error_handler.py`: Centralized error handling
- `config.py`: Configuration management
- `metrics.py`: Metrics client (to be implemented)

### LLM (`coach/llm/`)

- `llm_client.py`: Centralized LLM access (to be implemented)
- `prompt_builder.py`: Prompt assembly (to be implemented)

### Safety (`coach/safety/`)

- `safety_scanner.py`: Medical red flag detection (to be implemented)

## Usage

```python
from coach.utils.schema_validator import SchemaValidator
from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity

# Validate data
try:
    SchemaValidator.validate_runner_state(runner_state)
except SchemaValidationError as e:
    print(f"Validation failed: {e}")

# Handle errors
try:
    result = risky_operation()
except Exception as e:
    CoachErrorHandler.handle(
        error=e,
        severity=ErrorSeverity.HIGH,
        component="MyComponent",
        user_id="user-123"
    )
```

## Testing

See `tests/README.md` for testing guidelines.

## Configuration

Configuration is loaded from:
- Environment variables (see `coach/utils/config.py`)
- YAML files in `config/` directory

## Documentation

Experimental stack: read code and tests under `coach/` and `tests/coach/`. Product-wide rules for the shipped app live in `docs/SMARTCOACH_SYSTEM_SPEC_V1.md`.
