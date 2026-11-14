import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import (core_clone, core_files, evidence_of, FIX, one_record_journal, PLAN_JOURNAL, requires_evidence_roots, ROOT,
                      run_check)
import journal


@requires_evidence_roots
def test_check_plan_journal_all_found():
    j = journal.load_journal(PLAN_JOURNAL)
    evidence = PLAN_JOURNAL.parent / "evidence"
    plan_sources = {
        "docs/plan-flexible-pipeline.md": evidence / "plan-flexible-pipeline.md",
        "docs/plan-implementation.md": evidence / "plan-implementation.md",
        "docs/analysis/step0-sources.md": evidence / "step0-sources.md",
        "docs/analysis/gsd-openspec-integration.md": evidence / "gsd-openspec-integration.md",
    }
    r = journal.check_evidence(j, {**journal.default_roots(), **plan_sources})
    # 89 улик: F-01…F-24, F-25 (D4b), F-26 (D7), F-27; без нормализации (F-36). Улики прежних журналов — история
    # (F-24 A, ruling R9): путь, перенесённый изменением `module-structure`, остаётся в журнале и даёт «файла нет».
    assert r["total"] == 89
    wrapped = "F-07: docs/plan-flexible-pipeline.md"             # цитата переходит через перенос строки
    moved = "F-26: tools/journal_render.py «def render_html»"      # `render_html` ушёл в viewer_render.py, файл потом переедет
    absent = [m for m in r["missing"] if "файла нет" in m]
    for item in r["missing"]:
        assert item.startswith((wrapped, moved)) or item in absent, item
    for item in absent:                                          # «файла нет» называет только путь, которого в дереве нет
        path = item.split(": ", 1)[1].split(" «", 1)[0]
        assert not plan_sources.get(path, ROOT / path).exists(), item
    assert r["found"] + len(r["missing"]) == 89 and any(m.startswith(wrapped) for m in r["missing"])


# --- что именно записывается в улику ---------------------------------------


