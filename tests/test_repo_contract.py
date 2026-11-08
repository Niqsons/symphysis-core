"""Контракт с плагином: раздел о хуке описан, строки «когда появится» нет (F-35)."""
import journal_render
from conftest import ROOT

CONTRACT = ROOT / "docs" / "repo-contract.md"


def text():
    return CONTRACT.read_text(encoding="utf-8")


def test_scenario_no_more_when_it_appears_line():
    """Сценарий «Строки «когда появится» больше нет»: строки нет, раздел называет `events.jsonl`."""
    body = text()
    assert "когда появится: хук" not in body
    assert "events.jsonl" in body


def test_contract_names_hook_records_and_new_fields():
    body = text()
    for name in (
        "events.jsonl", "курсор", "скрипт хука", ".symphysis/viewer/",
        ".claude/settings.local.json", ".opencode/plugins/", ".git/info/exclude",
        "file_links", "skills", "verdict", "stale_scope",
        "предупреждение прочитано",   # форма заметки флага «прочитано» (attack-warning-read): значение, которое плагин разбирает
    ):
        assert name in body, f"в контракте не названо {name}"


def test_contract_three_is_named():
    """F-55 (`trace-graph`): линза `trace-link` — новое значение списка линз, смена контракта: номер 3
    назван в `docs/repo-contract.md` с тем, что изменилось. Абзац исторический и остаётся при любом
    текущем номере; равенство кода и последнего абзаца держит тест в `decisions/tests/test_journal_render.py`."""
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 3")), None)
    assert line is not None, "в контракте нет строки «С номера 3»"
    assert "trace-link" in line and "линз" in line, "строка о номере 3 не называет, что изменилось: список линз"


def test_contract_four_is_named():
    """`parking-addressee-agent` (F-09, F-17.A): адресат парковки и записи `материалы` → `агент` — новое
    значение существующего поля, смена контракта: номер 4 назван в `docs/repo-contract.md` с тем, что
    изменилось. Абзац исторический и остаётся при любом текущем номере; сценарий `plugin-core-contract`
    «Новое значение адресата поднимает номер»."""
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 4")), None)
    assert line is not None, "в контракте нет строки «С номера 4»"
    assert "агент" in line and "материалы" in line, "строка о номере 4 не называет, что изменилось: адресат"


def test_contract_six_is_named_and_matches_the_code():
    """`attack-severity-buttons` (F-23.A, F-47.A): строка `apply` о тяжести — новая форма грамматики, смена
    контракта: номер 6 назван в `docs/repo-contract.md` с тем, что изменилось, и равен `CONTRACT` в
    `journal_render.py`; сценарии `plugin-core-contract` «Номер в двух выводах» и «Абзац договора»."""
    assert journal_render.CONTRACT == 6
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 6")), None)
    assert line is not None, "в контракте нет строки «С номера 6»"
    assert "тяжесть" in line and "`apply`" in line, "строка о номере 6 не называет, что изменилось: строка `apply` о тяжести"
