import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "tools"))
