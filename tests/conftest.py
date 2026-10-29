import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "tools"))


def one_record_journal(path: str, quote: str) -> dict:
    """Минимальный годный журнал: одна развилка, один вариант, одна улика."""
    evidence = {"path": path, "quote": quote}
    option = {"letter": "A", "text": "вариант", "added": False, "unlikely": None, "evidence": [evidence]}
    record = {"id": "F-01", "question": "вопрос?", "kind": "развилка", "status": "открыт",
              "addressee": "", "depends_on": [], "delivery": "", "options": [option],
              "antipodes": [], "recommendation": None, "decision": None, "reversibility": None,
              "outcome": None, "parking": [], "dispute": "", "consequences": "",
              "evidence": [], "comments": []}
    return {"title": "т", "source": "s.md", "records": [record]}
