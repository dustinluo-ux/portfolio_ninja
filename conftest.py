"""Root conftest — ensures the project root is on sys.path for src.* imports."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root (parent of src/) so that `from src.portfolio_ninja...` works.
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
