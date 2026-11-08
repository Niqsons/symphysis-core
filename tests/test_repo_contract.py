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
    изменилось; сценарий `plugin-core-contract` «Новое значение адресата поднимает номер» и сценарий
    `plugin-core-contract` «Договор называет смену адресата»: абзац «С номера 4» называет `Needs:` на коммит ядра,
    правило «Что делать при смене» велит коммиту ядра называть смену в `Why:`. Абзац
    исторический и остаётся при любом текущем номере."""
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 4")), None)
    assert line is not None, "в контракте нет строки «С номера 4»"
    assert "агент" in line and "материалы" in line, "строка о номере 4 не называет, что изменилось: адресат"
    assert "Needs:" in line and "коммит ядра" in line, "строка о номере 4 не называет Needs: на коммит ядра"
    rule = next((l for l in body.splitlines() if l.startswith("**Что делать при смене.**")), None)
    assert rule is not None, "в контракте нет строки «**Что делать при смене.**»"
    assert "коммит ядра называет смену в `Why:`" in rule, "правило «Что делать при смене» не велит называть смену в Why:"


def test_contract_five_is_named_and_matches_the_code():
    """`attack-lens-conventions` (F-17, F-24.A): линза `rule-compliance` — новое значение списка линз, смена
    контракта: номер 5 назван в `docs/repo-contract.md` с тем, что изменилось, и равен `CONTRACT` в
    `journal_render.py`; сценарий `plugin-core-contract` «Линза правил составления поднимает номер»."""
    assert journal_render.CONTRACT == 5
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 5")), None)
    assert line is not None, "в контракте нет строки «С номера 5»"
    assert "rule-compliance" in line and "линз" in line, "строка о номере 5 не называет, что изменилось: линза"
