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

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import FIX, ROOT, fake_apply, fake_status, fork_env, fork_reply, install_fork_shim, one_record_journal, sample_journal
import journal
import journal_render

ATTACK_FIX = FIX / "attack"
TEMPLATE = ROOT / "viewer" / "playground-template.html"


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, str(ROOT / "cli" / "journal.py"), *map(str, args)],
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
    journal.save_journal(src, sample_journal())
    out = tmp_path / "page.html"
    assert run_cli("render-html", src, "--out", out).returncode == 0
    data = view(src)
    assert data.pop("attacks") == []
    assert data.pop("contract") == journal_render.CONTRACT
    assert isinstance(data.pop("file_links"), dict)
    for rec in data["records"]:
        assert rec.pop("destination")["label"]
        for park in rec["parking"]:
            assert park.pop("destination")
    assert data == page_payload(out.read_text(encoding="utf-8"))


def test_read_flag_note_keeps_the_contract_number_and_passes_through(tmp_path):
    """`warning-read-flag`: «Журнал с заметкой у прежнего номера» — заметка «предупреждение прочитано: <раздел>»
    отдаётся в `notes` как есть, без разбора, а номер контракта от заметки не растёт (остаётся текущим, `CONTRACT`)."""
    j = one_record_journal("a.md", "дв")
    j["notes"] = [{"date": "2026-11-07", "text": "предупреждение прочитано: F-12, options.B"}]
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    src = tmp_path / "decisions.json"
    journal.save_journal(src, j)
    data = view(src)
    assert data["contract"] == journal_render.CONTRACT
    assert data["notes"] == j["notes"]


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


def from_cwd(path) -> str:
    """Путь атаки от каталога вызова, где журнал вне `openspec/changes/` (F-72): `/` всюду, другой диск — имя файла."""
    try:
        return os.path.relpath(path).replace("\\", "/")
    except ValueError:
        return path.name


def project_with_attack(tmp_path):
    project = tmp_path / "proj"
    change = project / "openspec" / "changes" / "demo"
    (change / "attack").mkdir(parents=True)
    src = change / "decisions.json"
    journal.save_journal(src, one_record_journal("a.md", "дв"))
    attack = change / "attack" / "decisions.md"
    shutil.copy(ATTACK_FIX / "decisions.md", attack)
    return project, src, attack


def run_in(project, command, *args):
    return subprocess.run([sys.executable, str(ROOT / "cli" / "journal.py"), command, *map(str, args)], cwd=project,
                          capture_output=True, text=True, encoding="utf-8")


def test_attack_path_is_the_same_for_absolute_and_relative(tmp_path):
    """Сценарий «Абсолютный и относительный путь»: оба `render-html`, оба `view-json`."""
    project, src, attack = project_with_attack(tmp_path)
    relative = "openspec/changes/demo/attack/decisions.md"
    for given in (attack, relative):
        run = run_in(project, "view-json", src, "--attack", given)
        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout)["attacks"][0]["path"] == relative
        out = project / "page.html"
        assert run_in(project, "render-html", src, "--out", out, "--attack", given).returncode == 0
        html = out.read_text(encoding="utf-8")
        start = html.index("const ATTACK = ") + len("const ATTACK = ")
        assert json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))[0][0]["path"] == relative
        assert str(tmp_path) not in html[start:start + 400]


@pytest.mark.skipif(os.name != "nt", reason="обратные косые — разделитель только на Windows")
def test_attack_path_with_backslashes_goes_with_slashes(tmp_path):
    """Сценарий «Обратные косые»."""
    project, src, _ = project_with_attack(tmp_path)
    run = run_in(project, "view-json", src, "--attack", r"openspec\changes\demo\attack\decisions.md")
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["attacks"][0]["path"] == "openspec/changes/demo/attack/decisions.md"


def test_attack_file_outside_the_root(tmp_path):
    """Сценарий «Файл атаки вне корня»: `../…`, каталоги выше корня не названы; на другом диске только имя."""
    project, src, _ = project_with_attack(tmp_path)
    neighbour = tmp_path / "рядом"
    neighbour.mkdir()
    shutil.copy(ATTACK_FIX / "decisions.md", neighbour / "decisions.md")
    run = run_in(project, "view-json", src, "--attack", neighbour / "decisions.md")
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["attacks"][0]["path"] == "../рядом/decisions.md"