def test_check_records_line_found_verdict(tmp_path):
    (tmp_path / "a.md").write_text("раз\nдва\nтри целиком\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="три целиком")
    journal.check_evidence(j, {"": tmp_path})
    assert evidence_of(j) == {"path": "a.md", "quote": "три целиком",
                              "line": 3, "found": True, "verdict": "сверено"}
    assert journal.validate_journal(j) == []


def test_check_missing_is_found_false_not_null(tmp_path):
    """«Проверили — нет» (false) отличимо от «не проверяли» (нет поля / null)."""
    (tmp_path / "a.md").write_text("текст\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="чего-то нет")
    r = journal.check_evidence(j, {"": tmp_path})
    ev = evidence_of(j)
    assert (ev["line"], ev["found"], ev["verdict"]) == (None, False, "цитаты нет дословно")
    assert r == {"total": 1, "found": 0, "unchecked": [],
                 "missing": ["F-01: a.md «чего-то нет» — цитаты нет дословно"]}
    assert journal.validate_journal(j) == []


def test_schema_accepts_not_checked_evidence_as_null():
    j = one_record_journal(path="a.md", quote="x")
    evidence_of(j).update({"line": None, "found": None, "verdict": None})
    assert journal.validate_journal(j) == []


def test_check_covers_record_level_evidence(tmp_path):
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="раз")
    j["records"][0]["evidence"].append({"path": "a.md", "quote": "два"})
    r = journal.check_evidence(j, {"": tmp_path})
    assert r["total"] == 2 and r["found"] == 2
    assert j["records"][0]["evidence"][0]["line"] == 2


# --- правила журнала для check (5.2) ----------------------------------------

def fact_journal(**changes) -> dict:
    j = one_record_journal(path="a.md", quote="x")
    rec = j["records"][0]
    rec.update(kind="факт", options=[], status="решён", **changes)
    return j


def test_fact_without_evidence_is_an_error(tmp_path):
    """Сценарий «Факт без улики»: код 1, строка с префиксом [!!]."""
    path = tmp_path / "j.json"
    journal.save_journal(path, fact_journal())
    assert "F-01: факт без улики" in journal.validate_journal(journal.load_journal(path))
    run = run_check(path)
    assert run.returncode == 1 and "[!!] F-01: факт без улики" in run.stderr


def test_parked_fact_without_evidence_is_fine(tmp_path):
    """Сценарий «Припаркованный факт без улики»: ни парковка, ни статус «припаркован» не дают ошибки."""
    parked = fact_journal(parking=[{"addressee": "агент", "text": "найти"}])
    parked["records"][0]["status"] = "припаркован"
    assert journal.validate_journal(parked) == []
    assert journal.validate_journal(fact_journal(parking=[{"addressee": "агент", "text": "найти"}])) == []
    only_status = fact_journal()
    only_status["records"][0]["status"] = "припаркован"
    assert journal.validate_journal(only_status) == []
    path = tmp_path / "j.json"
    journal.save_journal(path, parked)
    run = run_check(path)
    assert run.returncode == 0 and "факт без улики" not in run.stdout + run.stderr


def test_fact_with_record_evidence_is_fine():
    assert journal.validate_journal(fact_journal(evidence=[{"path": "a.md", "quote": "x"}])) == []


def test_empty_why_is_an_error(tmp_path):
    """Сценарий «Пустое why»: код 1; why из пробелов считается пустым."""
    for why in ("", "  "):
        j = one_record_journal(path="a.md", quote="x")
        j["records"][0]["recommendation"] = {"option": "A", "why": why}
        path = tmp_path / "j.json"
        journal.save_journal(path, j)
        run = run_check(path)
        assert run.returncode == 1 and "[!!] F-01: рекомендация без why" in run.stderr
    j["records"][0]["recommendation"]["why"] = "потому что"
    assert journal.validate_journal(j) == []


def test_old_journal_with_text_stays_valid(tmp_path):
    """Сценарий «Старый журнал с полем `text`»: `why` нет внутри `text`, строки о поле нет, код 0."""
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="раз")
    j["records"][0]["recommendation"] = {"option": "A", "why": "дешевле откатить", "text": "A — кратко"}
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    run = run_check(path)
    assert run.returncode == 0, run.stderr
    assert "text" not in run.stdout + run.stderr


