"""Pytest configuration: make src/extract importable as top-level modules.

energy_charts.py and weather.py both do `from common import ...`, so
common.py, energy_charts.py, and weather.py must be importable without a
package prefix. Place this file at the repo root (or adjust the path below
to point at src/extract).
"""

import sys
from pathlib import Path

EXTRACT_DIR = Path(__file__).parent.parent.parent / "src" / "extract"
sys.path.insert(0, str(EXTRACT_DIR))