def test_attacks_come_parsed(tmp_path):
    src, roots = journal_file(tmp_path)
    data = view(src, "--roots", roots, "--attack", ATTACK_FIX / "decisions.md", "--attack", ATTACK_FIX / "artifacts.md")
    assert [a["path"] for a in data["attacks"]] == [from_cwd(ATTACK_FIX / "decisions.md"), from_cwd(ATTACK_FIX / "artifacts.md")]
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
    assert first == {"path": from_cwd(broken), "error": f"{broken}: нет frontmatter"}
    assert len(good["rows"]) == 3
    assert gone == {"path": from_cwd(missing), "error": f"{missing}: файла нет"}


def test_invalid_journal_refused_on_stderr(tmp_path):
    j = one_record_journal("a.md", "цитата")
    j["records"][0]["status"] = "готов"
    src = tmp_path / "decisions.json"
    journal.save_journal(src, j)
    run = run_cli("view-json", src)
    assert run.returncode == 1
    assert run.stdout == ""
    assert run.stderr.startswith("[!!] F-01")


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
    (record(outcome=probe("Dismiss"), decision={"option": "B", "word": "", "date": "2026-11-02"},
            recommendation={"option": "B", "why": "из рекомендации"}), "никуда", "причина: из рекомендации"),
    (record(outcome=probe("Dismiss"), decision={"option": "B", "word": "", "date": "2026-11-02"},
            recommendation={"option": "A", "why": "из рекомендации"}), "никуда", "причина не записана"),
    (record(outcome=probe("Defer")), "design.md › Open Questions", "отложена (Defer)"),
    (record(outcome=probe("Иное")), "никуда", "исход «Иное» вне четырёх"),
    (record(decision=DECISION), "design.md › Decisions", ""),
    (record(decision=DECISION, reversibility={"level": "в одну сторону", "why": "x"}), "design.md › Decisions", "в одну сторону — первой"),
    (record(decision=DECISION, outcome={"kind": "вопрос", "value": "ответ", "reason": ""}), "design.md › Decisions", ""),
    (record(), "design.md › Open Questions", "открыта"),
]
PARKINGS = [("ИБ", "design.md › Open Questions → security.md"), ("агент", "design.md › Open Questions → research/"),
            ("материалы", "design.md › Open Questions → research/"),     # старое значение у старых журналов — туда же
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


# --- номер контракта (F-08, F-16, F-31) ----------------------------------------

def test_output_carries_the_contract_number(tmp_path):
    src, roots = journal_file(tmp_path)
    number = view(src, "--roots", roots)["contract"]
    # `plugin-core-contract`: «Номер в двух выводах» — не ниже 6, «Линза правил составления поднимает номер» — не ниже 5;
    # равенство текущему номеру держит только тест наибольшего N («Номер контракта в сценариях — не ниже N»)
    assert type(number) is int and number == journal_render.CONTRACT and number >= 6


def test_one_number_in_both_outputs(tmp_path):
    """Сценарий «Один номер в двух выводах»: `view-json` и `step_help.py` несут одно и то же целое."""
    src, roots = journal_file(tmp_path)
    project = tmp_path / "proj"
    (project / "openspec" / "changes" / "demo").mkdir(parents=True)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))), apply=fork_reply(fake_apply()))
    done = subprocess.run([sys.executable, str(ROOT / "step-help" / "step_help.py"), "--change", "demo"], cwd=project,
                          env=fork_env(tmp_path / "bin"), capture_output=True)
    assert done.returncode == 0, done.stderr
    from_help = json.loads(done.stdout.decode("utf-8"))["contract"]
    from_view = view(src, "--roots", roots)["contract"]
    assert type(from_help) is int and from_help == from_view == journal_render.CONTRACT


def test_a_new_field_does_not_raise_the_number_and_reaches_the_output(tmp_path):
    src, roots = journal_file(tmp_path)
    before = view(src, "--roots", roots)["contract"]
    j = journal.load_journal(src)
    j["records"][0]["nodes"] = ["X"]
    journal.save_journal(src, j)
    data = view(src, "--roots", roots)
    assert data["contract"] == before
    assert data["records"][0]["nodes"] == ["X"]


