"""Manifest loader — parse and validate domekit.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from contracts.manifest import Manifest


def load_manifest(path: str) -> Manifest:
    """Load a domekit.yaml file and return a validated Manifest."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a YAML mapping, got {type(data).__name__}")

    return Manifest(**data)
