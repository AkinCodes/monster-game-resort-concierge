"""
Structured Output Extraction
==============================

Extracts valid JSON from raw LLM text. Uses the stdlib JSON parser
to find boundaries instead of regex guessing.
"""

from __future__ import annotations

import json


class StructuredOutputParser:
    """Extracts JSON from messy LLM responses."""

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract the first valid JSON value from LLM text.

        Uses json.JSONDecoder.raw_decode() instead of regex so the
        actual JSON parser determines where the value ends. This
        correctly handles nested braces, escaped characters, prose
        around the JSON, and markdown fences — without guessing.
        """
        start_obj = text.find("{")
        start_arr = text.find("[")
        candidates = [s for s in (start_obj, start_arr) if s != -1]

        if not candidates:
            return text.strip()

        decoder = json.JSONDecoder()
        for i in range(min(candidates), len(text)):
            if text[i] not in ("{", "["):
                continue
            try:
                obj, end = decoder.raw_decode(text[i:])
                return json.dumps(obj)
            except json.JSONDecodeError:
                continue

        return text.strip()
