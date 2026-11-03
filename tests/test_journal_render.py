import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import pytest

import journal
import journal_render
from conftest import (FIX, ROOT, fake_apply, fake_status, fork_calls, fork_env, fork_record, fork_reply, install_fork_shim,
                      journal_of, one_record_journal, real_fork, real_project, requires_fork)

TEMPLATE = ROOT / "tools" / "playground-template.html"
LIVE_JSON = ROOT / "docs" / "plan-implementation.journal.json"
LIVE_MD = ROOT / "docs" / "plan-implementation.journal.md"


def strip_check_fields(j):
    """Копия журнала без полей, которых в markdown нет (см. `render_md`): поля сверки улик
    `line/found/verdict`, `reversibility` и `comments` записи, `generated` журнала — их источник только JSON."""
    j = copy.deepcopy(j)
    j.pop("generated", None)
    for rec in j["records"]:
        rec["reversibility"] = None
        rec["comments"] = []
        for ev in rec["evidence"] + [e for o in rec["options"] for e in o["evidence"]]:
            for key in ("line", "found", "verdict"):
                ev.pop(key, None)
    return j


def plan():
    return journal.import_md(FIX / "journal-plan.md")


def roundtrip(j):
    # `source` в markdown не пишется (это имя файла, из которого разобрали), его передаём.
    return journal.import_md_text(journal.render_md(j), source=j["source"])


def embedded(html):
    """JSON, который шаблон получил вместо `__JOURNAL_JSON__`."""
    start = html.index("const JOURNAL = ") + len("const JOURNAL = ")
    payload, _ = json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))
    return payload


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "journal.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


# --- тесты из брифа ---------------------------------------------------------

def test_render_md_roundtrip():
    j = journal.import_md(FIX / "journal-plan.md")
    j2 = roundtrip(j)
    assert strip_check_fields(j2) == strip_check_fields(j)


def test_render_md_has_anchor_per_record():
    j = journal.import_md(FIX / "journal-plan.md")
    md = journal.render_md(j)
    assert md.count("<!-- journal:F-") == 24


def test_render_html_embeds_json(tmp_path):
    j = journal.import_md(FIX / "journal-plan.md")
    html = journal.render_html(j, ROOT / "tools/playground-template.html")
    assert "__JOURNAL_JSON__" not in html and '"F-19"' in html and "</script>" in html


# --- markdown: якорь, шапка, формат ----------------------------------------

def test_anchor_is_the_line_right_after_the_heading():
    lines = journal.render_md(plan()).splitlines()
    heads = [i for i, line in enumerate(lines) if line.startswith("## F-")]
    assert len(heads) == 24
    for i in heads:
        rid = lines[i].split()[1]
        assert lines[i + 1] == f"<!-- journal:{rid} -->"


def test_import_ignores_anchor_comment():
    md = "# Т\n\n## F-01 Вопрос?\n<!-- journal:F-01 -->\n- вид: факт\n- статус: решён\n"
    rec = journal.import_md_text(md)["records"][0]
    assert rec["question"] == "Вопрос?" and rec["kind"] == "факт" and rec["status"] == "решён"


def test_render_md_is_stable_on_second_pass():
    once = journal.render_md(plan())
    twice = journal.render_md(journal.import_md_text(once, source="x"))
    assert twice == once


def test_header_names_the_json_and_keeps_the_intro():
    j = plan()
    assert j["intro"].startswith("Формат — из `plan-flexible-pipeline.md`")
    md = journal.render_md(j, json_name="plan-implementation.journal.json")
    head = md.split("\n## F-01")[0]
    assert head.startswith(f"# {j['title']}\n")
    assert "`plan-implementation.journal.json`" in head and "не править руками" in head
    assert j["intro"] in head
    j2 = journal.import_md_text(md)
    assert j2["intro"] == j["intro"] and j2["title"] == j["title"]


def test_header_line_without_json_name_is_still_there():
    md = journal.render_md(one_record_journal("a.md", "q"))
    assert "не править руками" in md.split("\n## F-01")[0]


def test_import_intro_is_text_between_title_and_first_record():
    md = ("# Т\n\n> Рендер из `x.json`, не править руками.\n\nПервый абзац.\n\nВторой.\n\n"
          "## F-01 В?\n- вид: факт\n")
    assert journal.import_md_text(md)["intro"] == "Первый абзац.\n\nВторой."


def test_fields_in_format_order():
    md = journal.render_md(plan())
    f01 = md.split("\n## F-02")[0]
    keys = [line[2:].split(":")[0] for line in f01.splitlines() if line.startswith("- ")]
    assert keys == ["вид", "статус", "адресат", "зависит от", "поставка", "варианты", "антиподы",
                    "рекомендация", "парковка", "находка", "улики", "решение", "следствия"]
    fact = md.split("\n## F-20")[1].split("\n## F-21")[0]
    keys = [line[2:].split(":")[0] for line in fact.splitlines() if line.startswith("- ")]
    assert keys == ["вид", "статус", "адресат", "зависит от", "поставка", "улики", "спор", "следствия"]


def test_option_lines_carry_evidence_then_unlikely():
    md = journal.render_md(plan())
    f01 = md.split("\n## F-02")[0].splitlines()
    i = f01.index("  - C. Файл на решение в стиле ADR (MADR/Nygard), журнал — каталог")
    assert f01[i + 1].startswith("    - улика: `upstream/gsd-core/")
    assert f01[i + 2].startswith("    - маловероятно: десятки файлов")


# --- рекомендация: сырая строка --------------------------------------------

def test_recommendation_keeps_the_raw_line_as_text():
    recs = {r["id"]: r for r in plan()["records"]}
    for rid in ("F-06", "F-08", "F-11", "F-18"):
        text = recs[rid]["recommendation"]["text"]
        assert text and text.startswith(recs[rid]["recommendation"]["option"])
    assert recs["F-06"]["recommendation"]["text"].startswith(
        "B для процедур и A для коротких правил; слово")
    assert recs["F-06"]["recommendation"]["option"] == "B"


def test_render_writes_recommendation_from_raw_text():
    j = plan()
    lines = journal.render_md(j).splitlines()
    forks = [r for r in j["records"] if r["recommendation"]]
    assert len(forks) == 19
    for r in forks:
        assert f"- рекомендация: {r['recommendation']['text']}" in lines


def test_recommendation_without_text_falls_back_to_option_and_why():
    j = one_record_journal("a.md", "q")
    j["records"][0]["recommendation"] = {"option": "A", "why": "потому что"}
    assert "- рекомендация: A — потому что" in journal.render_md(j).splitlines()


# --- «» вокруг слова человека и вопроса парковки ----------------------------

def test_unquote_strips_exactly_one_outer_pair_for_word_and_parking():
    md = ("# Т\n\n## F-01 Вопрос?\n- вид: развилка\n- статус: решён\n- варианты:\n  - A. а\n"
          "- парковка: человек — «вопрос «внутри» ещё»\n"
          "- решение: A — «слово «внутри» ещё», 2026-10-29\n")
    rec = journal.import_md_text(md)["records"][0]
    assert rec["decision"]["word"] == "слово «внутри» ещё"
    assert rec["parking"][0]["text"] == "вопрос «внутри» ещё"


def test_unquote_leaves_unquoted_and_half_quoted_values_alone():
    md = ("# Т\n\n## F-01 Вопрос?\n- вид: развилка\n- статус: решён\n- варианты:\n  - A. а\n"
          "- парковка: человек — «начало» и конец\n"
          "- решение: A — просто слово, 2026-10-29\n")
    rec = journal.import_md_text(md)["records"][0]
    assert rec["decision"]["word"] == "просто слово"
    assert rec["parking"][0]["text"] == "«начало» и конец"


@pytest.mark.parametrize("text, expected", [
    ("«а» и «б»", "«а» и «б»"),                # первая « закрыта раньше последней »: пара не внешняя
    ("«а «б» в»", "а «б» в"),                  # первая « закрыта последней »: пара внешняя
    ("««а» и «б»»", "«а» и «б»"),              # слово, само начавшееся с «а», обёрнуто один раз
    ("«просто»", "просто"),
    ("«»", ""),
    ("«скобка « без пары»", "скобка « без пары"),   # без баланса — прежнее поведение: снять внешнюю пару
    ("«начало» и конец", "«начало» и конец"),
    ("слово", "слово"),
])
def test_unquote_strips_the_outer_pair_only_when_the_first_guillemet_closes_at_the_end(text, expected):
    assert journal._unquote(text) == expected


def test_decision_word_of_two_quoted_phrases_survives_the_roundtrip():
    j = one_record_journal("a.md", "q")
    rec = j["records"][0]
    rec["status"] = "решён"
    rec["decision"] = {"option": "A", "word": "«а» и «б»", "date": "2026-10-29"}
    assert "- решение: A — ««а» и «б»», 2026-10-29" in journal.render_md(j)
    assert strip_check_fields(roundtrip(j)) == strip_check_fields(j)


def test_render_writes_word_and_parking_back_in_guillemets():
    md = journal.render_md(plan())
    lines = md.splitlines()
    assert any(line.startswith("- решение: B — «видимо тогда вариант B") and line.endswith("», 2026-10-29")
               for line in lines)
    assert any(line.startswith("- парковка: материалы — «json разбирать") and line.endswith("»")
               for line in lines)
    assert "- решение: A, 2026-10-29" in lines          # F-04: слова нет, кавычек нет


def test_inner_guillemets_survive_the_roundtrip():
    j = one_record_journal("a.md", "q")
    rec = j["records"][0]
    rec["status"] = "решён"
    rec["decision"] = {"option": "A", "word": "слово «внутри» ещё", "date": "2026-10-29"}
    rec["parking"] = [{"addressee": "человек", "text": "вопрос «внутри» ещё", "finding": "ответ"}]
    md = journal.render_md(j)
    assert "- решение: A — «слово «внутри» ещё», 2026-10-29" in md
    assert "- парковка: человек — «вопрос «внутри» ещё»" in md
    assert strip_check_fields(roundtrip(j)) == strip_check_fields(j)


# --- пометка «добавлен человеком» -------------------------------------------

def test_added_marker_is_not_doubled():
    source = (FIX / "journal-plan.md").read_text(encoding="utf-8")
    j = plan()
    md = journal.render_md(j)
    assert md.count("(добавлен человеком") == source.count("(добавлен человеком") >= 1
    added = [o for r in j["records"] for o in r["options"] if o["added"]]
    assert added and all(o["text"].count("(добавлен человеком") == 1 for o in added)


def test_added_option_without_marker_gets_it_once():
    j = one_record_journal("a.md", "q")
    opt = j["records"][0]["options"][0]
    opt["added"], opt["text"] = True, "свой вариант"
    md = journal.render_md(j)
    assert md.count("(добавлен человеком") == 1
    assert journal.import_md_text(md)["records"][0]["options"][0]["added"] is True


# --- HTML ------------------------------------------------------------------

