import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "tools"))

import journal  # noqa: E402  (после правки sys.path)


def missing_evidence_roots() -> list[str]:
    """Корни улик из `default_roots()` (свои префиксы и `tools/journal-roots.json`),
    которых на этой машине нет: `префикс -> путь`."""
    return [f"{prefix} -> {path}" for prefix, path in journal.default_roots().items() if not path.exists()]


# Тест на настоящем журнале и настоящих корнях: на машине без корней — пропуск, не красное.
requires_evidence_roots = pytest.mark.skipif(
    bool(missing_evidence_roots()),
    reason="на этой машине нет корней улик: " + "; ".join(missing_evidence_roots()))


FORK_BIN = ROOT / "upstream" / "openspec" / "bin" / "openspec.js"
FORK_DIST = ROOT / "upstream" / "openspec" / "dist" / "cli" / "index.js"


def fork_unavailable() -> str:
    """Почему CLI форка на этой машине не запустить; пустая строка — можно."""
    if shutil.which("node") is None:
        return "нет node в PATH"
    if not FORK_BIN.exists():
        return f"нет {FORK_BIN.relative_to(ROOT).as_posix()}: форк не клонирован (upstream/ в .gitignore)"
    if not FORK_DIST.exists():
        return f"форк не собран: нет {FORK_DIST.relative_to(ROOT).as_posix()} (pnpm build в upstream/openspec)"
    return ""


# Тест через CLI форка: без node или без собранного форка — пропуск, не красное.
requires_fork = pytest.mark.skipif(bool(fork_unavailable()), reason=fork_unavailable() or "форк на месте")


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
