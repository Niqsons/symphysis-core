"""Контракт с плагином: раздел о хуке описан, строки «когда появится» нет (F-35)."""
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
