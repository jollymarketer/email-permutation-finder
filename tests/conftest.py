"""Shared pytest config. Adds the repo root to sys.path."""

import sys
from pathlib import Path

# Make permutation_finder.py, _permutations.py, _mv_client.py importable
sys.path.insert(0, str(Path(__file__).parent.parent))
