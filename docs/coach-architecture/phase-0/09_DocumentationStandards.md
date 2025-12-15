# Documentation Standards

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

This document defines documentation standards for the Coach architecture codebase. All code must follow these standards to ensure maintainability and clarity.

## Core Principles

1. **Self-Documenting Code**: Code should be readable without excessive comments
2. **Comprehensive Docstrings**: Public APIs must have complete docstrings
3. **Explanation of Why**: Comments explain "why", not "what"
4. **Keep Docs Updated**: Documentation must stay in sync with code
5. **Accessible**: Documentation should be easily findable and navigable

## Docstring Standards

### Format

Use **Google-style** docstrings:

```python
def function_name(param1: str, param2: int) -> dict:
    """
    Brief one-line description.

    Longer description if needed. This can span multiple lines
    and provide additional context about what the function does,
    why it exists, and how it fits into the larger system.

    Args:
        param1: Description of param1. Include type, constraints,
            and example values if helpful.
        param2: Description of param2.

    Returns:
        Description of return value. Include structure if it's
        a dict or complex object.

    Raises:
        ValueError: When this specific error occurs and why.
        RuntimeError: When this happens and what it means.

    Example:
        >>> result = function_name("example", 42)
        >>> print(result["key"])
        "value"
    """
    pass
```

### Class Docstrings

```python
class ComponentName:
    """
    Brief description of the component.

    Longer description explaining:
    - What this component does
    - When to use it
    - Key responsibilities
    - Important invariants or constraints

    Attributes:
        attr1: Description of attribute
        attr2: Description of attribute

    Example:
        >>> component = ComponentName()
        >>> result = component.method()
    """

    def __init__(self, param: str):
        """
        Initialize component.

        Args:
            param: Description of initialization parameter
        """
        self.attr1 = param
```

### Module-Level Docstrings

```python
"""
Module: coach.builders.runner_state_builder

Purpose:
    Builds the canonical RunnerState object for a user, including
    phase, week, zones, metrics, and patterns.

Key Components:
    - RunnerStateBuilder: Main builder class
    - RaceInfoBuilder: Extracts race information
    - ZoneCalculator: Calculates pace and HR zones
    - PatternAnalyzer: Detects training patterns

Usage:
    >>> builder = RunnerStateBuilder(user_id)
    >>> state = builder.build()
    >>> print(state["phase"])
    "Build"

Author: Engineering Team
Last Updated: 2025-01-15
"""
```

## Comment Standards

### When to Comment

**DO comment:**
- Complex algorithms or business logic
- Non-obvious decisions and trade-offs
- Workarounds for known issues
- Performance optimizations
- Safety considerations

**DON'T comment:**
- Obvious code (`x = x + 1  # Increment x`)
- What the code does (code should be self-explanatory)
- Outdated information (delete old comments)

### Comment Style

```python
# Good: Explains WHY
# We use hash-based routing instead of random assignment to ensure
# deterministic user experience across requests
shadow_bucket = hash(user_id) % 100

# Bad: Explains WHAT (obvious)
# Calculate shadow bucket by hashing user ID
shadow_bucket = hash(user_id) % 100

# Good: Explains complex logic
# The compression priority ensures we keep the most critical data
# even when hitting token limits. Race context is always preserved
# because it's small but essential for coaching advice.
if tokens > max_tokens:
    compress_by_priority(context, keep=["race_context", "zones"])

# Good: Explains workaround
# TODO: Remove this workaround when OpenAI fixes token counting
# Issue: https://github.com/openai/openai-python/issues/123
estimated_tokens = len(text) // 4  # Approximate, actual count differs
```

### TODO Comments

```python
# TODO(username): Description of work needed
# FIXME(username): Description of bug to fix
# NOTE(username): Important note about implementation
# HACK(username): Temporary workaround that should be fixed
```

## Documentation Files

### Architecture Documentation

**Location**: `docs/coach-architecture/`

**Requirements**:
- Document all major components
- Include diagrams (if helpful)
- Explain data flows
- Document interfaces