def test_render_html_payload_follows_the_viewer_contract():
    j = plan()
    data = embedded(journal.render_html(j, TEMPLATE))
    recs = {r["id"]: r for r in data["records"]}
    park = j["records"][0]["parking"][0]
    assert recs["F-01"]["parking"] == [{"addressee": park["addressee"], "text": park["text"],
                                        "finding": park["finding"]}]
    assert recs["F-01"]["finding"] == park["finding"]
    assert recs["F-02"]["parking"] == [] and recs["F-02"]["finding"] == ""
    forks = [r for r in j["records"] if r["kind"] == "развилка"]
    assert data["source"] == "journal-plan.md" and data["title"] == j["title"]
    assert data["stats"]["records"] == 24 and data["stats"]["forks"] == 19 and data["stats"]["facts"] == 5
    assert data["stats"]["decided"] == sum(1 for r in forks if r["decision"]) and data["stats"]["parked"] == 1
    assert "generated" not in data      # дата сборки — из журнала; своей даты рендер не придумывает


def test_render_html_counts_checked_evidence(tmp_path):
    (tmp_path / "a.md").write_text("q\n", encoding="utf-8")
    j = one_record_journal("a.md", "q")
    journal.check_evidence(j, {"": tmp_path})
    data = embedded(journal.render_html(j, TEMPLATE))
    assert data["stats"]["evidence_total"] == 1 and data["stats"]["evidence_found"] == 1
    ev = data["records"][0]["options"][0]["evidence"][0]
    assert ev["line"] == 1 and ev["found"] is True and ev["verdict"] == "сверено"


def test_render_html_escapes_script_close_tag():
    j = one_record_journal("a.md", "q")
    j["records"][0]["question"] = "до </script> после"
    html = journal.render_html(j, TEMPLATE)
    assert html.count("</script>") == TEMPLATE.read_text(encoding="utf-8").count("</script>")
    assert embedded(html)["records"][0]["question"] == "до </script> после"


def test_render_html_requires_the_placeholder(tmp_path):
    template = tmp_path / "t.html"
    template.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="__JOURNAL_JSON__"):
        journal.render_html(plan(), template)


def test_renderers_do_not_mutate_the_journal():
    j = plan()
    before = copy.deepcopy(j)
    journal.render_md(j)
    journal.render_html(j, TEMPLATE)
    assert j == before


# --- командная строка ------------------------------------------------------

def test_cli_render_md_writes_crlf_and_roundtrips(tmp_path):
    src, out = tmp_path / "j.json", tmp_path / "j.md"
    j = plan()
    journal.save_journal(src, j)
    run = run_cli("render-md", src, "--out", out)
    assert run.returncode == 0, run.stderr
    raw = out.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode("utf-8")
    assert "`j.json`" in text.split("\n## F-01")[0]
    assert strip_check_fields(journal.import_md_text(text, source=j["source"])) == strip_check_fields(j)


def html_fixture(tmp_path, quote):
    """Журнал с одной уликой и файл корней: всё внутри `tmp_path`, машина не важна."""
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    src = tmp_path / "j.json"
    journal.save_journal(src, one_record_journal("a.md", quote))
    return src, roots


def test_cli_render_html_writes_lf_and_checks_evidence(tmp_path):
    src, roots = html_fixture(tmp_path, "дв")
    before = src.read_bytes()
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 1 из 1" in run.stdout and "[!!]" not in run.stdout
    raw = out.read_bytes()
    assert b"\r" not in raw
    data = embedded(raw.decode("utf-8"))
    assert data["stats"]["evidence_total"] == 1 and data["stats"]["evidence_found"] == 1
    ev = data["records"][0]["options"][0]["evidence"][0]
    assert (ev["line"], ev["found"], ev["verdict"]) == (2, True, "сверено")
    assert src.read_bytes() == before     # сверка в памяти: журнал-источник не меняется


def test_cli_render_html_reports_unmatched_evidence_and_still_renders(tmp_path):
    src, roots = html_fixture(tmp_path, "нет такого")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 0 из 1" in run.stdout
    assert "[!!] не сверено — F-01: a.md «нет такого» — цитаты нет дословно" in run.stdout
    data = embedded(out.read_text(encoding="utf-8"))
    assert data["stats"]["evidence_found"] == 0
    assert data["records"][0]["options"][0]["evidence"][0]["found"] is False


@pytest.mark.parametrize("command", ["render-md", "render-html"])
def test_cli_render_refuses_an_invalid_journal(tmp_path, command):
    j = plan()
    j["records"][2]["status"] = "готов"
    src, out = tmp_path / "j.json", tmp_path / "out"
    journal.save_journal(src, j)
    run = run_cli(command, src, "--out", out)
    assert run.returncode == 1 and "F-03" in run.stderr
    assert not out.exists()


# --- атака: parse_attack_md, вторая метка шаблона, --attack ----------------

ATTACK_FIX = FIX / "attack"
FAKE_SHA = "0123456789abcdef" * 4
ROW_KEYS = ["claim", "section", "lens", "invariant", "severity", "support", "fix"]


def embedded_attack(html):
    """JSON, который шаблон получил вместо `__ATTACK_JSON__`."""
    start = html.index("const ATTACK = ") + len("const ATTACK = ")
    payload, _ = json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))
    return payload


def test_parse_attack_md_decisions_form():
    att = journal.parse_attack_md(ATTACK_FIX / "decisions.md")
    assert att["path"] == str(ATTACK_FIX / "decisions.md")
    assert att["frontmatter"]["status"] == "gaps_found"
    # форма decisions (`target` / `target_sha256`) наружу отдаётся той же формой `targets[]`
    assert att["frontmatter"]["targets"] == [{"path": "decisions.json", "sha256": FAKE_SHA}]
    rows = att["rows"]
    assert len(rows) == 3 and all(list(r) == ROW_KEYS for r in rows)
    assert rows[0]["section"] == "F-02, следствия" and rows[0]["support"] == "по спеке не выводится"
    assert rows[1]["support"] == "нет" and rows[1]["severity"] == "блокер"
    cover = next(r for r in rows if r["claim"] == "чисто")
    assert cover["lens"] == "coverage" and cover["invariant"] == "—" and cover["fix"] == "—"


def test_parse_attack_md_artifacts_form():
    att = journal.parse_attack_md(ATTACK_FIX / "artifacts.md")
    targets = att["frontmatter"]["targets"]
    assert [t["path"] for t in targets] == ["decisions.json", "specs/demo-cap/spec.md"]   # журнал первым
    assert targets[0]["sha256"] == FAKE_SHA and targets[1]["sha256"] == "fedcba9876543210" * 4
    assert att["frontmatter"]["status"] == "gaps_found"
    assert [r["lens"] for r in att["rows"]] == ["requirement-coverage", "honest-verifier", "coverage"]
    assert att["rows"][0]["section"] == "specs/demo-cap/spec.md, Requirement: работа по схеме"
    assert att["rows"][0]["fix"] == "правка артефакта"


def test_parse_attack_md_skips_placeholders_and_rejects_missing_table(tmp_path):
    text = (ATTACK_FIX / "decisions.md").read_text(encoding="utf-8")
    assert "| <утверждение журнала> |" in text        # строка-подстановка шаблона в фикстуре оставлена
    rows = journal.parse_attack_md(ATTACK_FIX / "decisions.md")["rows"]
    assert not any(r["claim"].startswith("<") for r in rows)
    no_table = tmp_path / "broken.md"
    no_table.write_text("---\nstatus: gaps_found\ntarget: decisions.json\ntarget_sha256:\n---\n\n# Атака\n\n"
                        "таблицы нет\n", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.md"):
        journal.parse_attack_md(no_table)
    no_front = tmp_path / "nofront.md"
    no_front.write_text(text.split("---\n", 2)[2], encoding="utf-8")   # та же таблица, frontmatter снят
    with pytest.raises(ValueError, match="nofront.md"):
        journal.parse_attack_md(no_front)


def test_render_html_without_attacks_embeds_empty_list():
    html = journal.render_html(plan(), TEMPLATE)
    assert "__ATTACK_JSON__" not in html
    assert embedded_attack(html) == []
    assert "sha256" not in embedded(html)      # хеш журнала — только когда подан


def test_render_html_with_attacks_embeds_rows_and_sha():
    attacks = [journal.parse_attack_md(ATTACK_FIX / "decisions.md"),
               journal.parse_attack_md(ATTACK_FIX / "artifacts.md")]
    html = journal.render_html(plan(), TEMPLATE, attacks=attacks, journal_sha256="ab" * 32)
    assert embedded_attack(html) == attacks      # результаты parse_attack_md как есть
    assert embedded(html)["sha256"] == "ab" * 32


def test_render_html_requires_both_placeholders(tmp_path):
    template = tmp_path / "t.html"
    template.write_text("<html>const JOURNAL = __JOURNAL_JSON__;</html>", encoding="utf-8")
    with pytest.raises(ValueError, match="__ATTACK_JSON__"):
        journal.render_html(plan(), template)
    template.write_text("<html>const ATTACK = __ATTACK_JSON__;</html>", encoding="utf-8")
    with pytest.raises(ValueError, match="__JOURNAL_JSON__"):
        journal.render_html(plan(), template)


def attack_path_from_cwd(path) -> str:
    try:
        return os.path.relpath(path).replace("\\", "/")
    except ValueError:
        return Path(path).name


def test_cli_render_html_attack_flag(tmp_path):
    src, roots = html_fixture(tmp_path, "дв")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots,
                  "--attack", ATTACK_FIX / "decisions.md", "--attack", ATTACK_FIX / "artifacts.md")
    assert run.returncode == 0, run.stderr
    html = out.read_text(encoding="utf-8")
    assert '"rows"' in html and '"sha256"' in html
    attacks = embedded_attack(html)
    # Журнал вне openspec/changes/: корень — каталог вызова; путь от него с «/», на другом диске только имя (F-72).
    assert [a["path"] for a in attacks] == [attack_path_from_cwd(ATTACK_FIX / "decisions.md"), attack_path_from_cwd(ATTACK_FIX / "artifacts.md")]
    assert [len(a["rows"]) for a in attacks] == [3, 3]
    assert embedded(html)["sha256"] == journal.sha256_file(src)   # хеш журнала — по байтам файла


def test_cli_render_html_attack_parse_error_exits_2(tmp_path):
    src, roots = html_fixture(tmp_path, "дв")
    broken = tmp_path / "attack.md"
    broken.write_text("# без frontmatter и без таблицы\n", encoding="utf-8")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots, "--attack", broken)
    assert run.returncode == 2, run.stdout + run.stderr
    assert run.stderr.startswith("[!!] ") and "attack.md" in run.stderr
    assert not out.exists()


# --- режимы «проверка» и «атака»: прогон скрипта шаблона без браузера ----------

node = shutil.which("node")
requires_node = pytest.mark.skipif(node is None, reason="нет node: шаблон просмотрщика не прогнать")