def parking_fixture(tmp_path, with_research=True, finding=None, addressee="агент"):
    j = one_record_journal(path="a.md", quote="раз")
    parking = {"addressee": addressee, "text": "найти"}
    if finding is not None:
        parking["finding"] = finding
    j["records"][0]["parking"] = [parking]
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    if with_research:
        (tmp_path / "research").mkdir()
        (tmp_path / "research" / "F-01.md").write_text("находка\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    return path, roots


def test_parking_without_finding_at_research_file_is_a_signal(tmp_path):
    """Сценарии «Парковка без находки при файле» и «Сигнал о парковке агенту при --strict»: код 0, с --strict — 2."""
    path, roots = parking_fixture(tmp_path)
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[!!] F-01: парковка «агент» без finding при research/F-01.md" in run.stdout
    strict = run_check(path, "--roots", roots, "--strict")
    assert strict.returncode == 2 and "[!!] F-01: парковка «агент» без finding при research/F-01.md" in strict.stdout


def test_parking_signal_needs_the_research_file_and_no_finding(tmp_path):
    for sub, kw in (("a", {"with_research": False}), ("b", {"finding": "нашли"})):
        (tmp_path / sub).mkdir()
        path, roots = parking_fixture(tmp_path / sub, **kw)
        run = run_check(path, "--roots", roots, "--strict")
        assert run.returncode == 0 and "без finding" not in run.stdout


def test_human_parking_without_finding_is_a_signal(tmp_path):
    """Сценарий «Парковка человеку без ответа»: у этого адресата нет своего шага, поэтому напоминает только `check`.
    Файла `research/` ей не нужно. Код 0, с --strict — 2."""
    path, roots = parking_fixture(tmp_path, with_research=False, addressee="человек")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "[!!] F-01: парковка «человек» без finding: найти" in run.stdout
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


def test_human_parking_with_finding_is_silent(tmp_path):
    """Сценарий «Парковка человеку с ответом»."""
    path, roots = parking_fixture(tmp_path, with_research=False, addressee="человек", finding="записано в бэклог")
    run = run_check(path, "--roots", roots, "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "без finding" not in run.stdout


def test_security_parking_does_not_wait_for_the_human(tmp_path):
    """Парковку `ИБ` закрывает шаг `security`, поэтому сигнала о ней нет."""
    path, roots = parking_fixture(tmp_path, with_research=False, addressee="ИБ")
    run = run_check(path, "--roots", roots, "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "без finding" not in run.stdout


def test_each_human_parking_is_counted_on_its_own(tmp_path):
    """Две парковки у одной записи: сигнал только о той, что без ответа."""
    path, roots = parking_fixture(tmp_path, with_research=False, addressee="человек", finding="ответ есть")
    j = journal.load_journal(path)
    j["records"][0]["parking"].append({"addressee": "человек", "text": "вторая"})
    journal.save_journal(path, j)
    lines = [line for line in run_check(path, "--roots", roots).stdout.splitlines() if "без finding" in line]
    assert lines == ["[!!] F-01: парковка «человек» без finding: вторая"]


# --- старое значение адресата «материалы»: читается, не пишется (parking-addressee-agent: F-22) ---------------------

OLD_ADDRESSEE_SIGNAL = "адресат «материалы» — старое значение, новые записи пишут «агент»"
LEGACY_FIX = FIX / "journal-legacy" / "decisions.json"


def addressee_fixture(tmp_path, record="", parking=None):
    """Журнал одной развилки с адресатом записи `record` и парковкой адресату `parking` (с находкой, файла `research/`
    нет); улика сходится — других сигналов журнал не даёт."""
    j = one_record_journal(path="a.md", quote="раз")
    rec = j["records"][0]
    rec["addressee"] = record
    if parking is not None:
        rec["parking"] = [{"addressee": parking, "text": "найти", "finding": "нашли"}]
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    return path, roots


def test_old_addressee_at_a_parking_is_a_signal_not_a_schema_error(tmp_path):
    """Сценарий «Старое значение в журнале активного изменения»: строка `[!!]`, код 0, с --strict — 2;
    в stderr ничего — это не ошибка схемы."""
    path, roots = addressee_fixture(tmp_path, parking="материалы")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stdout + run.stderr
    assert f"[!!] F-01: {OLD_ADDRESSEE_SIGNAL}" in run.stdout and run.stderr == ""
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


def test_old_addressee_at_a_record_is_a_signal(tmp_path):
    path, roots = addressee_fixture(tmp_path, record="материалы")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stdout + run.stderr
    assert f"[!!] F-01: {OLD_ADDRESSEE_SIGNAL}" in run.stdout
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


def test_old_addressee_at_a_record_and_its_parking_gives_one_line(tmp_path):
    path, roots = addressee_fixture(tmp_path, record="материалы", parking="материалы")
    lines = [line for line in run_check(path, "--roots", roots).stdout.splitlines() if OLD_ADDRESSEE_SIGNAL in line]
    assert lines == [f"[!!] F-01: {OLD_ADDRESSEE_SIGNAL}"]


def test_agent_addressee_gives_no_signal(tmp_path):
    """Журнал только с `агент` у записи и у парковки — молчание: ни строки о старом значении, ни другой `[!!]`."""
    path, roots = addressee_fixture(tmp_path, record="агент", parking="агент")
    run = run_check(path, "--roots", roots, "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "[!!]" not in run.stdout + run.stderr


def test_old_addressee_is_compared_exactly(tmp_path):
    """Сравнение точное (F-36 Dismiss): «Материалы» — не старое значение, а ошибка схемы, код 1."""
    path, roots = addressee_fixture(tmp_path, parking="Материалы")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 1 and "parking/0/addressee" in run.stderr and OLD_ADDRESSEE_SIGNAL not in run.stdout


def test_legacy_fixture_journal_passes_check_with_a_line_per_record(tmp_path):
    """Сценарий «Старый журнал годен» на фикстуре `journal-legacy`: улика сходится по историческому пути,
    единственные строки `[!!]` — о старом значении у факта F-01 и у парковки F-02; код 0, с --strict — 2."""
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"docs/plan-implementation.journal.json": str(PLAN_JOURNAL)}), encoding="utf-8")
    run = run_check(LEGACY_FIX, "--roots", roots)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stderr == "" and "[ok] улик сверено 1 из 1" in run.stdout
    assert [line for line in run.stdout.splitlines() if line.startswith("[!!]")] == [
        f"[!!] F-01: {OLD_ADDRESSEE_SIGNAL}", f"[!!] F-02: {OLD_ADDRESSEE_SIGNAL}"]
    assert run_check(LEGACY_FIX, "--roots", roots, "--strict").returncode == 2


# --- бинарные файлы (5.4) -----------------------------------------------------


def test_binary_evidence_does_not_stop_the_others(tmp_path):
    """Сценарий «Улика указывает на PNG»: check --write, остальные улики сверены, код 0, даже с --strict."""
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    shutil.copy(FIX / "evidence-pixel.png", tmp_path / "p.png")
    j = one_record_journal(path="p.png", quote="любая")
    j["records"][0]["options"][0]["evidence"].append({"path": "a.md", "quote": "раз"})
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    run = run_check(path, "--roots", roots, "--write", "--strict")
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 1 из 2, не проверить 1" in run.stdout
    evs = journal.load_journal(path)["records"][0]["options"][0]["evidence"]
    assert (evs[0]["found"], evs[0]["verdict"]) == (None, "не проверить: бинарный файл")
    assert evs[1]["found"] is True
    assert journal.validate_journal(journal.load_journal(path)) == []


# --- отступление от постановки без замка (7.4: F-55.E, F-08.A) --------------------

DEVIATION_FIX = FIX / "journal-deviation.json"
INTENT_DEMO = FIX / "intent-demo"


def intent_demo_roots(tmp_path) -> Path:
    """Корень улик fixture: путь `openspec/changes/intent-demo/…` — как в журнале изменения, от корня проекта."""
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"openspec/changes/intent-demo/": str(INTENT_DEMO)}), encoding="utf-8")
    return roots


