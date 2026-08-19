"""
Lenient JSON extraction — Phase 5.

Local models don't reliably return bare JSON — they wrap it in
```json fences, add a sentence of preamble, etc. This pulls the
first well-formed JSON array (or single object) out of raw text.

Full malformed-JSON *recovery* (retries, repair heuristics) is
explicitly Phase 20's job — this is just enough leniency to handle
the common formatting noise from Phase 5 onward.
"""
from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array of objects from a model's raw response text."""
    candidate = text.strip()

    fence_match = _FENCE_RE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()

    # Direct parse first (covers the well-behaved case).
    try:
        parsed = json.loads(candidate)
        return _coerce_to_list(parsed)
    except json.JSONDecodeError:
        pass

    # Fall back to slicing out the first '[' ... last ']' in the text.
    start = candidate.find("[")
    end = candidate.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(candidate[start : end + 1])
            return _coerce_to_list(parsed)
        except json.JSONDecodeError:
            pass

    # Last resort: a single '{' ... '}' object instead of an array.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(candidate[start : end + 1])
            return _coerce_to_list(parsed)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from judge response: {text[:200]!r}")


def _coerce_to_list(parsed) -> list[dict]:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    raise ValueError(f"Expected a JSON array or object, got {type(parsed).__name__}")