def smoke(tmp_path, html, state=None):
    """Итог `viewer-smoke.js`: панели режимов и промпт; `state` — состояние браузера, `__suffixes__` в нём —
    значения ключей `:mode` и `:attack`."""
    page = tmp_path / "v.html"
    page.write_text(html, encoding="utf-8", newline="\n")
    args = [node, str(FIX / "viewer-smoke.js"), str(page)]
    if state is not None:
        (tmp_path / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        args.append(str(tmp_path / "state.json"))
    run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def fixture_attacks():
    return [journal.parse_attack_md(ATTACK_FIX / "decisions.md"), journal.parse_attack_md(ATTACK_FIX / "artifacts.md")]


@requires_node
def test_viewer_state_belongs_to_one_page_not_to_every_journal(tmp_path):
    """Состояние браузера — своё у каждой страницы: у всех журналов `source` один (`decisions.json`), и ключ по нему
    приносил в промпт нового журнала варианты и буквы из другого журнала с теми же номерами F-NN."""
    html = journal.render_html(plan(), TEMPLATE, journal_sha256=FAKE_SHA)
    note = "замечание со страницы другого журнала"
    own = smoke(tmp_path, html, {"notes": note, "__pathname__": "/a/symphysis.html", "__key__": "symphysis:/a/symphysis.html"})
    assert note in own["out"]
    other = smoke(tmp_path, html, {"notes": note, "__pathname__": "/b/symphysis.html", "__key__": "symphysis:/a/symphysis.html"})
    assert note not in other["out"]


@requires_node
def test_viewer_check_mode_projects_records_like_render_design(tmp_path):
    """Режим «проверка»: снимок с хешем, счётчики, группа по дате решения («в одну сторону» первой, как
    `render_design`), проекция «куда уйдёт»: решение → Decisions, проба Specify → spec.md, Dismiss → никуда
    с причиной, факт → Context."""
    j = plan()
    recs = {r["id"]: r for r in j["records"]}
    recs["F-02"]["reversibility"] = {"level": "в одну сторону", "why": "контракт"}
    recs["F-04"]["outcome"] = {"kind": "проба", "value": "Specify", "reason": ""}
    recs["F-05"]["outcome"] = {"kind": "проба", "value": "Dismiss", "reason": "пары равных нет"}
    out = smoke(tmp_path, journal.render_html(j, TEMPLATE, journal_sha256=FAKE_SHA), {"__suffixes__": {":mode": "check"}})
    check = out["check"]
    assert FAKE_SHA[:12] in check and "атака не подана" in check and "вердиктом не считается" in check
    assert "решено <b>19</b>" in check and "открыто <b>0</b>" in check and "улик не найдено <b>" in check
    ids = re.findall(r'class="id mono">(F-\d+)<', check)
    assert ids[:3] == ["F-02", "F-01", "F-03"]          # F-02 «в одну сторону» — первой в группе 2026-10-29
    assert "<h3>2026-10-29 · 17</h3>" in check          # 19 решённых минус две пробы
    assert "→ design.md › Decisions · в одну сторону — первой" in check
    assert "→ spec.md · исход Specify" in check and "→ никуда · причина: пары равных нет" in check
    assert "→ design.md › Context" in check and check.count("design.md › Context") == 5
    assert "design.md › Open Questions → research/" in check     # парковка F-01 «материалы»
    assert "Researcher" not in check and "Исследователь" not in check
    assert out["modes"].count("<button") == 3 and 'class="small active" data-mode="check"' in out["modes"]


@requires_node
def test_viewer_attack_mode_groups_by_lens_and_returns_disputes_as_notes(tmp_path):
    """Режим «атака»: линза → тяжесть → строки в порядке списка линз файла, линза без строк не показана; раздел `F-NN, поле`
    — ссылка на карточку; споры из browser storage уходят в одну строку «Замечания к схеме:» после замечаний
    режима 1, через « · », и `parse_answers` читает её одной заметкой."""
    attacks = fixture_attacks()
    row = attacks[0]["rows"][1]                           # F-01, context-compliance, блокер
    key = f'{attacks[0]["path"]}|{row["section"]}|{row["claim"]}'
    html = journal.render_html(plan(), TEMPLATE, attacks=attacks, journal_sha256=FAKE_SHA)
    out = smoke(tmp_path, html, {"notes": "стрелка лишняя", "__suffixes__": {
        ":mode": "attack", ":attack": {"disputes": {key: "опора есть:\n  улика F-01 сверена"}}}})
    attack = out["attack"]
    assert re.findall(r"<h2><code>([a-z-]+)</code>", attack) == ["context-compliance", "claim-authority", "coverage"]
    assert attack.count("<h2>вне списка") == 1             # у артефактов все три линзы фикстуры — не из списка артефактов
    assert "хеш журнала совпал" in attack and "вердикт устарел" not in attack
    assert 'data-goto="F-01"' in attack and "вне списка" not in attack.split("<h2>")[1]
    assert "Researcher" not in attack and "Исследователь" not in attack
    assert "атака · 6" in out["modes"]
    last = out["out"].splitlines()[-1]
    assert last == ("Замечания к схеме: стрелка лишняя · атака " + attacks[0]["path"] + " · context-compliance · «"
                    + row["claim"][:59] + "…» — спор: опора есть: улика F-01 сверена")
    notes = [op for op in journal.parse_answers(out["out"]) if op["op"] == "note"]
    assert len(notes) == 1 and notes[0]["text"] == last[len("Замечания к схеме: "):]


@requires_node
def test_viewer_attack_mode_marks_stale_verdict_and_missing_attack(tmp_path):
    attacks = fixture_attacks()
    stale = smoke(tmp_path, journal.render_html(plan(), TEMPLATE, attacks=attacks, journal_sha256="ff" * 32),
                  {"__suffixes__": {":mode": "check"}})
    assert "атака: gaps_found" in stale["check"] and "вердикт устарел: журнал изменён после атаки" in stale["check"]
    none = smoke(tmp_path, journal.render_html(plan(), TEMPLATE), {"__suffixes__": {":mode": "attack"}})
    assert "атака не подана: <code>render-html --attack" in none["attack"]
    assert "Замечания к схеме" not in none["out"]


# --- заметки: раздел «Заметки» в конце markdown ------------------------------

NOTES = [
    {"date": "2026-10-30",
     "text": "круг 1 закончен: решений 2, фактов 1, открытых развилок 0, парковок материалам 1"},
    {"date": "2026-10-31", "text": "стрелка F-03 → F-15 лишняя\nи вторая строка"},
]


def test_render_md_writes_notes_as_the_last_section():
    j = one_record_journal("a.md", "q")
    assert "## Заметки" not in journal.render_md(j)
    j["notes"] = copy.deepcopy(NOTES)
    md = journal.render_md(j)
    assert md.index("## Заметки") > md.index("## F-01")
    tail = md.split("\n## Заметки\n")[1]
    assert tail.splitlines() == [
        "- 2026-10-30 — круг 1 закончен: решений 2, фактов 1, открытых развилок 0, парковок материалам 1",
        "- 2026-10-31 — стрелка F-03 → F-15 лишняя",
        "  и вторая строка",
    ]


def test_import_reads_the_notes_section_back_into_notes():
    j = one_record_journal("a.md", "q")
    j["notes"] = copy.deepcopy(NOTES)
    back = roundtrip(j)
    assert back["notes"] == NOTES
    assert journal.validate_journal(back) == []
    assert list(back).index("notes") < list(back).index("records")
    assert "notes" not in roundtrip(one_record_journal("a.md", "q"))


# --- исход: строка «- исход:» между решением и следствиями --------------------

PROBE_OUTCOME = {"kind": "проба", "value": "Dismiss",
                 "reason": "выход канонически отсортирован — пары равных нет"}


def decided_probe(outcome):
    """Решённый кандидат пробы: решение, исход и следствия — три поля, порядок которых проверяется."""
    j = one_record_journal("a.md", "q")
    rec = j["records"][0]
    rec["status"] = "решён"
    rec["decision"] = {"option": "A", "word": "слово", "date": "2026-10-30"}
    rec["outcome"] = outcome
    rec["consequences"] = "в spec.md: сценарий"
    return j


def test_render_md_writes_outcome_between_decision_and_consequences():
    lines = journal.render_md(decided_probe(PROBE_OUTCOME)).splitlines()
    keys = [line[2:].split(":")[0] for line in lines if line.startswith("- ")]
    assert keys[-3:] == ["решение", "исход", "следствия"]
    assert "- исход: проба — Dismiss — выход канонически отсортирован — пары равных нет" in lines
    assert "исход" in journal.render_md.__doc__


def test_render_md_omits_the_reason_tail_when_reason_is_empty():
    md = journal.render_md(decided_probe({"kind": "проба", "value": "Defer", "reason": ""}))
    assert "- исход: проба — Defer\n" in md
    assert "- исход:" not in journal.render_md(one_record_journal("a.md", "q"))


@pytest.mark.parametrize("outcome", [
    PROBE_OUTCOME,                                                   # причина сама содержит « — »
    {"kind": "проба", "value": "Defer", "reason": ""},               # причины нет — хвоста нет
    {"kind": "вопрос", "value": "не узнать по файлам", "reason": "файлов нет"},
    {"kind": "проба", "value": "Defer", "reason": "   "},            # причина из пробелов — как пустая
])
def test_outcome_survives_the_roundtrip(outcome):
    j = decided_probe(outcome)
    back = roundtrip(j)
    expected = {**outcome, "reason": outcome["reason"].strip()}      # импорт причину обрезает
    assert back["records"][0]["outcome"] == expected
    j["records"][0]["outcome"] = expected
    assert strip_check_fields(back) == strip_check_fields(j)


def test_import_skips_an_outcome_line_not_by_form(capsys):
    head = "# Т\n\n## F-01 В?\n- вид: развилка\n- статус: открыт\n- варианты:\n  - A. а\n"
    assert journal.import_md_text(head + "- исход: —\n")["records"][0]["outcome"] is None
    rec = journal.import_md_text(head + "- исход: что-то — Defer\n")["records"][0]
    assert rec["outcome"] is None
    assert "F-01: исход не по форме" in capsys.readouterr().err


# --- живой журнал ----------------------------------------------------------

def test_live_journal_roundtrips_through_markdown():
    j = journal.load_journal(LIVE_JSON)
    assert strip_check_fields(roundtrip(j)) == strip_check_fields(j)


def test_committed_markdown_is_the_render_of_the_json():
    j = journal.load_journal(LIVE_JSON)
    assert LIVE_MD.read_text(encoding="utf-8") == journal.render_md(j, json_name=LIVE_JSON.name)


# --- что сказано в документации модуля и в --help ----------------------------

def test_docs_state_unmatched_prefix_and_check_exit_code():
    doc = " ".join(journal.__doc__.split())
    assert "корня для пути нет" in doc and "отката на корень symphysis нет" in doc
    helptext = " ".join(run_cli("-h").stdout.split())
    assert "негодный по схеме журнал — код 1" in helptext


# --- разбор ячейки атаки: экранирование, backticks, пустые ячейки (5.7) ----------

ATTACK_HEAD = ("---\nstatus: gaps_found\ntarget: decisions.json\ntarget_sha256:\n---\n\n"
               "| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |\n"
               "| --- | --- | --- | --- | --- | --- | --- |\n")


def attack_file(tmp_path, *rows, name="attack.md"):
    path = tmp_path / name
    path.write_text(ATTACK_HEAD + "".join(row + "\n" for row in rows), encoding="utf-8")
    return path


def test_pipe_in_backticks_and_escaped_pipe(tmp_path):
    row = r"| `grep -c '| справка |'` | F-23 | coverage | а \| б | справка | нет | — |"
    cells = journal.parse_attack_md(attack_file(tmp_path, row))["rows"][0]
    assert cells["claim"] == "`grep -c '| справка |'`"      # черта в backticks — текст, backticks сохранены
    assert cells["invariant"] == "а | б"                    # \| — литеральная черта
    assert cells["support"] == "нет" and cells["fix"] == "—"


def test_escaped_backslash_and_unclosed_backtick(tmp_path):
    ok = r"| `\\|` | F-34 | coverage | x | справка | нет | — |"
    cells = journal.parse_attack_md(attack_file(tmp_path, ok))["rows"][0]
    assert cells["claim"] == r"`\|`"                        # в коде: \\ -> \, голая | — текст
    # вне кода \\| — литеральная косая и разделитель: ячейка «a\», следом «b»
    assert journal_render._split_row(r"|a\\|b |") == (["a\\", "b "], None)
    bad = attack_file(tmp_path, "| `открыт | F-01 | coverage | x | справка | нет | — |", name="bad.md")
    with pytest.raises(ValueError) as err:
        journal.parse_attack_md(bad)
    msg = str(err.value)
    assert "bad.md:9:" in msg and "«Утверждение»" in msg and "backtick" in msg


def test_escapes_inside_code_and_lone_backslash(tmp_path):
    r"""Триаж 5B: внутри backticks `\|` — `|`, `\\` — `\`; обратная косая перед иным символом литеральна;
    `\\|` вне кода через `parse_attack_md` — литеральная косая и разделитель."""
    row = r"| `a\|b` и `c:\\d` | F-23 | coverage | x\y и `\n` | справка | нет | — |"
    cells = journal.parse_attack_md(attack_file(tmp_path, row))["rows"][0]
    assert cells["claim"] == r"`a|b` и `c:\d`"
    assert cells["invariant"] == r"x\y и `\n`"
    outside = attack_file(tmp_path, r"| a\\| F-34 | coverage | x | справка | нет | — |", name="outside.md")
    cells = journal.parse_attack_md(outside)["rows"][0]
    assert cells["claim"] == "a\\" and cells["section"] == "F-34" and cells["fix"] == "—"


def test_empty_required_cell_names_the_column(tmp_path):
    path = attack_file(tmp_path, "| чисто | F-03 | coverage |  | справка | есть | — |", name="empty.md")
    with pytest.raises(ValueError) as err:
        journal.parse_attack_md(path)
    assert "empty.md:9:" in str(err.value) and "«Инвариант»" in str(err.value)


def test_wrong_cell_count_reports_the_number(tmp_path):
    path = attack_file(tmp_path, "| а | б | coverage | x | справка | нет |", name="six.md")
    with pytest.raises(ValueError, match=r"six.md:9: .*ячеек 6, нужно 7"):
        journal.parse_attack_md(path)


def test_cli_render_html_broken_attack_file_exits_2_with_position(tmp_path):
    src, roots = html_fixture(tmp_path, "дв")
    broken = attack_file(tmp_path, "| `открыт | F-01 | coverage | x | справка | нет | — |", name="broken-cell.md")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots, "--attack", broken)
    assert run.returncode == 2, run.stdout + run.stderr
    assert "broken-cell.md:9:" in run.stderr and "Утверждение" in run.stderr
    assert not out.exists()