def test_deviation_with_a_human_decision_against_the_setting_passes_check(tmp_path):
    """Сценарий «Отступление проходит check»: факт постановки, развилка, чей выбранный вариант несёт `deviation`
    на него, решение человека против факта со словом — `check` код 0 и с `--strict`, ни одной строки `[!!]`:
    пометка — видимость, не замок."""
    j = journal.load_journal(DEVIATION_FIX)
    fork = next(r for r in j["records"] if any(o.get("deviation") for o in r["options"]))
    chosen = next(o for o in fork["options"] if o["letter"] == fork["decision"]["option"])
    fact = next(r for r in j["records"] if r["id"] == chosen["deviation"])
    assert (fact["kind"], fact["addressee"]) == ("факт", "постановка")
    assert fork["kind"] == "развилка" and fork["status"] == "решён" and fork["decision"]["word"]
    assert chosen["text"].startswith("Наследование"), "решение против сценария факта постановки"
    assert fork["recommendation"]["option"] != chosen["letter"] and "deviation" not in fork
    run = run_check(DEVIATION_FIX, "--roots", intent_demo_roots(tmp_path), "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "[!!]" not in run.stdout + run.stderr and "[ok] улик сверено 3 из 3" in run.stdout


def test_deviation_stays_visible_in_the_renders():
    """Видимость: пометка у строки выбранного варианта в markdown и строка у решения в design."""
    j = journal.load_journal(DEVIATION_FIX)
    md = journal.render_md(j).split("\n## F-03")[1]
    assert "(отступление от F-01)" in next(line for line in md.splitlines() if line.startswith("  - B. "))
    assert "- **Отступление от постановки:** F-01" in journal.render_design(j)


# --- nodes: check смотрит только форму, со схемой не сверяет (F-24, F-114) -----

def check_output(tmp_path, record_nodes=None, scheme=None):
    """Вывод `check` журнала рядом со `scheme.md`: код и всё, что напечатано."""
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    j = one_record_journal("a.md", "дв")
    if record_nodes is not None:
        j["records"][0]["nodes"] = record_nodes
    src = tmp_path / "decisions.json"
    journal.save_journal(src, j)
    if scheme is not None:
        (tmp_path / "scheme.md").write_text(scheme, encoding="utf-8")
    run = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "cli" / "journal.py"), "check", str(src), "--roots", str(roots)],
                         capture_output=True, text=True, encoding="utf-8")
    return run.returncode, run.stdout + run.stderr


