from __future__ import annotations

import hashlib
import json
import re
from typing import TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | dict[str, "JsonValue"] | list["JsonValue"]


def normalize_hash_value(value: JsonValue) -> JsonValue:
    """Normalize a value into a deterministic representation for hashing."""
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip().lower())
    if isinstance(value, dict):
        return {key: normalize_hash_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_hash_value(item) for item in value]
    return value


def stable_sha256(payload: dict[str, JsonValue]) -> str:
    """Return a stable SHA-256 hash for a dictionary payload."""
    normalized = normalize_hash_value(payload)
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
