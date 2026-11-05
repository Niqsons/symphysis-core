"""Промпт возврата просмотрщика (`buildPrompt`) и экранирование (`esc`, `md`): чистые функции шаблона
`tools/playground-template.html`, вырезанные между маркерами-комментариями и прогнанные через node.
Строки, которые функция пишет, должны оставаться пригодными для `journal.parse_answers` и `apply_answers`."""
import copy
import json
import shutil
import subprocess
import sys

import pytest

import journal
from conftest import FIX, ROOT

TEMPLATE = ROOT / "tools" / "playground-template.html"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="нет node: функции шаблона не прогнать")

DATE = "2026-11-01"


def block(name):
    """Текст шаблона между `/* name:begin */` и `/* name:end */`."""
    text = TEMPLATE.read_text(encoding="utf-8")
    start = text.index(f"/* {name}:begin */") + len(f"/* {name}:begin */")
    return text[start:text.index(f"/* {name}:end */")]


def run_js(tmp_path, name, call, payload):
    """Исполняет блок шаблона и `call` (выражение над `input`), печатает JSON результата."""
    script = tmp_path / f"{name}.js"
    data = tmp_path / f"{name}.json"
    data.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    script.write_text(block(name) + "\nconst input = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
                      f"process.stdout.write(JSON.stringify({call}));\n", encoding="utf-8")
    run = subprocess.run([node, str(script), str(data)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def state(**kw):
    base = {"decisions": {}, "added": {}, "newForks": [], "disputes": {}, "deps": {}, "notes": ""}
    base.update(kw)
    return base


def plan_journal():
    """Журнал плана; F-04 сделан открытым (рекомендация A остаётся), F-02 решён вариантом B со словом."""
    j = journal.import_md(FIX / "journal-plan.md")
    rec = {r["id"]: r for r in j["records"]}["F-04"]
    rec["decision"], rec["status"] = None, "открыт"
    return j


def prompt(tmp_path, j, st, attacks=(), disputes=None):
    return run_js(tmp_path, "prompt", "buildPrompt(input.J, input.attacks, input.st, input.disputes, input.date)",
                  {"J": j, "attacks": list(attacks), "st": st, "disputes": disputes or {}, "date": DATE})


def attack_file(*rows):
    """Файл атаки журнала: строки — (раздел, утверждение, «чем закрыть»)."""
    return {"path": "attack/decisions.md", "frontmatter": {"status": "gaps_found", "targets": [{"path": "decisions.json", "sha256": ""}]},
            "rows": [{"claim": c, "section": s, "lens": "context-compliance", "invariant": "и", "severity": "блокер",
                      "support": "нет", "fix": f} for s, c, f in rows]}


def key(att, i):
    r = att["rows"][i]
    return f'{att["path"]}|{r["section"]}|{r["claim"]}'


def apply_clean(j, text):
    """Все строки промпта принимает `parse_answers` без `unknown`, а `apply_answers` — без отказов."""
    ops = journal.parse_answers(text)
    assert all(op["op"] != "unknown" for op in ops), ops
    report = journal.apply_answers(copy.deepcopy(j), ops, DATE)
    assert not [line for line in report if line.startswith("отказ")], report
    return ops


# --- сценарии «Внесённое уходит из промпта», «Выбор без слова» -------------------

def test_added_option_already_in_the_journal_leaves_the_prompt(tmp_path):
    j = plan_journal()
    rec = {r["id"]: r for r in j["records"]}["F-04"]
    rec["options"].append({"letter": "C", "text": "внесённый вариант (добавлен человеком)", "added": True,
                           "unlikely": None, "evidence": []})
    st = state(added={"F-04": [{"letter": "C", "text": "внесённый вариант"}, {"letter": "D", "text": "новый вариант"}]})
    out = prompt(tmp_path, j, st)["text"]
    assert "добавлен вариант C" not in out and "- F-04: добавлен вариант D. новый вариант" in out
    apply_clean(j, out)


def test_cleared_notes_field_clears_the_prompt(tmp_path):
    j = plan_journal()
    assert "Замечания к схеме: что-то не так" in prompt(tmp_path, j, state(notes=" что-то не так "))["text"]
    cleared = prompt(tmp_path, j, state(notes="  "))["text"]
    assert "Замечания к схеме" not in cleared and "что-то не так" not in cleared
    assert cleared.splitlines()[-1].startswith("(нового нет")
    j["notes"] = [{"date": "2026-10-31", "text": "что-то не так"}]            # уже внесено apply
    assert "Замечания к схеме" not in prompt(tmp_path, j, state(notes="что-то  не так"))["text"]


def test_ingested_word_park_and_dep_leave_the_prompt(tmp_path):
    j = plan_journal()
    recs = {r["id"]: r for r in j["records"]}
    word = recs["F-02"]["decision"]["word"]
    st = state(decisions={"F-02": {"choice": None, "word": f"  {word}\n", "parked": []}},
               deps={"F-03": {"add": ["F-02"], "remove": []}})
    out = prompt(tmp_path, j, st)["text"]
    assert "F-02" not in out and "зависимость" not in out        # слово и зависимость F-03 → F-02 уже в журнале


def test_choice_without_word_is_a_line_apply_accepts(tmp_path):
    j = plan_journal()
    out = prompt(tmp_path, j, state(decisions={"F-04": {"choice": "B", "word": "", "parked": []}}))["text"]
    assert "- F-04: B — (без слова)" in out.splitlines()
    ops = apply_clean(j, out)
    assert ops[0]["op"] == "decide" and ops[0]["option"] == "B" and ops[0]["word"] == ""
    out = prompt(tmp_path, j, state(decisions={"F-02": {"choice": "C", "word": "", "parked": []}}))["text"]
    assert "- F-02: C (было B) — (без слова)" in out.splitlines()
    apply_clean(j, out)


# --- сценарии «Спор становится словом», «Два ответа», «Ответ повторяет» ----------

def test_dispute_on_ask_the_human_row_becomes_the_word(tmp_path):
    j = plan_journal()
    att = attack_file(("F-04, decision", "утверждение 1", "вопрос человеку"),
                      ("F-02, decision", "утверждение 2", "вопрос человеку"),
                      ("F-04, question", "утверждение 3", "вопрос человеку"),
                      ("F-04, decision", "утверждение 4", "правка записи"))
    disputes = {key(att, 0): "ответ  по\nF-04", key(att, 1): "новое слово к F-02", key(att, 2): "спор 3", key(att, 3): "спор 4"}
    res = prompt(tmp_path, j, state(), [att], disputes)
    lines = res["text"].splitlines()
    assert not [l for l in lines if l.startswith("- F-04:")]  # открытая запись: слова нет, рекомендация не решение
    assert "- F-02: B — «новое слово к F-02»" in lines      # решённая: буква решения
    assert res["conflictKeys"] == []
    tail = lines[-1]
    assert tail.startswith("Замечания к схеме: ") and "спор: спор 3" in tail and "спор: спор 4" in tail
    assert "F-04: ответ по F-04" in tail and res["undecidedKeys"] == [key(att, 0)]
    ops = apply_clean(j, res["text"])
    words = {op["id"]: op for op in ops if op["op"] == "decide"}
    assert "F-04" not in words
    assert words["F-02"]["option"] == "B" and words["F-02"]["word"] == "новое слово к F-02"
    assert [op["op"] for op in ops].count("note") == 1


def test_two_different_answers_to_one_decision_conflict(tmp_path):
    j = plan_journal()
    att = attack_file(("F-02, decision", "первая", "вопрос человеку"), ("F-02, decision", "вторая", "вопрос человеку"),
                      ("F-04, decision", "третья", "вопрос человеку"))
    disputes = {key(att, 0): "ответ один", key(att, 1): "ответ два", key(att, 2): "ответ три"}
    res = prompt(tmp_path, j, state(), [att], disputes)
    assert "- F-02:" not in res["text"]                      # одной строки слова на запись нет вовсе
    assert sorted(res["conflictKeys"]) == sorted([key(att, 0), key(att, 1)])
    assert not [l for l in res["text"].splitlines() if l.startswith("- F-04:")]
    assert res["text"].splitlines()[-1] == "Замечания к схеме: F-04: ответ три · конфликт ответов к F-02 — оставьте один"
    apply_clean(j, res["text"])
    same = {key(att, 0): "ответ один", key(att, 1): "ответ  один"}                 # одинаковые ответы — не конфликт
    res = prompt(tmp_path, j, state(), [att], same)
    assert res["conflictKeys"] == [] and res["text"].count("- F-02: B — «ответ один»") == 1


def test_answer_repeating_the_decision_is_not_added(tmp_path):
    j = plan_journal()
    word = {r["id"]: r for r in j["records"]}["F-02"]["decision"]["word"]
    att = attack_file(("F-02, decision", "утверждение", "вопрос человеку"))
    res = prompt(tmp_path, j, state(), [att], {key(att, 0): f" {word} "})
    assert "- F-02" not in res["text"] and "Замечания" not in res["text"] and res["conflictKeys"] == []
    other = prompt(tmp_path, j, state(), [att], {key(att, 0): word + " и ещё"})
    assert "- F-02: B — «" + word + " и ещё»" in other["text"]


def test_ingested_answer_appended_to_the_old_word_leaves_the_prompt(tmp_path):
    """`apply` дописывает ответ к прежнему слову решения (`_merge`): внесённое — вхождение, не равенство.
    Ни спор строки атаки, ни слово карточки к тому же решению не возвращаются в промпт."""
    j = plan_journal()
    att = attack_file(("F-02, decision", "утверждение", "вопрос человеку"))
    first = prompt(tmp_path, j, state(), [att], {key(att, 0): "ответ  к\nF-02"})
    work = copy.deepcopy(j)
    journal.apply_answers(work, apply_clean(j, first["text"]), DATE)
    merged = {r["id"]: r for r in work["records"]}["F-02"]["decision"]["word"]
    assert merged.endswith(" ответ к F-02") and merged != "ответ к F-02"      # прежнее слово + ответ
    again = prompt(tmp_path, work, state(), [att], {key(att, 0): "ответ  к\nF-02"})
    assert "- F-02" not in again["text"] and again["conflictKeys"] == []
    card = prompt(tmp_path, work, state(decisions={"F-02": {"choice": None, "word": "ответ к F-02 ", "parked": []}}))
    assert "- F-02" not in card["text"]
    same_letter = prompt(tmp_path, work, state(decisions={"F-02": {"choice": "B", "word": "ответ к F-02", "parked": []}}))
    assert "- F-02" not in same_letter["text"]
    new_word = prompt(tmp_path, work, state(decisions={"F-02": {"choice": None, "word": "ещё одно", "parked": []}}))
    assert "- F-02: к решению B — «ещё одно»" in new_word["text"].splitlines()


def test_card_cleanup_uses_the_same_ingested_rule():
    """`cleanupIngested` чистит слово карточки тем же правилом вхождения, что и промпт."""
    html = TEMPLATE.read_text(encoding="utf-8")
    cleanup = html[html.index("(function cleanupIngested()"):html.index("/* prompt:begin */")]
    assert "wordIngested(rec.decision.word, d.word)" in cleanup
    assert "function wordIngested(" in block("prompt")


def test_answer_with_guillemets_survives_parse_answers(tmp_path):
    j = plan_journal()
    att = attack_file(("F-02, decision", "утверждение", "вопрос человеку"))
    res = prompt(tmp_path, j, state(), [att], {key(att, 0): "берём «как есть» и `код`"})
    ops = apply_clean(j, res["text"])
    assert ops[0]["word"] == "берём «как есть» и `код`"


# --- экранирование (6.4) ---------------------------------------------------------

def test_esc_covers_the_five_characters(tmp_path):
    out = run_js(tmp_path, "text", "esc(input)", "<a href=\"x\" onclick='y'>&</a>")
    assert out == "&lt;a href=&quot;x&quot; onclick=&#39;y&#39;&gt;&amp;&lt;/a&gt;"


def test_md_escapes_first_then_turns_backtick_pairs_into_code(tmp_path):
    cases = {
        "<b>жирный</b>": "&lt;b&gt;жирный&lt;/b&gt;",
        "`код`": "<code>код</code>",
        "`<script>alert(1)</script>` и <i>": "<code>&lt;script&gt;alert(1)&lt;/script&gt;</code> и &lt;i&gt;",
        "один ` без пары": "один ` без пары",
        "`a` и `b`": "<code>a</code> и <code>b</code>",
        "`it's`": "<code>it&#39;s</code>",
    }
    for src, expected in cases.items():
        assert run_js(tmp_path, "text", "md(input)", src) == expected, src
    assert run_js(tmp_path, "text", "md(input)", None) == ""


def test_answer_to_an_undecided_record_goes_to_notes_and_leaves_it_open(tmp_path):
    """Слово владельца 2026-10-31: запись без решения не получает ни строки слова, ни буквы рекомендации; ответ —
    замечание `F-NN: ответ` в notes[], после apply `decision` нет."""
    j = plan_journal()
    att = attack_file(("F-04, decision", "утверждение", "вопрос человеку"))
    res = prompt(tmp_path, j, state(), [att], {key(att, 0): "ответ по F-04"})
    assert not [l for l in res["text"].splitlines() if l.startswith("- F-04:")] and "- F-04: A" not in res["text"]
    assert res["text"].splitlines()[-1] == "Замечания к схеме: F-04: ответ по F-04"
    assert res["undecidedKeys"] == [key(att, 0)] and res["conflictKeys"] == []
    ops = apply_clean(j, res["text"])
    work = copy.deepcopy(j)
    journal.apply_answers(work, ops, DATE)
    assert {r["id"]: r for r in work["records"]}["F-04"]["decision"] is None
    assert any("F-04: ответ по F-04" in n["text"] for n in work["notes"])
    decided = prompt(tmp_path, j, state(), [attack_file(("F-02, decision", "у", "вопрос человеку"))],
                     {key(attack_file(("F-02, decision", "у", "вопрос человеку")), 0): "слово"})
    assert decided["undecidedKeys"] == [] and "- F-02: B — «слово»" in decided["text"]


def test_other_dispute_goes_to_notes_and_leaves_the_attack_file_alone(tmp_path):
    """`decision-viewer`: «Прочий спор идёт в замечания» — строка с закрытием «правка записи» и ответом в поле спора:
    ответ в «Замечания к схеме:», после `apply` он в `notes[]`, решения нет, файл атаки не изменён."""
    j = plan_journal()
    att = attack_file(("F-02, decision", "утверждение", "правка записи"))
    attack_md = tmp_path / "decisions.md"
    attack_md.write_text(
        "---\n"
        "status: gaps_found\n"
        "targets:\n"
        "  - path: decisions.json\n"
        "    sha256: ''\n"
        "---\n"
        "| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| утверждение | F-02, decision | context-compliance | и | блокер | нет | правка записи |\n"
        , encoding="utf-8")
    before = attack_md.read_bytes()
    res = prompt(tmp_path, j, state(), [att], {key(att, 0): "мой ответ на строку"})
    lines = res["text"].splitlines()
    assert lines[-1].startswith("Замечания к схеме: ") and lines[-1].endswith("спор: мой ответ на строку")
    assert not [l for l in lines if l.startswith("- F-02:")] and res["conflictKeys"] == [] and res["undecidedKeys"] == []
    ops = apply_clean(j, res["text"])
    assert [op["op"] for op in ops].count("note") == 1 and not [op for op in ops if op["op"] == "decide"]
    work = copy.deepcopy(j)
    journal.apply_answers(work, ops, DATE)
    assert any("мой ответ на строку" in n["text"] for n in work["notes"])
    # файл атаки проходит через путь, который мог бы его изменить: сборка страницы с `--attack`
    src = tmp_path / "decisions.json"
    journal.save_journal(src, work)
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "journal.py"), "render-html", str(src), "--out", str(tmp_path / "v.html"),
                          "--attack", str(attack_md)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    assert attack_md.read_bytes() == before


def test_page_marks_undecided_row_and_skill_states_the_rule():
    """У строки с ответом к нерешённой записи — пометка до копирования промпта; скилл называет то же правило."""
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "запись не решена — ответ уйдёт в замечания; выбери вариант в карточке" in html
    skill = " ".join((ROOT / "skills" / "symphysis-viewer" / "SKILL.md").read_text(encoding="utf-8").split())
    assert "У записи без решения слова нет, рекомендация не решение" in skill and "`F-NN: ответ`" in skill


# --- новая развилка, уже внесённая apply, из черновика уходит (F-17, F-93) ------

def page_prompt(tmp_path, j, st):
    """Промпт страницы, собранной из журнала, при состоянии браузера `st`: скрипт шаблона целиком, без браузера."""
    html = tmp_path / "v.html"
    html.write_text(journal.render_html(j, TEMPLATE), encoding="utf-8", newline="\n")
    data = tmp_path / "state.json"
    data.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    run = subprocess.run([node, str(FIX / "viewer-smoke.js"), str(html), str(data)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)["out"]


def ingested_fork_journal():
    j = plan_journal()
    j["records"].append({**copy.deepcopy(j["records"][-1]), "id": "F-90", "kind": "развилка", "status": "открыт", "question": "Новая   развилка человека?",
                         "options": [{"letter": "A", "text": "да", "added": True, "unlikely": None, "evidence": []}], "decision": None, "recommendation": None,
                         "antipodes": [], "depends_on": [], "evidence": [], "outcome": None, "reversibility": None, "parking": [], "dispute": "", "consequences": "", "comments": [], "addressee": "человек"})
    return j


def test_ingested_new_fork_leaves_the_prompt(tmp_path):
    fork = {"id": "F-N1", "question": "Новая развилка человека?", "options": "да", "word": ""}
    out = page_prompt(tmp_path, ingested_fork_journal(), state(newForks=[fork]))
    assert "Новая развилка человека?" not in out


def test_edited_new_fork_stays_in_the_prompt(tmp_path):
    fork = {"id": "F-N1", "question": "Новая развилка человека, поправленная?", "options": "да", "word": ""}
    out = page_prompt(tmp_path, ingested_fork_journal(), state(newForks=[fork]))
    assert out.count("Новая развилка человека, поправленная?") == 1


# --- дата в заголовке промпта: местная, не UTC (F-64) ---------------------------------

def local_date(tmp_path, tz, iso_moment):
    """`localDate(момент)` шаблона в процессе node с поясом `tz`: пояс задаёт переменная `TZ`, как её читает node."""
    script = tmp_path / "local-date.js"
    script.write_text(block("prompt") + f"\nprocess.stdout.write(localDate(new Date('{iso_moment}')));\n", encoding="utf-8")
    run = subprocess.run([node, str(script)], capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "TZ": tz})
    assert run.returncode == 0, run.stderr
    return run.stdout


def test_scenario_first_hours_of_the_day(tmp_path):
    """Сценарий «Первые часы суток»: 01:30 4 ноября при поясе UTC+3 (это 22:30 3 ноября по UTC) — в заголовке `2026-11-04`."""
    assert local_date(tmp_path, "Etc/GMT-3", "2026-11-03T22:30:00Z") == "2026-11-04"


def test_local_date_is_zero_padded_and_follows_the_zone(tmp_path):
    assert local_date(tmp_path, "Etc/GMT-3", "2026-01-05T00:10:00+03:00") == "2026-01-05"
    assert local_date(tmp_path, "Etc/GMT+5", "2026-01-01T02:00:00Z") == "2025-12-31"   # к западу от UTC местная дата раньше


def test_the_page_takes_the_date_from_local_date():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "toISOString" not in text and "localDate(new Date())" in text


def test_scenario_decision_date_comes_from_apply(tmp_path):
    """Сценарий «Дата решения»: дата в заголовке промпта не равна дате `apply`, у решения дата из `apply`."""
    j = plan_journal()
    rec = {r["id"]: r for r in j["records"]}["F-04"]
    text = run_js(tmp_path, "prompt", "buildPrompt(input.J, input.attacks, input.st, input.disputes, '2020-01-02')",
                  {"J": j, "attacks": [], "st": state(decisions={"F-04": {"choice": "A", "word": "", "parked": []}}), "disputes": {}})["text"]
    assert "2020-01-02" in text.splitlines()[0]
    applied = copy.deepcopy(j)
    report = journal.apply_answers(applied, journal.parse_answers(text), DATE)
    assert not [line for line in report if line.startswith("отказ")], report
    decided = {r["id"]: r for r in applied["records"]}["F-04"]["decision"]
    assert decided["date"] == DATE
