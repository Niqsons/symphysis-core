import copy
import json
import re
import shutil
import subprocess
import sys

import pytest

import journal
import journal_render
from conftest import FIX, ROOT, one_record_journal

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


def test_cli_render_html_attack_flag(tmp_path):
    src, roots = html_fixture(tmp_path, "дв")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots,
                  "--attack", ATTACK_FIX / "decisions.md", "--attack", ATTACK_FIX / "artifacts.md")
    assert run.returncode == 0, run.stderr
    html = out.read_text(encoding="utf-8")
    assert '"rows"' in html and '"sha256"' in html
    attacks = embedded_attack(html)
    assert [a["path"] for a in attacks] == [str(ATTACK_FIX / "decisions.md"), str(ATTACK_FIX / "artifacts.md")]
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