# --- режим «атака»: фильтр, счётчики, блок записи, слуги, понижение, улики без проверки ---------

JOURNAL_TARGET = [{"path": "decisions.json", "sha256": ""}]
ARTIFACT_TARGETS = JOURNAL_TARGET + [{"path": "design.md", "sha256": ""}]


def arow(section="F-01, decision", lens="context-compliance", severity="блокер", support="нет", claim="утверждение",
         fix="правка записи", invariant="инвариант"):
    return {"claim": claim, "section": section, "lens": lens, "invariant": invariant, "severity": severity,
            "support": support, "fix": fix}


def afile(rows, targets=JOURNAL_TARGET, path="attack/decisions.md", status="gaps_found"):
    return {"path": path, "frontmatter": {"status": status, "targets": targets}, "rows": rows}


def attack_view(tmp_path, attacks, suffixes=None, j=None):
    """Панели страницы в режиме «атака»; `suffixes` — дополнительные ключи browser storage (`:lens`)."""
    state = {"__suffixes__": dict({":mode": "attack"}, **(suffixes or {}))}
    return smoke(tmp_path, journal.render_html(j or plan(), TEMPLATE, attacks=attacks, journal_sha256=FAKE_SHA), state)


def without_rows(attack_html):
    """Шапки файлов и фильтр: всё, кроме контейнеров строк (`attack-rows` … маркер конца)."""
    return re.sub(r'<div class="attack-rows">.*?<!--/attack-rows-->', "", attack_html, flags=re.S)


@requires_node
def test_viewer_attack_has_lens_filter_and_severity_counters_outside_the_rows(tmp_path):
    """6.1: переключатель линз («все» и слуги файла) и блок счётчиков тяжести по всему файлу стоят вне контейнера строк."""
    rows = [arow(lens="context-compliance"), arow(lens="context-compliance", claim="второй"),
            arow(lens="claim-authority", severity="справка", support="есть"),
            arow(lens="coverage", severity="предупреждение", support="по спеке не выводится")]
    attack = attack_view(tmp_path, [afile(rows)])["attack"]
    assert 'id="lensFilter"' in attack and 'data-lens="all"' in attack
    for slug in ("context-compliance", "claim-authority", "coverage"):
        assert f'data-lens="{slug}"' in attack
    assert 'data-lens="scenario-run"' not in attack and 'data-lens="__outside__"' not in attack
    assert "блокеров <b>2</b> · предупреждений <b>1</b> · справок <b>1</b>" in without_rows(attack)
    assert "блокеров" not in attack[attack.index('<div class="attack-rows">'):attack.index("<!--/attack-rows-->")]


@requires_node
def test_viewer_attack_filter_hides_groups_but_not_blocker_counters(tmp_path):
    """Сценарий «Фильтр и счётчик блокеров»: при фильтре «claim-authority» видны строки этой линзы, шапка по-прежнему
    показывает «блокеров 2» по всему файлу (F-56.E)."""
    rows = [arow(lens="context-compliance", claim="блокер один"), arow(lens="context-compliance", claim="блокер два"),
            arow(lens="claim-authority", severity="справка", support="есть", claim="справка про числа")]
    attack = attack_view(tmp_path, [afile(rows)], {":lens": "claim-authority"})["attack"]
    assert "справка про числа" in attack and "блокер один" not in attack and "блокер два" not in attack
    assert re.findall(r"<h2><code>([a-z-]+)</code>", attack) == ["claim-authority"]
    assert 'class="small active" data-lens="claim-authority"' in attack
    assert "блокеров <b>2</b>" in without_rows(attack)
    # линзы, которой в файлах нет, фильтр не держит: страница показывает всё
    stale = attack_view(tmp_path, [afile(rows)], {":lens": "scenario-run"})["attack"]
    assert "блокер один" in stale and 'class="small active" data-lens="all"' in stale


@requires_node
def test_viewer_attack_lens_lists_follow_the_target_of_the_file(tmp_path):
    """Журнал (`decisions.json` — единственная цель): context-compliance, claim-authority, claim-extraction, coverage;
    артефакты: scenario-run, claim-extraction. Прочие слуги — «вне списка»: в тяжести считаются, в линзе нет."""
    jr = [arow(lens=s, claim=f"ж-{s}") for s in ("context-compliance", "claim-authority", "claim-extraction", "coverage", "scenario-run", "style")]
    ar = [arow(section="design.md", lens=s, claim=f"а-{s}") for s in ("scenario-run", "claim-extraction", "coverage", "requirement-coverage")]
    attack = attack_view(tmp_path, [afile(jr), afile(ar, ARTIFACT_TARGETS, "attack/artifacts.md")])["attack"]
    groups = re.findall(r"<h2>(?:<code>([a-z-]+)</code>|(вне списка))", attack)
    assert groups == [("context-compliance", ""), ("claim-authority", ""), ("claim-extraction", ""), ("coverage", ""),
                      ("", "вне списка"), ("scenario-run", ""), ("claim-extraction", ""), ("", "вне списка")]
    outside_journal = attack.split("<h2>вне списка")[1]
    assert "ж-scenario-run" in outside_journal and "ж-style" in outside_journal and "строка невалидна" in outside_journal
    heads = without_rows(attack)
    assert heads.count("блокеров <b>6</b>") == 1 and heads.count("блокеров <b>4</b>") == 1      # тяжесть — по всему файлу
    assert "по линзе: <code>context-compliance</code> <b>1</b> · <code>claim-authority</code> <b>1</b>" in heads
    assert "строк вне списка (невалидны, в счётчике линз их нет): <b>2</b>" in heads
    assert 'data-lens="__outside__"' in attack and 'data-lens="requirement-coverage"' not in attack


@requires_node
def test_viewer_attack_row_has_a_record_block(tmp_path):
    """6.2 и сценарий «Текст записи у строки»: `<details>` с вопросом записи, выбранным вариантом и переходом; без записи блока нет."""
    j = plan()
    rec = {r["id"]: r for r in j["records"]}["F-02"]
    picked = next(o for o in rec["options"] if o["letter"] == rec["decision"]["option"])
    rows = [arow(section="F-02, decision"), arow(section="F-99, decision", claim="нет такой записи"),
            arow(section="intro", claim="раздел без записи")]
    attack = attack_view(tmp_path, [afile(rows)], j=j)["attack"]
    assert attack.count('<details class="recblock">') == 1
    block = attack.split('<details class="recblock">')[1].split("</details>")[0]
    assert rec["question"].split("`")[0] in block and f'<span class="letter">{picked["letter"]}.</span>' in block
    assert picked["text"].split("`")[0][:20] in block
    assert 'href="#F-02" data-goto="F-02"' in block
    assert attack.count('data-goto="F-02"') == 2          # ссылка раздела в шапке строки и переход из блока
    assert "F-99" in attack and 'href="#F-99"' not in attack


@requires_node
def test_viewer_attack_demotion_without_reason_is_visible(tmp_path):
    """F-54.E, сценарий «Понижение без причины»: опора «нет» и тяжесть ниже блокера без причины в скобках — пометка;
    с причиной — видимая причина; опора «есть» и «по спеке не выводится» понижением не считаются."""
    rows = [arow(severity="предупреждение", support="нет", claim="без причины"),
            arow(severity="предупреждение (решено человеком в F-11)", support="нет: ничем не подтверждено", claim="с причиной"),
            arow(severity="блокер", support="нет", claim="блокер"),
            arow(severity="справка", support="есть: файл:1 «цитата»", claim="есть опора"),
            arow(severity="предупреждение", support="по спеке не выводится", claim="не выводится")]
    attack = attack_view(tmp_path, [afile(rows)])["attack"]
    cards = attack.split('<div class="card attackrow')[1:]
    by_claim = {re.search(r'<div class="q">([^<]*)</div>', c).group(1): c for c in cards}
    assert "понижение без причины" in by_claim["без причины"] and "понижено:" not in by_claim["без причины"]
    assert "понижено: решено человеком в F-11" in by_claim["с причиной"] and "понижение без причины" not in by_claim["с причиной"]
    for claim in ("блокер", "есть опора", "не выводится"):
        assert "понижени" not in by_claim[claim], claim
    assert "блокеров <b>1</b> · предупреждений <b>3</b>" in without_rows(attack)       # скобка тяжесть не меняет


