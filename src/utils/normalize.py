import re


def normalize_postgres_row(row: dict) -> dict:
    """
    Normalize PostgreSQL row fields for JSON serialization:
    - Convert enum types to strings
    - Convert Postgres-style array strings (like '{A,B}') to Python lists
    - Leave native lists untouched
    """
    print("🔍 normalize_postgres_row called with:")
    print(row)

    normalized = {}

    for key, val in row.items():
        print(f"  → {key}: {val} ({type(val)})")

        if isinstance(val, list):
            normalized[key] = [str(item) for item in val]
        elif isinstance(val, str) and val.startswith("{") and val.endswith("}"):
            # Postgres array string (e.g., "{A,B}")
            items = val.strip("{}").split(",")
            normalized[key] = [item.strip('"') for item in items if item]
        else:
            normalized[key] = val

    print("✅ Normalized result:", normalized)
    return normalized


def strip_enum_prefix(value: str) -> str:
    """
    Converts 'EnumName.Value' → 'Value', and logs what it's doing.
    """
    print(f"   > Stripping enum prefix from: {value}")
    return value.split(".")[-1] if isinstance(value, str) else value