SCHEME_WITHOUT_X = "```mermaid\nflowchart TD\n  A --> B\n```\n"


def test_check_does_not_compare_nodes_with_the_scheme(tmp_path):
    code, out = check_output(tmp_path, ["X"], SCHEME_WITHOUT_X)
    assert code == 0, out
    assert "nodes" not in out and "узел" not in out


def test_check_says_nothing_about_a_journal_without_nodes(tmp_path):
    code, out = check_output(tmp_path, None, SCHEME_WITHOUT_X)
    assert code == 0, out
    assert "nodes" not in out and "узел" not in out


# --- слово у выбора мимо рекомендации ---------------------------------------------

def word_fixture(tmp_path, choice, word="", added=False):
    j = one_record_journal(path="a.md", quote="раз")
    record = j["records"][0]
    other = dict(record["options"][0], letter="B", text="второй", added=added)
    record["options"].append(other)
    record["status"] = "решён"
    record["recommendation"] = {"option": "A", "why": "причина из рекомендации"}
    record["decision"] = {"option": choice, "word": word, "date": "2026-11-02"}
    record["reversibility"] = {"level": "обратимо", "why": "одна строка"}
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    return path, roots


def test_choice_past_the_recommendation_without_a_word_is_a_signal(tmp_path):
    """Сценарий «Выбор мимо рекомендации без слова»: код 0, с --strict — 2."""
    path, roots = word_fixture(tmp_path, "B")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[!!] F-01: выбран не рекомендованный вариант B без слова" in run.stdout
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