@requires_node
def test_viewer_unchecked_evidence_is_neutral_not_missing(tmp_path):
    """Улика `found: null` («не проверить: бинарный файл») показана нейтрально, не как «не найдено»."""
    j = plan()
    j["records"][0]["evidence"] = [
        {"path": "a.bin", "quote": "q", "line": None, "found": None, "verdict": "не проверить: бинарный файл"},
        {"path": "b.md", "quote": "q", "line": None, "found": False, "verdict": "цитаты нет дословно"}]
    cards = smoke(tmp_path, journal.render_html(j, TEMPLATE))["cards"]
    assert '<b class="mute">не проверить: бинарный файл</b>' in cards
    assert "не найдено: не проверить" not in cards and '<b class="bad">не найдено: цитаты нет дословно</b>' in cards


# --- экранирование (6.4) ---------------------------------------------------------

XSS_SCRIPT = "<script>alert(1)</script>"
XSS_IMG = "<img src=x onerror=alert(1)>"


def xss_journal():
    j = plan()
    rec = j["records"][0]
    rec["decision"]["word"] = XSS_SCRIPT
    rec["question"] = "вопрос `код` и <b>жирный</b>"
    rec["evidence"] = [{"path": "a.md", "quote": XSS_IMG, "line": 1, "found": True, "verdict": "сверено"}]
    rec["consequences"] = XSS_SCRIPT
    return j


@requires_node
def test_viewer_escapes_journal_and_attack_text_in_every_mode(tmp_path):
    """6.4: слово `<script>alert(1)</script>`, цитата с `<img onerror>` и ячейка атаки с тем же показаны текстом
    во всех режимах; `<b>` — текст, `` `код` `` — `<code>`."""
    att = afile([arow(claim=XSS_IMG, invariant=XSS_SCRIPT, support=f"есть: `{XSS_IMG}`", fix="<b>x</b>", lens=XSS_IMG)])
    html = journal.render_html(xss_journal(), TEMPLATE, attacks=[att], journal_sha256=FAKE_SHA)
    cards = smoke(tmp_path, html)["cards"]
    check = smoke(tmp_path, html, {"__suffixes__": {":mode": "check"}})["check"]
    attack = smoke(tmp_path, html, {"__suffixes__": {":mode": "attack"}})["attack"]
    for shown in (cards, check, attack):
        assert "<script" not in shown and "<img" not in shown and "<b>жирный" not in shown and "<b>x" not in shown
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in cards and "&lt;img src=x onerror=alert(1)&gt;" in cards
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in check
    assert "вопрос <code>код</code> и &lt;b&gt;жирный&lt;/b&gt;" in cards and "вопрос <code>код</code> и &lt;b&gt;жирный&lt;/b&gt;" in check
    assert "опора: есть: <code>&lt;img src=x onerror=alert(1)&gt;</code>" in attack
    assert "&lt;b&gt;x&lt;/b&gt;" in attack and "линза «&lt;img" in attack


def test_render_html_embeds_hostile_text_as_data_only():
    """Данные журнала и атаки не закрывают `<script>` страницы и не открывают в нём «экранированное» состояние:
    `</` и `<!--` в JSON закодированы."""
    j = xss_journal()
    j["records"][0]["question"] = "до </script><script>alert(2)</script> и <!--<script> после"
    html = journal.render_html(j, TEMPLATE, attacks=[afile([arow(claim="</script><img src=x onerror=alert(3)>")])])
    assert "</script><script>alert(2)" not in html and "<!--<script>" not in html and "</script><img" not in html
    assert embedded(html)["records"][0]["question"] == "до </script><script>alert(2)</script> и <!--<script> после"
    assert embedded_attack(html)[0]["rows"][0]["claim"] == "</script><img src=x onerror=alert(3)>"


# --- пометка «отступление от постановки»: `options[].deviation` (5.1, ruling: у варианта, F-28.E) ----

def deviation_journal():
    """Факт постановки F-01 и решённая развилка F-02: вариант B отступает от F-01, A — нет."""
    j = one_record_journal("intent.md", "критерий")
    fact = j["records"][0]
    fact.update(kind="факт", status="решён", addressee="постановка", options=[],
                evidence=[{"path": "intent.md", "quote": "критерий"}])
    fork = copy.deepcopy(one_record_journal("a.md", "q")["records"][0])
    fork["options"].append({"letter": "B", "text": "наследование", "added": False, "unlikely": None,
                            "evidence": [], "deviation": "F-01"})
    fork.update(id="F-02", status="решён", addressee="человек", depends_on=["F-01"],
                decision={"option": "B", "word": "", "date": "2026-10-31"})
    j["records"].append(fork)
    assert journal.validate_journal(j) == []
    return j


def test_render_md_marks_the_deviating_option_line():
    md = journal.render_md(deviation_journal())
    fork = md.split("\n## F-02")[1].splitlines()
    assert "  - B. наследование (отступление от F-01)" in fork
    assert "  - A. вариант" in fork                                         # вариант без пометки — как был
    assert "отступление от" not in md.split("\n## F-02")[0]                # у факта пометки нет
    assert not any(line.startswith("- отступление") for line in fork)     # строки записи больше нет
    assert "отступление от F-NN" in journal.render_md.__doc__


def test_deviation_survives_the_roundtrip():
    j = deviation_journal()
    back = roundtrip(j)
    options = back["records"][1]["options"]
    assert options[1]["deviation"] == "F-01" and options[1]["text"] == "наследование"
    assert "deviation" not in options[0] and "deviation" not in back["records"][1]
    assert strip_check_fields(back) == strip_check_fields(j)
    assert journal.render_md(back) == journal.render_md(j)


def test_deviation_mark_follows_the_added_mark_and_survives_the_roundtrip():
    """Вариант, добавленный человеком и отступающий: обе пометки, импорт разбирает обе."""
    j = deviation_journal()
    j["records"][1]["options"][1]["added"] = True
    md = journal.render_md(j)
    assert "  - B. наследование (добавлен человеком) (отступление от F-01)" in md
    back = roundtrip(j)["records"][1]["options"][1]
    assert back["added"] is True and back["deviation"] == "F-01"


@requires_node
def test_viewer_marks_the_deviating_option_escaped(tmp_path):
    """Бейдж «отступление от F-NN» — у отступающего варианта, при выборе видно, какой вариант отступает;
    значение идёт через `esc`."""
    j = deviation_journal()
    cards = smoke(tmp_path, journal.render_html(j, TEMPLATE))["cards"]
    fork = cards.split('id="F-02"')[1]
    option_a, option_b = fork.split('value="A"')[1].split('value="B"')
    assert '<span class="tag deviation">отступление от F-01</span>' in option_b
    assert "отступление от" not in option_a and "отступление от" not in cards.split('id="F-02"')[0]
    j["records"][1]["options"][1]["deviation"] = "<b>F-01</b>"          # в обход схемы: показ всё равно экранирован
    cards = smoke(tmp_path, journal.render_html(j, TEMPLATE))["cards"]
    assert "отступление от &lt;b&gt;F-01&lt;/b&gt;" in cards and "<b>F-01" not in cards


@requires_node
def test_viewer_check_and_attack_modes_tag_the_deviating_option(tmp_path):
    """Ревью: «Проверка» и блок записи «Атаки» показывают у выбранного варианта тот же тег отступления, что карточка;
    в «Проверке» у открытой развилки тег стоит у отступающего варианта; значение — через `esc`."""
    tag = '<span class="tag deviation">отступление от F-01</span>'
    j = deviation_journal()
    html = journal.render_html(j, TEMPLATE, attacks=[afile([arow(section="F-02, decision")])], journal_sha256=FAKE_SHA)
    check = smoke(tmp_path, html, {"__suffixes__": {":mode": "check"}})["check"]
    assert check.count(tag) == 1 and tag in check.split('<span class="letter">B.</span>')[1]
    attack = smoke(tmp_path, html, {"__suffixes__": {":mode": "attack"}})["attack"]
    block = attack.split('<details class="recblock">')[1].split("</details>")[0]
    assert tag in block

    j["records"][1].update(status="открыт", decision=None)
    check = smoke(tmp_path, journal.render_html(j, TEMPLATE), {"__suffixes__": {":mode": "check"}})["check"]
    option_a, option_b = check.split('<span class="letter">A.</span>')[1].split('<span class="letter">B.</span>')
    assert tag in option_b and "отступление от" not in option_a

    j = deviation_journal()
    j["records"][1]["options"][1]["deviation"] = "<b>F-01</b>"          # в обход схемы: показ экранирован
    html = journal.render_html(j, TEMPLATE, attacks=[afile([arow(section="F-02, decision")])], journal_sha256=FAKE_SHA)
    for mode in ("check", "attack"):
        shown = smoke(tmp_path, html, {"__suffixes__": {":mode": mode}})[mode]
        assert "отступление от &lt;b&gt;F-01&lt;/b&gt;" in shown and "<b>F-01" not in shown


# 3. хвост отступления в тексте варианта без поля: импорт не превращает его в поле

def test_deviation_tail_in_option_text_does_not_turn_into_the_field(tmp_path):
    """Ревью: текст варианта без поля, сам оканчивающийся «(отступление от F-NN)», после рендера и импорта получил
    бы поле и усечённый текст. Такой текст `check` отвергает (код 1), render-md его не пишет; тот же оборот
    в середине текста и хвост при настоящем поле проходят круг без потерь."""
    j = deviation_journal()
    a = j["records"][1]["options"][0]
    a["text"] = "вариант (отступление от F-01) в середине"
    back = roundtrip(j)
    assert back["records"][1]["options"][0]["text"] == a["text"] and "deviation" not in back["records"][1]["options"][0]

    a["text"] = "вариант (отступление от F-01)"
    assert journal.validate_journal(j) == \
        ["F-02: вариант A — текст варианта оканчивается пометкой отступления без поля"]
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    run = run_cli("render-md", path, "--out", tmp_path / "j.md")
    assert run.returncode == 1 and not (tmp_path / "j.md").exists()
    assert "[!!] F-02: вариант A — текст варианта оканчивается пометкой отступления без поля" in run.stderr

    # триаж финального ревью: хвостовой пробел не прячет пометку от check — импорт её всё равно принял бы
    a["text"] = "вариант (отступление от F-01) "
    assert journal.validate_journal(j) == \
        ["F-02: вариант A — текст варианта оканчивается пометкой отступления без поля"]

    a["text"] = "вариант (отступление от F-01)"
    a["deviation"] = "F-01"
    assert journal.validate_journal(j) == []
    back = roundtrip(j)
    assert back["records"][1]["options"][0] == {**a, "evidence": back["records"][1]["options"][0]["evidence"]}
    assert strip_check_fields(back) == strip_check_fields(j)


# --- scheme.md: разбор и встраивание в страницу (F-25, F-39, F-59, F-60, F-61, F-89) ---

SCHEME_CASES = json.loads((FIX / "scheme" / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", SCHEME_CASES, ids=lambda c: c["name"])
def test_parse_scheme_by_the_shared_cases(case):
    assert journal_render.parse_scheme(case["text"]) == case["expect"]


def scheme_embedded(html):
    start = html.index("const SCHEME = ") + len("const SCHEME = ")
    return json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))[0]


def render_page(tmp_path, scheme=None, out=None):
    src = tmp_path / "decisions.json"
    journal.save_journal(src, plan())
    if scheme is not None:
        (tmp_path / "scheme.md").write_text(scheme, encoding="utf-8", newline="")
    out = out or tmp_path / "page.html"
    run = run_cli("render-html", src, "--out", out)
    assert run.returncode == 0, run.stderr
    return out.read_text(encoding="utf-8"), src


