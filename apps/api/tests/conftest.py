"""pytest configuration for BehaviorTrade API tests.

Sets the working directory so imports like `from app.xyz` resolve correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the api package root is on sys.path so `from app.xyz` works
_API_ROOT = Path(__file__).parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))