@pytest.mark.parametrize("choice, word, added", [("A", "", False), ("B", "потому что", False), ("B", "", True)])
def test_no_signal_for_recommended_worded_or_own_choice(tmp_path, choice, word, added):
    """Сценарии «Рекомендованный отказ без слова», «Слово к выбору мимо рекомендации внесено» (B со словом — молчание
    и с --strict код 0) и «Вариант, добавленный человеком»."""
    path, roots = word_fixture(tmp_path, choice, word, added)
    run = run_check(path, "--roots", roots, "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "не рекомендованный" not in run.stdout


# --- цикл зависимостей --------------------------------------------------------------

def deps_fixture(tmp_path, deps):
    """Журнал из записей с заданными `depends_on`; в остальном записи годны и сигналов не дают."""
    j = one_record_journal(path="a.md", quote="раз")
    j["records"] = [dict(j["records"][0], id=rid, depends_on=on) for rid, on in deps.items()]
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    return path, roots


def test_cycle_through_a_third_record_is_a_signal(tmp_path):
    """Сценарий «Цикл зависимостей». Форма из журнала `trace-graph`: стрелка замыкается через третью запись,
    поэтому взаимных пар недостаточно. Код 0, с --strict — 2."""
    path, roots = deps_fixture(tmp_path, {"F-01": ["F-02"], "F-02": ["F-03"], "F-03": ["F-01"]})
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "[!!] F-01: цикл зависимостей F-01 → F-02 → F-03 → F-01" in run.stdout
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


def test_each_cycle_is_named_once(tmp_path):
    """Две пары: по строке на пару, вход во вторую из её же записи строки не дублирует."""
    path, roots = deps_fixture(tmp_path, {"F-01": ["F-02"], "F-02": ["F-01"], "F-03": ["F-04"], "F-04": ["F-03"]})
    lines = [line for line in run_check(path, "--roots", roots).stdout.splitlines() if "цикл зависимостей" in line]
    assert lines == ["[!!] F-01: цикл зависимостей F-01 → F-02 → F-01", "[!!] F-03: цикл зависимостей F-03 → F-04 → F-03"]


@pytest.mark.parametrize("deps", [
    {"F-01": [], "F-02": ["F-01"], "F-03": ["F-02"]},                       # цепочка
    {"F-01": [], "F-02": ["F-01"], "F-03": ["F-01"], "F-04": ["F-02", "F-03"]},   # ромб: F-01 достижима двумя путями
    {"F-01": ["F-02"], "F-02": []},                                         # стрелка на запись с большим номером
], ids=["цепочка", "ромб", "вперёд"])
def test_no_cycle_signal_without_a_cycle(tmp_path, deps):
    path, roots = deps_fixture(tmp_path, deps)
    run = run_check(path, "--roots", roots, "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "цикл" not in run.stdout


# --- корни при инструментах вне проекта (F-93, F-104): раскладка по образцу research/F-93-probe/probe.py ---


def _copy_tools(into: Path, clone: bool = False) -> Path:
    """Каталог файла корней. Раскладка инсталлятора: код и схема журнала в `<into>/.symphysis/tools` (F-41 A), файл корней
    с `"": "<root>/.."` там же. `clone=True` — клон ядра в модульной раскладке: код в `<into>/<модуль>/`, файл корней
    настоящий в `<into>/tools`, пустого префикса в нём нет; `docs/` клона есть."""
    if clone:
        (into / "docs").mkdir(parents=True)
        return core_clone(into) / "tools"
    tools = into / ".symphysis" / "tools"
    tools.mkdir(parents=True)
    for f in core_files():
        if re.match(r"journal.*\.(py|json)|roots\.py|runtime_context\.py|viewer_render\.py|attack_table\.py|attack_scope\.py|step_help\.py|openspec_run\.py|symphysis_config\.py|playground-template\.html", f.name):
            shutil.copy(f, tools / f.name)
    (tools / "journal-roots.json").write_text('{"": "<root>/.."}\n', encoding="utf-8")
    return tools


def _layout(tmp_path: Path, tools_in_project: bool, clone: bool = False):
    """(tools, project): в проекте `only_project.py` и `both.py`, в установке `only_install.py` и `both.py`. `clone=True` — установка это клон ядра."""
    install = tmp_path / "установка с пробелом"
    project = install if tools_in_project else tmp_path / "проект"
    tools = _copy_tools(install, clone)
    for base, names in ((install, ("both.py", "only_install.py")), (project, ("both.py", "only_project.py"))):
        (base / "src").mkdir(exist_ok=True, parents=True)
        for name in names:
            (base / "src" / name).write_text("в этом месте\n", encoding="utf-8")
    change = project / "openspec" / "changes" / "demo"
    change.mkdir(parents=True)
    j = one_record_journal("src/both.py", "в ")
    j["records"][0]["options"][0]["evidence"] = [
        {"path": f"src/{n}", "quote": "в "} for n in ("both.py", "only_project.py", "only_install.py")]
    journal.save_journal(change / "decisions.json", j)
    return tools, project


def _core(tools: Path, project: Path, *args):
    """`journal.py` той раскладки, чей файл корней лежит в `tools`: у установки — рядом с ним, у клона — в модуле `cli`."""
    script = tools / "journal.py" if (tools / "journal.py").is_file() else tools.parent / "cli" / "journal.py"
    return subprocess.run([sys.executable, "-X", "utf8", str(script), *map(str, args)], cwd=project,
                          capture_output=True, encoding="utf-8", errors="replace")


JOURNAL_REL = "openspec/changes/demo/decisions.json"


def _verdicts(view_stdout: str) -> dict:
    return {e["path"]: e["verdict"] for e in json.loads(view_stdout)["records"][0]["options"][0]["evidence"]}


def test_scenario_root_with_tools_outside_the_project(tmp_path):
    """«Корень при инструментах вне проекта»: вердикт и карта считаются от проекта из пути журнала."""
    tools, project = _layout(tmp_path, tools_in_project=False)
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert view.returncode == 0, view.stderr
    assert _verdicts(view.stdout) == {"src/both.py": "сверено", "src/only_project.py": "сверено", "src/only_install.py": "файла нет"}


def test_scenario_all_core_commands_with_tools_outside_the_project(tmp_path):
    """«Все команды ядра»: `check` и `render-html` не читают корни установки."""
    tools, project = _layout(tmp_path, tools_in_project=False)
    out = _core(tools, project, "check", JOURNAL_REL)
    assert "улик сверено 2 из 3" in out.stdout and "only_install.py" in out.stdout and "файла нет" in out.stdout
    page = _core(tools, project, "render-html", JOURNAL_REL, "--out", "openspec/changes/demo/symphysis.html")
    assert page.returncode == 0, page.stderr
    assert "улик сверено 2 из 3" in page.stdout
    html = (project / "openspec" / "changes" / "demo" / "symphysis.html").read_text(encoding="utf-8")
    assert re.search(r'"src/only_project.py":\s*"[^"]*src/only_project.py"', html)
    assert not re.search(r'"src/only_install.py":\s*"', html)   # файл только в установке в карту не идёт


def test_scenario_ordinary_installation(tmp_path):
    """«Обычная установка»: инструменты в проекте, корни из файла корней; `--roots` важнее всего."""
    tools, project = _layout(tmp_path, tools_in_project=True)
    for command in ("view-json", "check", "render-html"):
        extra = ("--out", "openspec/changes/demo/symphysis.html") if command == "render-html" else ()
        run = _core(tools, project, command, JOURNAL_REL, *extra)
        assert run.returncode == 0, run.stderr
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert _verdicts(view.stdout)["src/only_install.py"] == "сверено"   # установка и проект — один каталог
    other = tmp_path / "другой"
    (other / "src").mkdir(parents=True)
    (other / "src" / "both.py").write_text("в другом\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(other)}), encoding="utf-8")
    forced = _core(tools, project, "view-json", JOURNAL_REL, "--roots", roots)
    assert _verdicts(forced.stdout) == {"src/both.py": "сверено", "src/only_project.py": "файла нет", "src/only_install.py": "файла нет"}


def test_explicit_roots_beat_the_project_root_with_tools_outside(tmp_path):
    tools, project = _layout(tmp_path, tools_in_project=False)
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path / "установка с пробелом")}), encoding="utf-8")
    view = _core(tools, project, "view-json", JOURNAL_REL, "--roots", roots)
    assert _verdicts(view.stdout)["src/only_install.py"] == "сверено"


