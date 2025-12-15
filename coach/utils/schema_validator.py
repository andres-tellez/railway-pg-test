"""
Schema validation utilities.

Validates data against JSON schemas defined in schemas/ directory.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import jsonschema
from jsonschema import validate, ValidationError


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""

    pass


class SchemaValidator:
    """Validates data against JSON schemas."""

    SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"

    _cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_schema(cls, schema_name: str, version: str = "1_0") -> Dict[str, Any]:
        """
        Load schema from schemas directory.

        Args:
            schema_name: Name of schema (e.g., "runner_state")
            version: Schema version (e.g., "1_0" for v1.0.0)

        Returns:
            Schema dict

        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema is invalid JSON
        """
        cache_key = f"{schema_name}_{version}"

        if cache_key not in cls._cache:
            schema_file = cls.SCHEMAS_DIR / f"{schema_name}_v{version}.json"

            if not schema_file.exists():
                raise FileNotFoundError(f"Schema not found: {schema_file}")

            with open(schema_file, "r") as f:
                cls._cache[cache_key] = json.load(f)

        return cls._cache[cache_key]

    @classmethod
    def validate_runner_state(cls, data: Dict[str, Any]) -> bool:
        """
        Validate RunnerState data against schema.

        Args:
            data: RunnerState data dict

        Returns:
            True if valid

        Raises:
            SchemaValidationError: If validation fails
        """
        # Convert "1.0.0" to "1_0" for filename (major_minor only)
        version_str = data.get("version", "1.0.0")
        version_parts = version_str.split(".")
        version = (
            f"{version_parts[0]}_{version_parts[1]}"
            if len(version_parts) >= 2
            else "1_0"
        )
        schema = cls.load_schema("runner_state", version)

        try:
            validate(instance=data, schema=schema)
            return True
        except ValidationError as e:
            raise SchemaValidationError(
                f"RunnerState validation failed: {e.message}"
            ) from e

    @classmethod
    def validate_question_context(cls, data: Dict[str, Any]) -> bool:
        """
        Validate QuestionContext data against schema.

        Args:
            data: QuestionContext data dict

        Returns:
            True if valid

        Raises:
            SchemaValidationError: If validation fails
        """
        # Convert "1.0.0" to "1_0" for filename (major_minor only)
        version_str = data.get("version", "1.0.0")
        version_parts = version_str.split(".")
        version = (
            f"{version_parts[0]}_{version_parts[1]}"
            if len(version_parts) >= 2
            else "1_0"
        )
        schema = cls.load_schema("question_context", version)

        try:
            validate(instance=data, schema=schema)
            return True
        except ValidationError as e:
            raise SchemaValidationError(
                f"QuestionContext validation failed: {e.message}"
            ) from e

    @classmethod
    def validate_proactive_insights(cls, data: Dict[str, Any]) -> bool:
        """
        Validate ProactiveInsights data against schema.

        Args:
            data: ProactiveInsights data dict

        Returns:
            True if valid

        Raises:
            SchemaValidationError: If validation fails
        """
        # Convert "1.0.0" to "1_0" for filename (major_minor only)
        version_str = data.get("version", "1.0.0")
        version_parts = version_str.split(".")
        version = (
            f"{version_parts[0]}_{version_parts[1]}"
            if len(version_parts) >= 2
            else "1_0"
        )
        schema = cls.load_schema("proactive_insights", version)

        try:
            validate(instance=data, schema=schema)
            return True
        except ValidationError as e:
            raise SchemaValidationError(
                f"ProactiveInsights validation failed: {e.message}"
            ) from e

    @classmethod
    def validate_safety_flags(cls, data: Dict[str, Any]) -> bool:
        """
        Validate SafetyFlags data against schema.

        Args:
            data: SafetyFlags data dict

        Returns:
            True if valid

        Raises:
            SchemaValidationError: If validation fails
        """
        # Convert "1.0.0" to "1_0" for filename (major_minor only)
        version_str = data.get("version", "1.0.0")
        version_parts = version_str.split(".")
        version = (
            f"{version_parts[0]}_{version_parts[1]}"
            if len(version_parts) >= 2
            else "1_0"
        )
        schema = cls.load_schema("safety_flags", version)

        try:
            validate(instance=data, schema=schema)
            return True
        except ValidationError as e:
            raise SchemaValidationError(
                f"SafetyFlags validation failed: {e.message}"
            ) from e
