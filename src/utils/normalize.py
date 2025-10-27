import re


def normalize_postgres_row(row: dict) -> dict:
    """
    Normalize PostgreSQL row fields for JSON serialization:
    - Convert enum types to strings
    - Convert Postgres-style array strings (like '{A,B}') to Python lists
    - Leave native lists untouched
    - Filter out SQLAlchemy internal fields
    """
    import uuid
    from enum import Enum

    normalized = {}

    for key, val in row.items():
        # Skip SQLAlchemy internal fields
        if key.startswith("_sa_"):
            continue

        # Convert enum objects to their values
        if isinstance(val, Enum):
            normalized[key] = val.value
        # Convert UUID objects to strings
        elif isinstance(val, uuid.UUID):
            normalized[key] = str(val)
        # Convert lists of enums/UUIDs
        elif isinstance(val, list):
            normalized[key] = [
                (
                    item.value
                    if isinstance(item, Enum)
                    else str(item) if isinstance(item, uuid.UUID) else str(item)
                )
                for item in val
            ]
        # Convert Postgres array strings (e.g., "{A,B}")
        elif isinstance(val, str) and val.startswith("{") and val.endswith("}"):
            items = val.strip("{}").split(",")
            normalized[key] = [item.strip('"') for item in items if item]
        else:
            normalized[key] = val

    return normalized


def strip_enum_prefix(value: str) -> str:
    """
    Converts 'EnumName.Value' → 'Value', and logs what it's doing.
    """
    print(f"   > Stripping enum prefix from: {value}")
    return value.split(".")[-1] if isinstance(value, str) else value
