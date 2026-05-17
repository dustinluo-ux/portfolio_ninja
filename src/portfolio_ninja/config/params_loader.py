from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "params.yaml"
_REQUIRED_SECTIONS = {"market_state", "scoring", "portfolio", "risk", "data", "date_normalizer"}

_cache: dict[str, Any] | None = None


def load_params(path: Path | None = None) -> dict[str, Any]:
    """Read params.yaml, validate required sections, return raw dict.

    Caches the result for the default path. Pass a custom path to bypass cache
    (useful in tests that need isolated parameter sets).

    Raises FileNotFoundError if path is missing.
    Raises KeyError if any required section is absent.
    Raises ValueError if the YAML root is not a mapping.
    """
    global _cache
    if path is None and _cache is not None:
        return _cache

    resolved = path or _DEFAULT_PATH
    if not resolved.exists():
        raise FileNotFoundError(f"params.yaml not found: {resolved}")

    with open(resolved, encoding="utf-8") as f:
        raw: Any = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"params.yaml must be a YAML mapping, got {type(raw).__name__}")

    missing = _REQUIRED_SECTIONS - raw.keys()
    if missing:
        raise KeyError(f"params.yaml missing required sections: {sorted(missing)}")

    if path is None:
        _cache = raw
    return raw