def test_template_requires_the_scheme_mark(tmp_path):
    template = tmp_path / "t.html"
    template.write_text("<html>const JOURNAL = __JOURNAL_JSON__; const ATTACK = __ATTACK_JSON__;</html>", encoding="utf-8")
    with pytest.raises(ValueError, match="__SCHEME_JSON__"):
        journal.render_html(plan(), template)


def test_scheme_with_script_end_keeps_the_page_whole_and_the_text_verbatim(tmp_path):
    text = "```mermaid\nflowchart TD\n  A[\"</script><!-- --> \\u003c\"] --> B\n```\n"
    html, _ = render_page(tmp_path, text)
    assert "</script><!--" not in html
    assert html.count("</script>") == 1
    assert scheme_embedded(html)["text"] == "flowchart TD\n  A[\"</script><!-- --> \\u003c\"] --> B\n"


def test_scheme_text_does_not_reach_view_json(tmp_path):
    _, src = render_page(tmp_path, "```mermaid\nflowchart TD\n  МЕТКАСХЕМЫ --> B\n```\n")
    run = run_cli("view-json", src)
    assert run.returncode == 0, run.stderr
    assert "МЕТКАСХЕМЫ" not in run.stdout


def test_page_without_scheme_md_is_valid(tmp_path):
    html, _ = render_page(tmp_path)
    assert scheme_embedded(html) == {"exists": False, "text": None, "blocks": 0, "first_line": None, "mermaid": None}


def test_file_without_a_block_is_not_the_missing_file(tmp_path):
    html, _ = render_page(tmp_path, "только текст\n")
    assert scheme_embedded(html)["exists"] is True and scheme_embedded(html)["text"] is None


def test_binary_scheme_is_a_file_without_a_block(tmp_path):
    (tmp_path / "scheme.md").write_bytes(bytes(range(256)))
    html, _ = render_page(tmp_path)
    assert scheme_embedded(html)["exists"] is True and scheme_embedded(html)["text"] is None


def test_two_renders_of_one_journal_and_scheme_match(tmp_path):
    first, _ = render_page(tmp_path, "```mermaid\nflowchart TD\n```\n")
    second, _ = render_page(tmp_path, "```mermaid\nflowchart TD\n```\n")
    assert first == second


def test_page_inside_a_project_points_at_the_installed_mermaid(tmp_path):
    change = tmp_path / "openspec" / "changes" / "x"
    change.mkdir(parents=True)
    (tmp_path / ".symphysis" / "tools").mkdir(parents=True)
    html, _ = render_page(change, "```mermaid\nflowchart TD\n```\n")
    assert scheme_embedded(html)["mermaid"] == "../../../.symphysis/tools/mermaid.min.js"


def test_page_outside_a_project_has_no_mermaid_path(tmp_path):
    html, _ = render_page(tmp_path, "```mermaid\nflowchart TD\n```\n")
    assert scheme_embedded(html)["mermaid"] is None


def test_page_carries_the_csp_and_no_embedded_plan_scheme():
    template = TEMPLATE.read_text(encoding="utf-8")
    assert '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\' file:; style-src \'unsafe-inline\'; img-src data:; font-src data:">' in template
    assert "NODES" not in template and "function renderScheme(" not in template and "filter.node" not in template
    assert "Схема работы" not in template


@requires_node
def test_page_without_the_embedded_scheme_still_runs_all_modes(tmp_path):
    html = journal.render_html(plan(), TEMPLATE, attacks=fixture_attacks(), journal_sha256=FAKE_SHA)
    done = smoke(tmp_path, html)
    assert "F-19" in done["cards"] and done["out"]
    for mode in ("check", "attack"):
        assert smoke(tmp_path, html, {"__suffixes__": {":mode": mode}})["modes"]


# --- антипод и дефекты шаблона (F-17, F-41, F-52, F-94) -------------------------

def facts_journal(status="решён", dispute=""):
    j = one_record_journal("a.md", "дв")
    fork = j["records"][0]
    fact = json.loads(json.dumps(fork))
    fact.update(id="F-02", kind="факт", status=status, addressee="материалы", options=[], dispute=dispute,
                parking=[{"addressee": "материалы", "text": "вопрос"}] if status == "припаркован" else [])
    fork["depends_on"] = ["F-02"]
    j["records"].append(fact)
    return j


@requires_node
def test_dependency_on_a_settled_fact_is_not_waiting(tmp_path):
    assert "предпосылка не решена" not in smoke(tmp_path, journal.render_html(facts_journal(), TEMPLATE))["cards"]


@requires_node
def test_dependency_on_a_parked_fact_is_waiting(tmp_path):
    assert "предпосылка не решена: F-02" in smoke(tmp_path, journal.render_html(facts_journal("припаркован"), TEMPLATE))["cards"]


@requires_node
def test_disputing_a_fact_does_not_make_it_a_waiting_dependency(tmp_path):
    assert "предпосылка не решена" not in smoke(tmp_path, journal.render_html(facts_journal(dispute="не так"), TEMPLATE))["cards"]


@requires_node
def test_dependency_on_an_undecided_fork_is_still_waiting(tmp_path):
    j = facts_journal()
    j["records"][1].update(kind="развилка", status="открыт", addressee="человек", options=j["records"][0]["options"])
    assert "предпосылка не решена: F-02" in smoke(tmp_path, journal.render_html(j, TEMPLATE))["cards"]


def test_park_hint_says_the_agent_looks_in_files_or_by_a_probe():
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "«материалы» — ответ ищет агент, в файлах или пробой" in template
    assert "const ADDRESSEES = ['материалы','человек','ИБ'];" in template


# --- снимок справки в `render-html`: метка шаблона, корень из пути журнала, сбой страницу не роняет, команда пересборки ---

JOURNAL_PY = ROOT / "tools" / "journal.py"


def help_of(html: str) -> dict:
    start = html.index("const HELP = ") + len("const HELP = ")
    return json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))[0]


def journal_in(project: Path, change="demo", data=None, under="") -> Path:
    change_dir = project / "openspec" / "changes" / under / change
    change_dir.mkdir(parents=True)
    src = change_dir / "decisions.json"
    journal.save_journal(src, data or journal_of(fork_record("F-01", "A", A=[])))
    return src


def build(src: Path, env: dict, *extra, cwd=None, out=None, script=JOURNAL_PY, timeout=60):
    """`render-html` в своём процессе; возвращает вызов и путь страницы."""
    out = out or src.parent / "page.html"
    run = subprocess.run([sys.executable, str(script), "render-html", str(src), "--out", str(out), *map(str, extra)],
                         capture_output=True, text=True, encoding="utf-8", env=env, cwd=cwd or src.parent, timeout=timeout)
    return run, out


def built(src: Path, env: dict, *extra, **kwargs) -> tuple[dict, str]:
    run, out = build(src, env, *extra, **kwargs)
    assert run.returncode == 0, run.stdout + run.stderr
    html = out.read_text(encoding="utf-8")
    return help_of(html), html


def shim_project(tmp_path, done=(), ready=("intent",), apply=None, name="proj", **replies):
    """Проект с журналом и шим форка с ответами по сценарию: возвращает журнал и окружение."""
    project = tmp_path / name
    src = journal_in(project)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, done=done, ready=ready)),
                      apply=fork_reply(apply or fake_apply()), **replies)
    return project, src, fork_env(tmp_path / "bin")


def all_modes_work(tmp_path: Path, html: str):
    assert "F-01" in smoke(tmp_path, html)["cards"]
    for mode in ("check", "attack"):
        assert smoke(tmp_path, html, {"__suffixes__": {":mode": mode}})["modes"]


# --- 3.1 метка шаблона --------------------------------------------------------

def test_template_requires_the_help_mark(tmp_path):
    template = tmp_path / "t.html"
    template.write_text("const J = __JOURNAL_JSON__; const A = __ATTACK_JSON__; const S = __SCHEME_JSON__;", encoding="utf-8")
    with pytest.raises(ValueError, match="__HELP_JSON__"):
        journal.render_html(journal_of(), template)
    src = journal_in(tmp_path / "proj")
    run, out = build(src, fork_env(), "--template", template)
    assert run.returncode == 1 and "__HELP_JSON__" in run.stderr
    assert not out.exists()


def test_render_from_memory_says_no_calculation_and_stays_deterministic():
    """Без данных на метку встаёт снимок «расчёта нет», времени в нём нет: два рендера совпадают (F-46)."""
    first = journal.render_html(journal_of(), TEMPLATE)
    assert first == journal.render_html(journal_of(), TEMPLATE)
    snapshot = help_of(first)
    assert snapshot["error"] and snapshot["taken_at"] is None and snapshot["steps"] == []
    assert snapshot["current_step"] is None


def test_docstring_says_who_adds_the_time():
    assert "время снятия добавляет CLI" in " ".join(journal.render_html.__doc__.split())


def hostile_snapshot() -> dict:
    text = "</script><img src=x onerror=alert(1)><!-- `<b>код</b>`"
    page = {"id": "intent", "state": "ready", "turn": "human", "optional": False, "blocks": [], "stops_apply": False,
            "waits_for": [], "files": [{"path": text, "exists": True}], "file_note": None,
            "texts": {"title": text, "why": text, "mechanics": "- " + text, "if_skipped": text, "what_to_check": text,
                      "command": text, "how_to_prepare": text},
            "text_note": None, "prev": None, "next": None}
    return {"error": text, "taken_at": text, "versions": {"openspec": text, "symphysis": text}, "rebuild": text,
            "current_step": "intent", "current_text": text, "turn": "human", "next_by_status": "intent", "change": "demo",
            "changes": None, "forks": {"open": text, "parked": text}, "tasks": None, "steps": [page]}


def test_hostile_text_does_not_close_the_tag():
    """Канон F-53: `</script>` в тексте шага и в `error` тег не закрывает, текст доезжает как есть."""
    html = journal.render_html(journal_of(), TEMPLATE, help_snapshot=hostile_snapshot())
    assert html.count("</script>") == TEMPLATE.read_text(encoding="utf-8").count("</script>")
    assert "<!-- `<b>" not in html
    assert help_of(html)["error"] == hostile_snapshot()["error"]


@requires_node
@pytest.mark.parametrize("failed", [True, False], ids=["сбой", "снимок"])
def test_hostile_text_makes_no_markup(tmp_path, failed):
    """Канон F-53: на панели текст снимка экранирован, разметки нет; `` `код` `` — единственное, что становится тегом."""
    snapshot = hostile_snapshot()
    if not failed:
        snapshot["error"] = None
    shown = smoke(tmp_path, journal.render_html(journal_of(), TEMPLATE, help_snapshot=snapshot))["help"]
    assert shown and "<img" not in shown and "<b>код" not in shown and "</script>" not in shown
    assert "&lt;img src=x onerror=alert(1)&gt;" in shown


# --- 3.2 расчёт из `render-html` ----------------------------------------------

def test_snapshot_on_the_page(tmp_path):
    """Сценарий «Снимок на странице»."""
    project, src, env = shim_project(tmp_path, done=("intent", "decisions"), ready=("research",))
    snapshot, _ = built(src, env)
    assert snapshot["error"] is None and snapshot["change"] == "demo"
    assert snapshot["current_step"] == "research" and snapshot["taken_at"]
    assert [item["id"] for item in snapshot["steps"]][:3] == ["intent", "decisions", "viewer"]


