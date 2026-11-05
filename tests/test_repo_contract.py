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
        "file_links", "skills",
    ):
        assert name in body, f"в контракте не названо {name}"


def test_contract_three_is_named_and_matches_the_code():
    """F-55: линза `trace-link` — новое значение списка линз, смена контракта: номер 3 назван в
    `docs/repo-contract.md` с тем, что изменилось, и равен `CONTRACT` в `journal_render.py`."""
    assert journal_render.CONTRACT == 3
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 3")), None)
    assert line is not None, "в контракте нет строки «С номера 3»"
    assert "trace-link" in line and "линз" in line, "строка о номере 3 не называет, что изменилось: список линз"
