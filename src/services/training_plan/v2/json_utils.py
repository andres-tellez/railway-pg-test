from datetime import date, datetime
from decimal import Decimal


def to_json_safe(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def make_json_safe(data):
    import json

    return json.loads(json.dumps(data, default=to_json_safe))