def test_the_page_does_not_get_the_contract_number(tmp_path):
    src, roots = journal_file(tmp_path)
    out = tmp_path / "page.html"
    assert run_cli("render-html", src, "--out", out, "--roots", roots).returncode == 0
    assert "contract" not in page_payload(out.read_text(encoding="utf-8"))


# --- file_links: карта «путь — файл от корня проекта» (F-44, F-102) ---

def links_project(tmp_path):
    """Проект с файлом в папке с пробелом и кириллицей, соседний каталог `symphysis-vscode` и файл корней с префиксом `vscode/`."""
    project = tmp_path / "проект"
    (project / "док ументы").mkdir(parents=True)
    (project / "док ументы" / "файл один.md").write_text("раз\nдва\n", encoding="utf-8")
    side = tmp_path / "symphysis-vscode"
    (side / "src").mkdir(parents=True)
    (side / "src" / "a.ts").write_text("export {}\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(project), "vscode/": str(side)}), encoding="utf-8")
    change = project / "openspec" / "changes" / "demo"
    change.mkdir(parents=True)
    return project, change, roots


def test_scenario_evidence_and_record_text_in_file_links(tmp_path):
    """«Улика и текст записи»: путь улики и существующий файл из текста записи в карте, `нет.md` нет, абсолютных путей нет, без `%20`."""
    project, change, roots = links_project(tmp_path)
    j = one_record_journal("док ументы/файл один.md", "раз")
    j["records"][0]["question"] = "Смотри `док ументы/файл один.md:2-3` и `нет.md`, а ещё `C:/Windows/win.ini`"
    journal.save_journal(change / "decisions.json", j)
    links = view(change / "decisions.json", "--roots", roots)["file_links"]
    assert links == {"док ументы/файл один.md": "док ументы/файл один.md"}
    assert not any(os.path.isabs(v) or "%" in v for v in links.values())


def test_scenario_attack_file_in_file_links(tmp_path):
    """«Файл атаки»: настоящий файл из строки атаки (и сам файл атаки) попадает в карту."""
    project, change, roots = links_project(tmp_path)
    journal.save_journal(change / "decisions.json", one_record_journal("док ументы/файл один.md", "раз"))
    (change / "attack").mkdir()
    shutil.copy(ATTACK_FIX / "decisions.md", change / "attack" / "decisions.md")
    text = (change / "attack" / "decisions.md").read_text(encoding="utf-8")
    (change / "attack" / "decisions.md").write_text(text + "\nСмотри `док ументы/файл один.md`.\n", encoding="utf-8")
    links = view(change / "decisions.json", "--roots", roots, "--attack", change / "attack" / "decisions.md")["file_links"]
    assert links["док ументы/файл один.md"] == "док ументы/файл один.md"
    assert links["openspec/changes/demo/attack/decisions.md"] == "openspec/changes/demo/attack/decisions.md"


def test_scenario_evidence_root_outside_the_project_in_file_links(tmp_path):
    """«Корень улик вне проекта»: префикс на соседний каталог даёт `../symphysis-vscode/...`."""
    project, change, roots = links_project(tmp_path)
    journal.save_journal(change / "decisions.json", one_record_journal("vscode/src/a.ts", "export"))
    assert view(change / "decisions.json", "--roots", roots)["file_links"] == {"vscode/src/a.ts": "../symphysis-vscode/src/a.ts"}


def test_file_links_do_not_change_the_contract_number_or_the_page_map(tmp_path):
    project, change, roots = links_project(tmp_path)
    journal.save_journal(change / "decisions.json", one_record_journal("док ументы/файл один.md", "раз"))
    assert view(change / "decisions.json", "--roots", roots)["contract"] == journal_render.CONTRACT
    out = tmp_path / "page.html"
    assert run_cli("render-html", change / "decisions.json", "--out", out, "--roots", roots).returncode == 0
    assert "%D0%B4%D0%BE%D0%BA%20" in out.read_text(encoding="utf-8")   # карта страницы кодирует, как прежде
