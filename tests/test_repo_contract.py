"""Контракт с плагином: раздел о хуке описан, строки «когда появится» нет (F-35)."""
import re

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


def test_contract_five_is_named():
    """`attack-lens-conventions` (F-17, F-24.A): линза `rule-compliance` — новое значение списка линз, смена
    контракта: номер 5 назван в `docs/repo-contract.md` с тем, что изменилось; сценарий `plugin-core-contract`
    «Линза правил составления поднимает номер». Абзац исторический: `attack-severity-buttons` влито раньше
    с номером 6, и номер 5 есть только в истории ветки `attack-lens-conventions`."""
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 5")), None)
    assert line is not None, "в контракте нет строки «С номера 5»"
    assert "rule-compliance" in line and "линз" in line, "строка о номере 5 не называет, что изменилось: линза"


def test_contract_six_is_named():
    """`attack-severity-buttons` (F-23.A, F-47.A): строка `apply` о тяжести — новая форма грамматики, смена
    контракта: номер 6 назван в `docs/repo-contract.md` с тем, что изменилось; сценарий `plugin-core-contract`
    «Абзац договора». Абзац исторический и остаётся при любом текущем номере: равенство `CONTRACT` наибольшему N
    держит тест в `decisions/tests/test_journal_render.py` («Номер контракта в сценариях — не ниже N»)."""
    body = text()
    line = next((l for l in body.splitlines() if l.startswith("С номера 6")), None)
    assert line is not None, "в контракте нет строки «С номера 6»"
    assert "тяжесть" in line and "`apply`" in line, "строка о номере 6 не называет, что изменилось: строка `apply` о тяжести"


# --- номер контракта при мерже и «не ниже N» (бэклог B-57, слово владельца 2026-11-08) ---

SPEC = ROOT / "openspec" / "specs" / "plugin-core-contract" / "spec.md"
EQUALITY_IN_SPEC = re.compile(r"`contract` равен \d|SHALL стать \d")
EQUALITY_IN_TESTS = re.compile(r"CONTRACT\s*==\s*\d|\[[\"']contract[\"']\]\s*==\s*\d")
SKIP_DIRS = {"upstream", "node_modules", "payload"}


def test_contract_paragraphs_go_one_by_one():
    """Сценарии `plugin-core-contract` «Номер при мерже» и «Номер ветки занят»: номер растёт как `main`+1 при мерже,
    поэтому абзацы «С номера N» идут подряд, без пропусков и повторов; второе влитое, не перенумеровавшее свой
    абзац, даёт два абзаца с одним номером."""
    numbers = [int(n) for n in re.findall(r"^С номера (\d+)\b", text(), re.MULTILINE)]
    assert numbers, "в договоре нет абзацев «С номера N»"
    assert len(numbers) == len(set(numbers)), f"два абзаца с одним номером: {sorted(numbers)}"
    assert sorted(numbers) == list(range(min(numbers), max(numbers) + 1)), f"номера абзацев с пропуском: {sorted(numbers)}"


def test_merge_rule_and_exception_are_written():
    """Сценарий `plugin-core-contract` «Исключение 5 и 6»: абзац «Номер при мерже» договора несёт правило владельца
    и называет исключение — номера 5 и 6 выданы до правила, номер 6 несут `268eb25` и `32bfca7`."""
    line = next((l for l in text().splitlines() if l.startswith("**Номер при мерже.**")), None)
    assert line is not None, "в контракте нет абзаца «**Номер при мерже.**»"
    for token in ("`<current_number>`+1", "из `main` перед мержем в `main`", "предварительный", "перенумеровывает",
                  "«не ниже N»", "наибольшему N", "номера 5 и 6", "`268eb25`", "`32bfca7`"):
        assert token in line, f"в абзаце «Номер при мерже» нет «{token}»"


def _test_files():
    """Файлы тестов проекта: каталоги верхнего уровня обходятся явно — `upstream` в worktree ссылка на форк."""
    for top in sorted(ROOT.iterdir()):
        if not top.is_dir() or top.name in SKIP_DIRS or top.name.startswith("."):
            continue
        for path in sorted(top.glob("**/*.py" if top.name == "tests" else "**/tests/**/*.py")):
            if not SKIP_DIRS & set(path.relative_to(ROOT).parts):
                yield path


def test_contract_number_is_never_pinned_by_equality():
    """Сценарий `plugin-core-contract` «Следующая смена номера»: сценарии и тексты требований мастер-спеки называют
    номер «не ниже N», тесты сравнивают номер с `CONTRACT`; буквальное равенство номеру не держит ни один из них —
    его держит только тест наибольшего N в `decisions/tests/test_journal_render.py`."""
    spec = SPEC.read_text(encoding="utf-8")
    assert not EQUALITY_IN_SPEC.findall(spec), f"в мастер-спеке равенство номеру: {EQUALITY_IN_SPEC.findall(spec)}"
    pinned = [f"{path.relative_to(ROOT).as_posix()}:{n}: {line.strip()}"
              for path in _test_files()
              for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
              if EQUALITY_IN_TESTS.search(line)]
    assert not pinned, "тест закрепляет номер контракта буквально:\n" + "\n".join(pinned)