def _with_evidence(project: Path, *paths: str) -> None:
    j = journal.load_journal(project / JOURNAL_REL)
    j["records"][0]["options"][0]["evidence"] = [{"path": p, "quote": "в "} for p in paths]
    journal.save_journal(project / JOURNAL_REL, j)


def test_scenario_root_with_tools_in_a_core_clone(tmp_path):
    """«Корень при инструментах вне проекта», раскладка клона: файл корней без `""` не решает, чей это проект.
    Файл только в клоне — «файла нет», файлы проекта — «сверено», в карте только файлы проекта."""
    tools, project = _layout(tmp_path, tools_in_project=False, clone=True)
    (tools.parent / "docs" / "repo-contract.md").write_text("в этом месте\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "design-part1-viewer.md").write_text("в этом месте\n", encoding="utf-8")
    (project / "src" / "extension.ts").write_text("в этом месте\n", encoding="utf-8")
    _with_evidence(project, "docs/repo-contract.md", "docs/design-part1-viewer.md", "src/extension.ts")
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert view.returncode == 0, view.stderr
    assert _verdicts(view.stdout) == {"docs/repo-contract.md": "файла нет", "docs/design-part1-viewer.md": "сверено", "src/extension.ts": "сверено"}
    assert json.loads(view.stdout)["file_links"] == {"docs/design-part1-viewer.md": "docs/design-part1-viewer.md", "src/extension.ts": "src/extension.ts"}
    check = _core(tools, project, "check", JOURNAL_REL)
    assert "улик сверено 2 из 3" in check.stdout and "repo-contract.md" in check.stdout


def test_ordinary_clone_keeps_its_roots_file(tmp_path):
    """Инструменты клона и журнал того же клона: файл корней действует, `docs/` считается от клона, пути без префикса корня не имеют."""
    tools, project = _layout(tmp_path, tools_in_project=True, clone=True)
    (project / "docs" / "a.md").write_text("в этом месте\n", encoding="utf-8")
    _with_evidence(project, "docs/a.md", "src/both.py")
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert view.returncode == 0, view.stderr
    assert _verdicts(view.stdout) == {"docs/a.md": "сверено", "src/both.py": "корня для пути нет"}


def test_scenario_ordinary_installation_with_the_journal_in_a_subfolder(tmp_path):
    """«Обычная установка»: инструменты в `<x>/.symphysis/tools`, журнал в `<x>/sub` внутри корня файла: корни из файла, а не от подкаталога."""
    x = tmp_path / "установка с пробелом"
    tools = _copy_tools(x)
    sub = x / "sub"
    (x / "src").mkdir()
    (x / "src" / "only_x.py").write_text("в этом месте\n", encoding="utf-8")
    (sub / "src").mkdir(parents=True)
    (sub / "src" / "only_sub.py").write_text("в этом месте\n", encoding="utf-8")
    journal_file = sub / "openspec" / "changes" / "a" / "decisions.json"
    journal_file.parent.mkdir(parents=True)
    j = one_record_journal("src/only_x.py", "в ")
    j["records"][0]["options"][0]["evidence"] = [{"path": p, "quote": "в "} for p in ("src/only_x.py", "src/only_sub.py")]
    journal.save_journal(journal_file, j)
    view = _core(tools, sub, "view-json", "openspec/changes/a/decisions.json")
    assert view.returncode == 0, view.stderr
    assert _verdicts(view.stdout) == {"src/only_x.py": "сверено", "src/only_sub.py": "файла нет"}
    check = _core(tools, sub, "check", "openspec/changes/a/decisions.json")
    assert "улик сверено 1 из 2" in check.stdout, check.stderr


@pytest.mark.parametrize("content", [b"[]", b'{"": 1}', b"\xff\xfe", None], ids=["список", "значение не строка", "не UTF-8", "файла нет"])
def test_unusable_roots_file_outside_the_project_gives_the_project_root(tmp_path, content):
    """Файл корней вне проекта негоден в любом виде: единственный корень это проект, команда не падает."""
    tools, project = _layout(tmp_path, tools_in_project=False)
    roots = tools / "journal-roots.json"
    if content is None:
        roots.unlink()
    else:
        roots.write_bytes(content)
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert view.returncode == 0, view.stderr
    assert _verdicts(view.stdout) == {"src/both.py": "сверено", "src/only_project.py": "сверено", "src/only_install.py": "файла нет"}


@pytest.mark.parametrize("clone", [False, True], ids=["установка", "клон"])
def test_broken_roots_file_does_not_stop_commands_that_do_not_need_it(tmp_path, clone):
    """Инструменты вне проекта: битый файл корней команду не роняет, единственный корень это проект."""
    tools, project = _layout(tmp_path, tools_in_project=False, clone=clone)
    (tools / "journal-roots.json").write_text("{не json", encoding="utf-8")
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert view.returncode == 0, view.stderr
    assert _verdicts(view.stdout) == {"src/both.py": "сверено", "src/only_project.py": "сверено", "src/only_install.py": "файла нет"}
    check = _core(tools, project, "check", JOURNAL_REL)
    assert "улик сверено 2 из 3" in check.stdout, check.stderr
    page = _core(tools, project, "render-html", JOURNAL_REL, "--out", "openspec/changes/demo/symphysis.html")
    assert page.returncode == 0, page.stderr


def test_explicit_roots_beat_the_project_root_with_a_core_clone(tmp_path):
    tools, project = _layout(tmp_path, tools_in_project=False, clone=True)
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tools.parent)}), encoding="utf-8")
    view = _core(tools, project, "view-json", JOURNAL_REL, "--roots", roots)
    assert _verdicts(view.stdout)["src/only_install.py"] == "сверено"