def test_no_fork_keeps_the_page(tmp_path):
    """Сценарий «Форка нет»: код 0, журнал и режимы на месте, панель говорит причину."""
    src = journal_in(tmp_path / "proj")
    snapshot, html = built(src, fork_env())
    assert "openspec не найден" in snapshot["error"] and "SYMPHYSIS_OPENSPEC" in snapshot["error"]
    assert "F-01" in html
    if node:
        all_modes_work(tmp_path, html)


def test_journal_of_another_project(tmp_path):
    """Сценарий «Журнал из другого проекта»: корень из пути журнала, а не каталог вызова."""
    a = tmp_path / "A"
    src = journal_in(a, data=journal_of(fork_record("F-01", chosen=None, A=[])))
    journal_in(tmp_path / "B")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(a, ready=("intent",))), apply=fork_reply(fake_apply()))
    snapshot, _ = built(src, fork_env(tmp_path / "bin"), cwd=tmp_path / "B")
    assert snapshot["forks"]["open"] == 1 and snapshot["current_step"] == "viewer"
    assert {Path(call["cwd"]) for call in fork_calls(tmp_path / "bin")} == {a}


def test_relative_journal_path_gives_the_same_root(tmp_path):
    project, src, env = shim_project(tmp_path)
    run = subprocess.run([sys.executable, str(JOURNAL_PY), "render-html", "openspec/changes/demo/decisions.json", "--out", "p.html"],
                         capture_output=True, text=True, encoding="utf-8", env=env, cwd=project)
    assert run.returncode == 0, run.stderr
    assert {Path(call["cwd"]) for call in fork_calls(tmp_path / "bin")} == {project}


def test_project_directory_is_not_on_the_page(tmp_path):
    """Сценарий «Каталог с заметным именем»."""
    project = tmp_path / "probe-machine-name"
    src = journal_in(project)
    status = fake_status(project, done=("intent",), ready=("decisions",))
    install_fork_shim(tmp_path / "bin", status=fork_reply(status), apply=fork_reply(fake_apply()))
    snapshot, html = built(src, fork_env(tmp_path / "bin"))
    assert "probe-machine-name" not in html
    intent = next(item for item in snapshot["steps"] if item["id"] == "intent")
    assert intent["files"] == [{"path": "openspec/changes/demo/intent.md", "exists": True}]


def test_failure_reason_has_no_directory(tmp_path):
    """Сценарий «Причина сбоя без каталога»."""
    src = journal_in(tmp_path / "proj")
    env = fork_env(SYMPHYSIS_OPENSPEC=str(tmp_path / "probe-machine-name" / "openspec"))
    snapshot, html = built(src, env)
    assert "openspec не найден" in snapshot["error"]
    assert "probe-machine-name" not in html


def test_hung_fork_returns_after_the_first_taken_down_call(tmp_path):
    """Сценарий «`openspec` завис», половина `render-html`, настоящий предел: зависли бы и `status`, и `instructions apply`,
    но следующих вызовов нет, и сборка укладывается в 30 с плагина."""
    _, src, env = shim_project(tmp_path)
    scenario = tmp_path / "bin" / "scenario.json"
    replies = json.loads(scenario.read_text(encoding="utf-8"))
    replies["status"]["hang"] = replies["apply"]["hang"] = 50
    scenario.write_text(json.dumps(replies, ensure_ascii=False), encoding="utf-8")
    started = time.monotonic()
    snapshot, html = built(src, env, timeout=120)
    assert time.monotonic() - started < 30
    assert "openspec status" in snapshot["error"] and "15 с" in snapshot["error"]
    assert "F-01" in html
    assert [call["argv"][0] for call in fork_calls(tmp_path / "bin")] == ["--version", "status"]


def test_telemetry_is_off_in_every_call(tmp_path):
    """Сценарий «Телеметрия форка подавлена», половина `render-html`."""
    _, src, env = shim_project(tmp_path)
    built(src, {**env, "OPENSPEC_TELEMETRY": "1"})
    calls = fork_calls(tmp_path / "bin")
    assert len(calls) == 3, "--version, status, instructions apply"
    assert {call["env"]["OPENSPEC_TELEMETRY"] for call in calls} == {"0"}


def test_dangerous_directory_of_the_journal(tmp_path):
    """Канон: каталог `a&md,marker` в чужом репозитории срабатывал бы при сборке страницы; имя из пути журнала не идёт в шим."""
    project = tmp_path / "proj"
    src = journal_in(project, change="a&md,marker")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project)), apply=fork_reply(fake_apply()))
    snapshot, html = built(src, fork_env(tmp_path / "bin"), cwd=project)
    assert "не подходит" in snapshot["error"] and "F-01" in html
    assert not (project / "marker").exists() and not (src.parent / "marker").exists()
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"]]


def copy_of_tools_without_the_script(home: Path) -> Path:
    """Инструменты журнала в `home/tools`, схема журнала в `home/docs`, как их ставит инсталлятор: возвращает `journal.py`."""
    (home / "tools").mkdir(parents=True)
    (home / "docs").mkdir()
    for file in (ROOT / "tools").glob("journal*"):
        shutil.copy(file, home / "tools")
    shutil.copy(TEMPLATE, home / "tools")
    shutil.copy(ROOT / "docs" / "journal.schema.json", home / "docs")
    return home / "tools" / "journal.py"


def test_no_script_file_keeps_the_page(tmp_path):
    """Предположение «б»: инструменты без `step_help.py` страницу собирают, панель называет причину (F-65)."""
    script = copy_of_tools_without_the_script(tmp_path / "home")
    src = journal_in(tmp_path / "proj")
    snapshot, html = built(src, fork_env(), script=script)
    assert "step_help" in snapshot["error"] and "symphysis install" in snapshot["error"]
    assert "F-01" in html and snapshot["steps"] == []


@requires_node
@pytest.mark.parametrize("reply", [fork_reply("это не JSON"), fork_reply(""), fork_reply("{обрыв"), fork_reply({"artifacts": 5}),
                                   fork_reply(code=7, stderr="упал\n")],
                         ids=["мусор", "пусто", "обрыв", "не та форма", "код возврата"])
def test_strange_answer_keeps_the_page(tmp_path, reply):
    """Тест-страховка F-61."""
    project = tmp_path / "proj"
    src = journal_in(project)
    install_fork_shim(tmp_path / "bin", status=reply, apply=fork_reply(fake_apply()))
    snapshot, html = built(src, fork_env(tmp_path / "bin"))
    assert snapshot["error"] and snapshot["current_step"] is None
    all_modes_work(tmp_path, html)


def test_unexpected_failure_of_the_calculation_keeps_the_page(tmp_path):
    """Любой сбой расчёта идёт на панель: `step_help.py` падает своей ошибкой, код 0, каталога в причине нет (F-34)."""
    script = copy_of_tools_without_the_script(tmp_path / "home")
    (script.parent / "step_help.py").write_text("def compute(root, change):\n    raise RuntimeError(r'C:\\probe-machine-name\\x')\n",
                                                encoding="utf-8")
    src = journal_in(tmp_path / "proj")
    snapshot, html = built(src, fork_env(), script=script)
    assert snapshot["error"] and "RuntimeError" in snapshot["error"]
    assert "probe-machine-name" not in html and "F-01" in html


def test_journal_outside_changes_does_not_call_the_fork(tmp_path):
    """Предположение «в»: журнал вне `openspec/changes/` корня не даёт, форк не зовётся, причина своими словами."""
    src = tmp_path / "somewhere" / "decisions.json"
    src.parent.mkdir()
    journal.save_journal(src, journal_of(fork_record("F-01", "A", A=[])))
    install_fork_shim(tmp_path / "bin")
    snapshot, html = built(src, fork_env(tmp_path / "bin"))
    assert "openspec/changes/" in snapshot["error"]
    assert snapshot["taken_at"] is None and snapshot["rebuild"] is None
    assert fork_calls(tmp_path / "bin") == [] and "F-01" in html


def test_archived_journal_goes_the_common_way(tmp_path):
    """Предположение «в», F-45: корень есть, форк зовётся, панель показывает его сообщение."""
    project = tmp_path / "proj"
    src = journal_in(project, change="2026-11-02-demo", under="archive")
    missing = {"status": [{"code": "change_error", "message": "Change '2026-11-02-demo' not found."}]}
    install_fork_shim(tmp_path / "bin", status=fork_reply(missing, code=1))
    snapshot, _ = built(src, fork_env(tmp_path / "bin"))
    assert "2026-11-02-demo" in snapshot["error"] and "not found" in snapshot["error"]
    assert {Path(call["cwd"]) for call in fork_calls(tmp_path / "bin")} == {project}


def test_no_default_out(tmp_path):
    """F-30: файл задаёт только `--out`."""
    src = journal_in(tmp_path / "proj")
    run = subprocess.run([sys.executable, str(JOURNAL_PY), "render-html", str(src)], capture_output=True, text=True,
                         encoding="utf-8", env=fork_env())
    assert run.returncode == 2 and "--out" in run.stderr
    assert sorted(path.name for path in src.parent.iterdir()) == ["decisions.json"]


def test_calculation_leaves_the_project_as_it_was(tmp_path):
    """Сборка пишет только страницу: журнал и файлы шагов те же."""
    project, src, env = shim_project(tmp_path)
    before = {path: path.read_bytes() for path in project.rglob("*") if path.is_file()}
    built(src, env)
    after = {path: path.read_bytes() for path in project.rglob("*") if path.is_file() and path.name != "page.html"}
    assert after == before


# --- 3.3 команда пересборки ---------------------------------------------------

def test_rebuild_command_on_the_data(tmp_path):
    """Сценарий «Команда пересборки рядом со снимком»: пути от корня, `--out` этой сборки, абсолютных путей нет."""
    project = tmp_path / "probe-machine-name"
    src = journal_in(project)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))), apply=fork_reply(fake_apply()))
    snapshot, _ = built(src, fork_env(tmp_path / "bin"), out=src.parent / "страница с пробелом.html")
    argv = shlex.split(snapshot["rebuild"])
    assert argv[:3] == ["python", ".symphysis/tools/journal.py", "render-html"]
    assert argv[3] == "openspec/changes/demo/decisions.json"
    assert argv[4:] == ["--out", "openspec/changes/demo/страница с пробелом.html"]
    assert "probe-machine-name" not in snapshot["rebuild"]


def test_rebuild_command_quotes_with_double_quotes(tmp_path):
    """Одинарные кавычки не читает `cmd`, двойные читают PowerShell, bash и `cmd`: слово с пробелом или кириллицей
    в двойных, простое пишется как есть; разбор `shlex` даёт те же слова."""
    project = tmp_path / "proj"
    src = journal_in(project)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))), apply=fork_reply(fake_apply()))
    snapshot, _ = built(src, fork_env(tmp_path / "bin"), out=src.parent / "страница с пробелом.html")
    assert "'" not in snapshot["rebuild"]
    assert snapshot["rebuild"].endswith('--out "openspec/changes/demo/страница с пробелом.html"')
    assert snapshot["rebuild"].startswith("python .symphysis/tools/journal.py render-html openspec/changes/demo/decisions.json ")