**Example Structure**:
```
docs/coach-architecture/
  README.md                    # Overview
  architecture.md              # High-level architecture
  components/
    runner_state_builder.md
    llm_client.md
    ...
  phase-0/
    [Phase 0 specs]
  phase-1/
    [Phase 1 specs]
```

### API Documentation

**Location**: `docs/api/` or inline in code (Sphinx)

**Requirements**:
- Document all public APIs
- Include request/response examples
- Document error codes
- Include authentication requirements

### README Files

**Location**: Root and component directories

**Requirements**:
- Project overview
- Setup instructions
- Usage examples
- Contribution guidelines

**Example**:
```markdown
# Coach Architecture

AI-powered running coach system.

## Setup

1. Install dependencies
2. Configure environment variables
3. Run tests

## Usage

[Examples]

## Architecture

See docs/coach-architecture/ for details.
```

## Code Documentation Requirements

### Required Documentation

1. **All public functions**: Docstrings
2. **All classes**: Class docstrings
3. **All modules**: Module docstrings
4. **Complex logic**: Inline comments
5. **Configuration**: Config file comments

### Optional Documentation

1. Private functions: Docstrings (if helpful)
2. Simple functions: Brief docstrings
3. Test files: Test purpose documentation

## Documentation Maintenance

### When to Update Docs

Update documentation when:
- Adding new components
- Changing public APIs
- Modifying architecture
- Changing configuration
- Fixing bugs (update relevant docs)

### Documentation Review

- Include docs in PR review
- Verify examples still work
- Check for outdated information
- Ensure consistency

## Examples

### Good Documentation

```python
class RunnerStateBuilder:
    """
    Builds the canonical RunnerState object for a user.

    The RunnerState object represents the complete training state
    of a runner, including their current phase, weekly metrics,
    pace/HR zones, and detected patterns. This object is cached
    and reused across multiple coaching conversations to ensure
    consistency and reduce computation.

    Attributes:
        user_id: User identifier
        cache_ttl: Cache time-to-live in seconds (default: 86400)
    """

    def build(self) -> dict:
        """
        Build RunnerState object.

        Fetches and aggregates data from multiple sources:
        - User profile (race info, goals)
        - Training plan (phase, week)
        - Activities (metrics, patterns)
        - System calculations (zones, fatigue indicators)

        Returns:
            RunnerState dict with schema version 1.0.0.
            Structure:
            {
                "version": "1.0.0",
                "runner_state": {
                    "phase": str,
                    "week_of_block": int,
                    "zones": {...},
                    "weekly_metrics": {...},
                    "patterns": {...}
                }
            }

        Raises:
            RunnerStateBuilderError: If required data is missing
            DatabaseError: If database query fails

        Example:
            >>> builder = RunnerStateBuilder(user_id="abc123")
            >>> state = builder.build()
            >>> print(state["runner_state"]["phase"])
            "Build"
        """
        # Implementation
        pass
```

### Bad Documentation

```python
class RunnerStateBuilder:
    """Builds runner state."""  # Too brief, no context

    def build(self):
        """Builds state."""  # Doesn't explain what, why, or how
        # No docstring details
        pass
```

## Documentation Tools

### Recommended Tools

- **Sphinx**: For API documentation generation
- **MkDocs**: For markdown-based documentation
- **Type Hints**: For inline type documentation
- **Docstring Linters**: `pydocstyle` for style checking

### Documentation Generation

```bash
# Generate API docs from docstrings
sphinx-build -b html docs/ docs/_build/html

# Check docstring style
pydocstyle coach/
```

## Checklist for New Code

When adding new code, ensure:

- [ ] Public functions have docstrings
- [ ] Classes have class docstrings
- [ ] Complex logic has comments
- [ ] Module has module docstring
- [ ] Examples included (if helpful)
- [ ] Error cases documented
- [ ] Architecture docs updated (if major component)
- [ ] README updated (if setup changes)

## Related Documents

- `docs/coach-architecture/phase-0/CodingAgent_Execution_Guide.md` - Agent workflow
- `docs/coach-architecture/phase-0/HumanReviewChecklist.md` - Review process
