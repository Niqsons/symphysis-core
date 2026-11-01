"""`journal.py view-json`: данные журнала для расширения VS Code — JSON на stdout. Та же проекция, что получает
страница `render-html`, плюс «куда уйдёт» у записи и парковки и файлы атаки. Битый файл атаки журнал не прячет."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

import journal
import journal_render
from conftest import FIX, ROOT, one_record_journal

ATTACK_FIX = FIX / "attack"
TEMPLATE = ROOT / "tools" / "playground-template.html"


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "journal.py"), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", env=env)


def view(*args) -> dict:
    run = run_cli("view-json", *args)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def journal_file(tmp_path, quote="дв"):
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    src = tmp_path / "decisions.json"
    journal.save_journal(src, one_record_journal("a.md", quote))
    return src, roots


def page_payload(html: str) -> dict:
    start = html.index("const JOURNAL = ") + len("const JOURNAL = ")
    return json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))[0]


def test_payload_is_what_the_page_gets_plus_additions(tmp_path):
    """Страница и расширение видят одну проекцию журнала: разойтись может только то, что добавлено."""
    src = tmp_path / "decisions.json"
    journal.save_journal(src, journal.import_md(FIX / "journal-plan.md"))
    out = tmp_path / "page.html"
    assert run_cli("render-html", src, "--out", out).returncode == 0
    data = view(src)
    assert data.pop("attacks") == []
    for rec in data["records"]:
        assert rec.pop("destination")["label"]
        for park in rec["parking"]:
            assert park.pop("destination")
    assert data == page_payload(out.read_text(encoding="utf-8"))


def test_evidence_is_checked_in_memory(tmp_path):
    src, roots = journal_file(tmp_path)
    before = src.read_bytes()
    data = view(src, "--roots", roots)
    ev = data["records"][0]["options"][0]["evidence"][0]
    assert (ev["line"], ev["found"], ev["verdict"]) == (2, True, "сверено")
    assert (data["stats"]["evidence_found"], data["stats"]["evidence_total"]) == (1, 1)
    assert src.read_bytes() == before


def test_unmatched_evidence_keeps_the_verdict(tmp_path):
    src, roots = journal_file(tmp_path, quote="нет такого")
    ev = view(src, "--roots", roots)["records"][0]["options"][0]["evidence"][0]
    assert (ev["found"], ev["verdict"]) == (False, "цитаты нет дословно")


def test_sha256_is_of_the_file_bytes(tmp_path):
    src, roots = journal_file(tmp_path)
    assert view(src, "--roots", roots)["sha256"] == hashlib.sha256(src.read_bytes()).hexdigest()


def test_attacks_come_parsed(tmp_path):
    src, roots = journal_file(tmp_path)
    data = view(src, "--roots", roots, "--attack", ATTACK_FIX / "decisions.md", "--attack", ATTACK_FIX / "artifacts.md")
    assert [a["path"] for a in data["attacks"]] == [str(ATTACK_FIX / "decisions.md"), str(ATTACK_FIX / "artifacts.md")]
    assert [len(a["rows"]) for a in data["attacks"]] == [3, 3]
    assert data["attacks"][0]["frontmatter"]["status"] == "gaps_found"


def test_broken_attack_file_does_not_hide_the_journal(tmp_path):
    """Атаку пишет агент, файл бывает недописан: журнал виден, отказ назван у своего файла."""
    src, roots = journal_file(tmp_path)
    broken = tmp_path / "broken.md"
    broken.write_text("# без frontmatter и без таблицы\n", encoding="utf-8")
    missing = tmp_path / "нет.md"
    data = view(src, "--roots", roots, "--attack", broken, "--attack", ATTACK_FIX / "decisions.md", "--attack", missing)
    assert len(data["records"]) == 1
    first, good, gone = data["attacks"]
    assert first == {"path": str(broken), "error": f"{broken}: нет frontmatter"}
    assert len(good["rows"]) == 3
    assert gone == {"path": str(missing), "error": f"{missing}: файла нет"}


def test_invalid_journal_refused_on_stderr(tmp_path):
    j = journal.import_md(FIX / "journal-plan.md")
    j["records"][2]["status"] = "готов"
    src = tmp_path / "decisions.json"
    journal.save_journal(src, j)
    run = run_cli("view-json", src)
    assert run.returncode == 1
    assert run.stdout == ""
    assert run.stderr.startswith("[!!] F-03")


def test_stdout_is_utf8_whatever_the_locale(tmp_path):
    """Стрелки нет в cp1251: без своей кодировки потока вывод упал бы именно на такой строке."""
    src = tmp_path / "журнал с пробелом.json"
    j = one_record_journal("a.md", "дв")
    j["records"][0]["question"] = "Куда ведёт → стрелка?"
    journal.save_journal(src, j)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    run = run_cli("view-json", src, env=env)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["records"][0]["question"] == "Куда ведёт → стрелка?"


# --- «куда уйдёт» ---------------------------------------------------------------

def record(**kw) -> dict:
    return {"kind": "развилка", "outcome": None, "decision": None, "reversibility": None, "dispute": "", **kw}


def probe(value, reason=""):
    return {"kind": "проба", "value": value, "reason": reason}


DECISION = {"option": "A", "word": "слово", "date": "2026-11-01"}

DESTINATIONS = [
    (record(kind="факт"), "design.md › Context", ""),
    (record(kind="факт", dispute="не так"), "design.md › Context", "спор → design.md › Open Questions"),
    (record(outcome=probe("Specify")), "spec.md", "исход Specify"),
    (record(outcome=probe("Specify: уточнено")), "spec.md", "исход Specify: уточнено"),
    (record(outcome=probe("Backstop")), "tasks.md › тест-страховка", "в design.md не попадает"),
    (record(outcome=probe("Dismiss", "неприменимо")), "никуда", "причина: неприменимо"),
    (record(outcome=probe("Dismiss")), "никуда", "причина не записана"),
    (record(outcome=probe("Defer")), "design.md › Open Questions", "отложена (Defer)"),
    (record(outcome=probe("Иное")), "никуда", "исход «Иное» вне четырёх"),
    (record(decision=DECISION), "design.md › Decisions", ""),
    (record(decision=DECISION, reversibility={"level": "в одну сторону", "why": "x"}), "design.md › Decisions", "в одну сторону — первой"),
    (record(decision=DECISION, outcome={"kind": "вопрос", "value": "ответ", "reason": ""}), "design.md › Decisions", ""),
    (record(), "design.md › Open Questions", "открыта"),
]
PARKINGS = [("ИБ", "design.md › Open Questions → security.md"), ("материалы", "design.md › Open Questions → research/"),
            ("человек", "design.md › Open Questions → вопрос человеку"), ("", "design.md › Open Questions → —")]


@pytest.mark.parametrize("rec, label, note", DESTINATIONS)
def test_destination(rec, label, note):
    assert journal_render.destination(rec) == {"label": label, "note": note}


@pytest.mark.parametrize("addressee, label", PARKINGS)
def test_parking_destination(addressee, label):
    assert journal_render.parking_destination(addressee) == label


node = shutil.which("node")


@pytest.mark.skipif(node is None, reason="нет node: шаблон не прогнать")
def test_destination_matches_the_template(tmp_path):
    """Правило живёт и в шаблоне страницы: пока их два, расхождение видно здесь."""
    text = TEMPLATE.read_text(encoding="utf-8")
    pick = lambda pattern: re.search(pattern, text, re.S | re.M).group(0)
    code = "\n".join([
        pick(r"^const ONE_WAY = .*?;$"),
        pick(r"^function isProbe\(rec\).*?$"),
        pick(r"^function isOneWay\(rec\).*?$"),
        pick(r"^function destination\(rec\) \{.*?^\}$"),
        pick(r"^function parkingDestination\(addressee\).*?$"),
    ])
    script = tmp_path / "destination.js"
    data = tmp_path / "records.json"
    data.write_text(json.dumps({"records": [d[0] for d in DESTINATIONS], "parkings": [p[0] for p in PARKINGS]}, ensure_ascii=False), encoding="utf-8")
    script.write_text(code + "\nconst input = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
                      "process.stdout.write(JSON.stringify({records: input.records.map(destination), parkings: input.parkings.map(parkingDestination)}));\n",
                      encoding="utf-8")
    run = subprocess.run([node, str(script), str(data)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    js = json.loads(run.stdout)
    assert js["records"] == [journal_render.destination(d[0]) for d in DESTINATIONS]
    assert js["parkings"] == [journal_render.parking_destination(p[0]) for p in PARKINGS]