def test_rebuild_command_keeps_cmd_metacharacters_in_double_quotes(tmp_path):
    """`&`, `|`, `<`, `>`, `^` внутри двойных кавычек безопасны в PowerShell, bash и `cmd`; одинарные `cmd` не читает,
    и `&` в них исполнил бы хвост."""
    project = tmp_path / "proj"
    src = journal_in(project)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))), apply=fork_reply(fake_apply()))
    snapshot, _ = built(src, fork_env(tmp_path / "bin"), out=src.parent / "а&б в^г.html")
    assert "'" not in snapshot["rebuild"]
    assert snapshot["rebuild"].endswith('--out "openspec/changes/demo/а&б в^г.html"')


def test_rebuild_command_repeats_attacks_of_this_build(tmp_path):
    """Предположение «г»: без `--attack` обновление потеряло бы режим «атака»."""
    project, src, env = shim_project(tmp_path)
    (src.parent / "attack").mkdir()
    attack = src.parent / "attack" / "decisions.md"
    shutil.copy(ATTACK_FIX / "decisions.md", attack)
    snapshot, _ = built(src, env, "--attack", attack)
    argv = shlex.split(snapshot["rebuild"])
    assert argv[argv.index("--attack") + 1] == "openspec/changes/demo/attack/decisions.md"


def test_rebuild_command_names_the_script_it_ran_from(tmp_path):
    """Сборка инструментами самого проекта: путь скрипта от корня, а не установленный по умолчанию."""
    project, src, env = shim_project(tmp_path)
    script = copy_of_tools_without_the_script(project)
    shutil.copy(ROOT / "tools" / "step_help.py", script.parent)
    snapshot, _ = built(src, env, script=script)
    assert shlex.split(snapshot["rebuild"])[1] == "tools/journal.py"


def test_rebuild_is_given_for_a_failed_calculation_too(tmp_path):
    """Причина снята — пересборка та же: команда есть и при сбое, если корень известен."""
    src = journal_in(tmp_path / "proj")
    snapshot, _ = built(src, fork_env())
    assert snapshot["error"] and "render-html" in snapshot["rebuild"]


def test_rebuild_command_run_from_the_root_builds_the_same_page(tmp_path):
    """Команда, выполненная из корня, собирает страницу с тем же составом режимов и тем же файлом."""
    project, src, env = shim_project(tmp_path)
    installed = copy_of_tools_without_the_script(project / ".symphysis")
    shutil.copy(ROOT / "tools" / "step_help.py", installed.parent)
    (src.parent / "attack").mkdir()
    attack = src.parent / "attack" / "decisions.md"
    shutil.copy(ATTACK_FIX / "decisions.md", attack)
    snapshot, html = built(src, env, "--attack", attack, script=installed)
    out = src.parent / "page.html"
    first_rows = [len(item["rows"]) for item in json.JSONDecoder().raw_decode(html[html.index("const ATTACK = ") + 15:])[0]]
    out.unlink()
    argv = shlex.split(snapshot["rebuild"])
    run = subprocess.run([sys.executable, *argv[1:]], cwd=project, env=env, capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    again = out.read_text(encoding="utf-8")
    assert [len(item["rows"]) for item in json.JSONDecoder().raw_decode(again[again.index("const ATTACK = ") + 15:])[0]] == first_rows
    assert first_rows and help_of(again)["rebuild"] == snapshot["rebuild"]


# --- настоящий форк -----------------------------------------------------------

@requires_fork
def test_real_fork_snapshot_on_the_page(tmp_path):
    project, env = real_project(tmp_path, "demo", name="probe-machine-name")
    (project / "openspec" / "changes" / "demo" / "intent.md").write_text("намерение\n", encoding="utf-8")
    src = project / "openspec" / "changes" / "demo" / "decisions.json"
    journal.save_journal(src, one_record_journal("a.md", "дв"))
    snapshot, html = built(src, env)
    assert snapshot["error"] is None and snapshot["current_step"] == "viewer" and snapshot["next_by_status"] == "research"
    assert snapshot["versions"]["openspec"] and "symphysis" in snapshot["versions"]["openspec"]
    assert next(item for item in snapshot["steps"] if item["id"] == "specs")["texts"]["why"]
    assert "probe-machine-name" not in html


@requires_fork
def test_real_fork_on_an_archived_journal(tmp_path):
    """F-45 на настоящем форке: `status` такого имени не знает, панель несёт его сообщение."""
    project, env = real_project(tmp_path)
    src = journal_in(project, change="2026-11-02-demo", under="archive")
    snapshot, html = built(src, env)
    assert "2026-11-02-demo" in snapshot["error"] and "F-01" in html


@requires_fork
def test_real_fork_after_a_rebuild_shows_the_new_step(tmp_path):
    """Сценарий «Файлы изменились после снимка» на данных: прежняя страница не меняется, новая сборка — новый шаг и время."""
    project, env = real_project(tmp_path, "demo")
    change = project / "openspec" / "changes" / "demo"
    (change / "intent.md").write_text("намерение\n", encoding="utf-8")
    src = change / "decisions.json"
    journal.save_journal(src, journal_of())
    first, html = built(src, env)
    assert first["current_step"] == "research"
    (change / "research").mkdir()
    (change / "research" / "none.md").write_text("нет\n", encoding="utf-8")
    assert help_of((change / "page.html").read_text(encoding="utf-8")) == first
    time.sleep(1.1)
    second, _ = built(src, env)
    assert second["current_step"] == "proposal" and second["taken_at"] != first["taken_at"]
    assert real_fork(project, env, "status", "--change", "demo", "--json")


# --- 9.2 сигнал о несформированной справке (F-71) -------------------------------

SIGNAL = "[..] справка не сформирована: "


def signal_of(run) -> str:
    lines = [line for line in run.stdout.splitlines() if line.startswith(SIGNAL)]
    assert len(lines) == 1, run.stdout
    return lines[0][len(SIGNAL):]


def test_signal_when_the_fork_is_missing(tmp_path):
    """Сценарий «Справка не сформирована»: код 0, строка `[..]` с причиной, та же причина на панели, `[!!]` нет."""
    src = journal_in(tmp_path / "proj")
    run, out = build(src, fork_env())
    assert run.returncode == 0, run.stderr
    reason = signal_of(run)
    assert "openspec не найден" in reason and "[!!]" not in run.stdout
    error = help_of(out.read_text(encoding="utf-8"))["error"]
    assert error == "Справка не сформирована: " + reason
    assert str(tmp_path) not in reason


def test_signal_for_a_journal_outside_changes(tmp_path):
    """Сценарий «Журнал вне изменений»: код 0, тот же сигнал, форк не вызван."""
    src = tmp_path / "somewhere" / "decisions.json"
    src.parent.mkdir()
    journal.save_journal(src, journal_of(fork_record("F-01", "A", A=[])))
    install_fork_shim(tmp_path / "bin")
    run, out = build(src, fork_env(tmp_path / "bin"))
    assert run.returncode == 0 and "openspec/changes/" in signal_of(run) and "[!!]" not in run.stdout
    assert fork_calls(tmp_path / "bin") == []
    assert help_of(out.read_text(encoding="utf-8"))["error"].startswith("Справка не сформирована: ")


def test_signal_without_the_script_file(tmp_path):
    script = copy_of_tools_without_the_script(tmp_path / "home")
    run, _ = build(journal_in(tmp_path / "proj"), fork_env(), script=script)
    assert run.returncode == 0 and "step_help.py" in signal_of(run) and "[!!]" not in run.stdout


def test_no_signal_when_the_help_is_formed(tmp_path):
    project, src, env = shim_project(tmp_path)
    run, _ = build(src, env)
    assert run.returncode == 0 and SIGNAL not in run.stdout


# --- ссылки на файлы ----------------------------------------------------------


def link_project(tmp_path):
    root = tmp_path / "проект"
    change = root / "openspec" / "changes" / "x"
    change.mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "docs" / "план работ.md").write_text("раз\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [ ] 1\n", encoding="utf-8")
    return change, {"": root}


PLAN_HREF = "../../../docs/" + quote("план работ.md")


def test_file_links_only_for_existing_files(tmp_path):
    """Сценарии «Файл в теле вопроса» и «Файла нет»: каталог, команда, чужое дерево и пропавший файл ссылки не дают."""
    change, roots = link_project(tmp_path)
    (tmp_path / "secret.txt").write_text("s", encoding="utf-8")
    j = one_record_journal("docs/план работ.md", "раз")
    j["records"][0]["question"] = "см. `tasks.md:3`, `tasks.md:3-5`, `docs`, `нет.md`, `../../../../secret.txt`, `tasks.md --help`"
    assert journal.file_links(j, roots, change, change / "symphysis.html") == {"docs/план работ.md": PLAN_HREF, "tasks.md": "tasks.md"}


def test_file_links_cover_attacks_and_help(tmp_path):
    change, roots = link_project(tmp_path)
    attacks = [{"path": "attack/none.md", "rows": [{"support": "`tasks.md:2`"}]}]
    snapshot = {"steps": [{"files": [{"path": "docs/план работ.md", "exists": True}]}]}
    links = journal.file_links(journal_of(), roots, change, change / "symphysis.html", attacks, snapshot)
    assert links == {"docs/план работ.md": PLAN_HREF, "tasks.md": "tasks.md"}


def test_file_links_hold_no_absolute_path_and_are_stable(tmp_path):
    change, roots = link_project(tmp_path)
    j = one_record_journal("docs/план работ.md", "раз")
    first = journal.file_links(j, roots, change, change / "symphysis.html")
    assert first == journal.file_links(copy.deepcopy(j), roots, change, change / "symphysis.html")
    assert list(first) == sorted(first) and not any(":" in href or href.startswith("/") for href in first.values())


def test_render_html_embeds_links_and_needs_their_mark(tmp_path):
    html = journal.render_html(plan(), TEMPLATE, links={"root": "../", "files": {"a.md": "../a.md"}})
    assert '"a.md": "../a.md"' in html and '"root": "../"' in html
    assert '"root": null' in journal.render_html(plan(), TEMPLATE)
    template = tmp_path / "t.html"
    template.write_text("const J = __JOURNAL_JSON__; const A = __ATTACK_JSON__; const S = __SCHEME_JSON__; const H = __HELP_JSON__;", encoding="utf-8")
    with pytest.raises(ValueError, match="__LINKS_JSON__"):
        journal.render_html(plan(), template)


@requires_node
def test_viewer_smoke_walks_a_page_with_a_file_link(tmp_path):
    """Плагин гоняет эту заглушку на журналах с настоящими уликами: страница со ссылкой на файл падала, когда пути страницы
    не подано и `location` не было. Значка редактора без `file:` нет, ссылка на файл на месте."""
    html = journal.render_html(one_record_journal("a.md", "раз"), TEMPLATE, links={"root": "../", "files": {"a.md": "../a.md"}})
    cards = smoke(tmp_path, html)["cards"]
    assert 'href="../a.md"' in cards
    assert "filelink editor" not in cards


def test_project_href_falls_back_to_the_tools_parent():
    """У ядра в файле корней нет пустого префикса: без этой опоры вариант IDEA / GIGA IDE на его страницах молча терял значок."""
    out = journal.ROOT / "docs" / "x.html"
    assert journal.project_href({}, out) == "../"
    assert journal.project_href({"": journal.ROOT / "docs"}, out) == "./"
