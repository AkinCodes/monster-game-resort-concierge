"""
Prompt Loader — loads prompt templates from YAML files.

Keeps prompts out of Python source and in version-controlled YAML files
under the ``prompts/`` directory. Loaded prompts are cached in memory so
each file is read at most once per process.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Default prompts directory: <project_root>/prompts/
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache(maxsize=64)
def _load_yaml(file_path: str) -> dict[str, Any]:
    """Read and parse a YAML file, cached by absolute path."""
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def load_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt template and apply variable substitution.

    ``name`` uses dot-notation to address nested keys:
      - ``"planner"``            -> prompts/planner.yaml  -> data["prompt"]
      - ``"executor.knowledge"`` -> prompts/executor.yaml -> data["knowledge"]["prompt"]

    Keyword arguments are substituted into the template using
    ``str.format_map``, so templates should use ``{variable}`` placeholders.
    Double braces ``{{`` / ``}}`` are preserved literally (useful for JSON
    examples inside prompts).
    """
    parts = name.split(".")
    file_name = parts[0]
    yaml_path = str(_PROMPTS_DIR / f"{file_name}.yaml")

    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Prompt file not found: {yaml_path}")

    data = _load_yaml(yaml_path)

    # Navigate into nested keys (e.g. "executor.knowledge" -> data["knowledge"])
    node = data
    for key in parts[1:]:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"Prompt key '{key}' not found in {file_name}.yaml")
        node = node[key]

    # The final node should either be a string or a dict with a "prompt" key
    if isinstance(node, dict):
        template = node.get("prompt")
        if template is None:
            raise KeyError(f"No 'prompt' key in {name}")
    elif isinstance(node, str):
        template = node
    else:
        raise TypeError(f"Unexpected type for prompt '{name}': {type(node)}")

    template = template.strip()

    if kwargs:
        return template.format_map(kwargs)
    return template
