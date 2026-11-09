"""`anchors/anchor_refs.py`: якоря записей журнала в мастер-спеках после синхронизации (F-24, F-35, F-40, F-41, F-49, F-65)."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import ROOT
import anchor_refs
import journal_model
import trace_graph

SCRIPT = ROOT / "anchors" / "anchor_refs.py"
CHANGE = "demo"
JOURNAL = ("F-07", "F-14", "F-20", "F-21", "F-26", "F-47", "F-49")
SCN = "#### Scenario: {}\n{}- **WHEN** a\n- **THEN** b\n\n"


def block(name, text, scenarios=(("Сц", ""),), tail=""):
    return f"### Requirement: {name}\n{text}\n\n" + "".join(SCN.format(n, under) for n, under in scenarios) + tail


ONE = block("Один", "Текст SHALL (F-20) и новый (F-21), вне журнала (F-74), (журнал `symphysis-schema`: F-26.B) и (F-26).",
            (("Старый", "<!-- F-47 -->\n"),))
TWO = block("Два", "Текст SHALL (F-7): под заголовком стоит `<!-- F-14 -->`, образец ``<!-- F-14 -->``.",
            (("Новый", "<!-- F-14 -->\n"),), "<!-- требование из F-49; пробами не проходило -->\n\n")
THREE = block("Три", "Чужой блок SHALL (F-20).")
DELTA = "## MODIFIED Requirements\n\n" + ONE + "## ADDED Requirements\n\n" + TWO
MASTER = "# demo\n\n## Requirements\n\n" + ONE + TWO + THREE  # мастер после `/opsx:sync`: блоки дельты и чужой блок


def project(tmp_path, journal=JOURNAL, delta=DELTA, master=MASTER, crlf=False):
    """Проект с изменением `demo` (дельта, журнал) и мастер-спекой `demo` после синхронизации."""
    root = tmp_path / "proj"
    base = root / "openspec" / "changes" / CHANGE
    (base / "specs" / "demo").mkdir(parents=True)
    (base / ".openspec.yaml").write_text("schema: symphysis\n", encoding="utf-8")
    records = [journal_model._new_record(rid, f"Вопрос {rid}?") for rid in journal]
    (base / "decisions.json").write_text(json.dumps({"title": "t", "source": "", "records": records}, ensure_ascii=False,
                                                    indent=1) + "\n", encoding="utf-8")
    (base / "specs" / "demo" / "spec.md").write_text(delta, encoding="utf-8", newline="\n")
    path = root / "openspec" / "specs" / "demo" / "spec.md"
    path.parent.mkdir(parents=True)
    path.write_text(master, encoding="utf-8", newline="\r\n" if crlf else "\n")
    return root, base, path


def run(root, change=CHANGE):
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), change], capture_output=True, text=True,
                          encoding="utf-8", cwd=root)


def tree_hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob("*") if p.is_file()}


def snapshot_with_base(base, numbers):
    """Снимок формата 2 с базой по требованию «Один»: `numbers` — строки ссылок мастера до синхронизации."""
    (base / "graph").mkdir()
    snap = {"format": trace_graph.GRAPH_FORMAT, "sources": [], "nodes": [], "edges": [], "candidates": [], "roots": [],
            "base": {"demo": {"Один": {"numbers": numbers, "scenarios": {}, "text": "x", "traces": []}}}}
    (base / "graph" / "req-graph.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")


def test_implementation_annotation_is_data_and_stays_with_its_requirement(tmp_path):
    declaration = '<!-- symphysis:implements {"modules":[{"repo":"core","module":"F-19"}],"files":[{"repo":"core","path":"F-19.py"}]} -->'
    delta = '## ADDED Requirements\n\n### Requirement: One\nThe system SHALL work (F-19).\n' + declaration + '\n\n#### Scenario: S\n- **GIVEN** x\n- **WHEN** y\n- **THEN** z\n'
    master = delta.replace('## ADDED Requirements', '## Requirements')
    root, base, path = project(tmp_path, delta=delta, master=master, journal=('F-19',))
    result = run(root)
    assert result.returncode == 0, result.stderr
    actual = path.read_text(encoding='utf-8')
    assert declaration in actual
    assert f'({CHANGE}/F-19)' in actual


# --- переписывание (F-24, F-35) ---------------------------------------------------------------------------------------

def test_bare_journal_number_becomes_anchor_and_output_names_file_line_and_reference(tmp_path):
    """`record-anchors`: «Голый номер после синхронизации» — `(F-21)` блока изменения стал `(demo/F-21)`; вывод называет файл,
    строку и ссылку; число приводится к виду id записи: `F-7` → `demo/F-07`."""
    root, _, path = project(tmp_path)
    done = run(root)
    assert done.returncode == 0, done.stderr
    text = path.read_text(encoding="utf-8")
    assert "(demo/F-21)" in text and "(F-21)" not in text and "(demo/F-07)" in text
    assert re.search(r"^openspec/specs/demo/spec\.md:\d+: F-21 → demo/F-21$", done.stdout, re.MULTILINE), done.stdout
    assert "Переписано ссылок:" in done.stdout and "Traceback" not in done.stderr


def test_second_run_changes_nothing(tmp_path):
    """`record-anchors`: «Повтор ничего не меняет» — после первого запуска файлы те же, вывод говорит, что переписывать нечего."""
    root, _, path = project(tmp_path)
    assert run(root).returncode == 0
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    again = run(root)
    assert again.returncode == 0 and anchor_refs.NOTHING in again.stdout and "→" not in again.stdout, again.stdout
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_number_outside_journal_and_other_block_stay(tmp_path):
    """`record-anchors`: «Номер вне журнала и чужой блок» — `(F-74)` без записи в журнале и голое `(F-20)` блока, которого дельта
    не несёт, остались как были."""
    root, _, path = project(tmp_path)
    run(root)
    text = path.read_text(encoding="utf-8")
    assert "(F-74)" in text and "demo/F-74" not in text
    assert "Чужой блок SHALL (F-20)." in text


def test_reference_with_journal_name_is_untouched(tmp_path):
    """`record-anchors`: «Ссылка с именем не трогается» — ``(журнал `symphysis-schema`: F-26.B)`` прежняя, `(F-26)` рядом стал
    `(demo/F-26)`."""
    root, _, path = project(tmp_path)
    run(root)
    text = path.read_text(encoding="utf-8")
    assert "(журнал `symphysis-schema`: F-26.B) и (demo/F-26)." in text


def test_marker_and_comment_of_block_are_rewritten(tmp_path):
    """`record-anchors`: «Маркер под сценарием» (F-62) — `<!-- F-47 -->` стал `<!-- demo/F-47 -->`; комментарий «требование
    из F-49; пробами не проходило» тоже несёт якорь."""
    root, _, path = project(tmp_path)
    run(root)
    text = path.read_text(encoding="utf-8")
    assert "<!-- demo/F-47 -->" in text and "<!-- F-47 -->" not in text
    assert "<!-- требование из demo/F-49; пробами не проходило -->" in text


def test_sample_in_single_backticks_is_rewritten_and_double_backticks_are_not(tmp_path):
    """`record-anchors`: «Образец в обратных кавычках» (F-41) — что граф читает как ссылку, то скрипт и переписывает: образец
    в одинарных обратных кавычках и маркер стали якорем, образец в двойных не тронут."""
    root, _, path = project(tmp_path)
    run(root)
    text = path.read_text(encoding="utf-8")
    assert "стоит `<!-- demo/F-14 -->`, образец ``<!-- F-14 -->``." in text
    assert text.count("<!-- demo/F-14 -->") == 2  # образец в одинарных и маркер под сценарием «Новый»


# --- унаследованные голые номера (F-40) --------------------------------------------------------------------------------

def test_inherited_bare_number_from_snapshot_base_stays_bare(tmp_path):
    """`record-anchors`: «Унаследованный голый номер» (F-40) — `(F-20)` стоит в базе снимка: остался голым, `(F-21)` переписан."""
    root, base, path = project(tmp_path)
    snapshot_with_base(base, ["F-20"])
    done = run(root)
    text = path.read_text(encoding="utf-8")
    assert "Текст SHALL (F-20) и новый (demo/F-21)" in text, text
    assert "нет записи базы снимка" not in done.stdout


def test_without_snapshot_every_bare_journal_number_is_rewritten_and_output_says_so(tmp_path):
    """`record-anchors`: «Унаследованный голый номер» (F-40) — без снимка переписаны все голые номера журнала, вывод это называет."""
    root, _, path = project(tmp_path)
    done = run(root)
    assert "Текст SHALL (demo/F-20) и новый (demo/F-21)" in path.read_text(encoding="utf-8")
    assert "у требования «Один» нет записи базы снимка" in done.stdout, done.stdout


def test_snapshot_of_format_one_is_not_a_base(tmp_path):
    """Снимок формата 1 базы не даёт (F-25, F-61): переписываются все голые номера журнала."""
    root, base, path = project(tmp_path)
    snapshot_with_base(base, ["F-20"])
    snap = json.loads((base / "graph" / "req-graph.json").read_text(encoding="utf-8"))
    snap["format"] = 1
    (base / "graph" / "req-graph.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    run(root)
    assert "(demo/F-20) и новый (demo/F-21)" in path.read_text(encoding="utf-8")


# --- границы записи (F-49, парковки F-55, F-56) -----------------------------------------------------------------------

def test_change_dir_is_untouched(tmp_path):
    """`record-anchors`: «Каталог изменения прежний» (F-49) — дельты, журнал и снимок после запуска байт в байт прежние."""
    root, base, _ = project(tmp_path)
    snapshot_with_base(base, ["F-20"])
    before = tree_hashes(base)
    assert run(root).returncode == 0
    assert tree_hashes(base) == before


def test_only_master_spec_is_written(tmp_path):
    """Пишется только `openspec/specs/<cap>/spec.md`: других файлов в проекте не прибавилось, временного файла нет."""
    root, _, path = project(tmp_path)
    before = set(tree_hashes(root))
    run(root)
    assert set(tree_hashes(root)) == before and not path.with_name("spec.md.tmp").exists()


def test_capability_leading_outside_root_is_refused(tmp_path):
    """`security.md` «Пути с `../`» — имя capability не по правилу имени или каталог, ведущий за корень, — отказ до записи."""
    root, _, _ = project(tmp_path)
    for bad in ("..", "../x", "a/b", "", "-x"):
        with pytest.raises(trace_graph.Refusal):
            anchor_refs.master_target(root, bad)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "openspec" / "specs" / "evil"
    try:
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
        else:
            os.symlink(outside, link, target_is_directory=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("ссылку каталога не создать")
    with pytest.raises(trace_graph.Refusal, match="за корнем проекта"):
        anchor_refs.master_target(root, "evil")


def test_bad_change_name_is_refused_before_any_path(tmp_path):
    """`security.md` «Имя изменения как аргумент скрипта» — символы оболочки, пустое имя, ведущий дефис: отказ с именем, код 1,
    без трассировки и без проекта под рукой."""
    for bad in ("a;b", "x y", "$(x)"):
        done = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), bad], capture_output=True, text=True,
                              encoding="utf-8", cwd=tmp_path)
        assert done.returncode == 1 and bad in done.stderr and "Traceback" not in done.stderr, done.stderr
    assert subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--", "-x"], capture_output=True, text=True,
                          encoding="utf-8", cwd=tmp_path).returncode == 1
    assert subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT)], capture_output=True, text=True,
                          encoding="utf-8", cwd=tmp_path).returncode == 2
    assert list(tmp_path.iterdir()) == []


def test_master_not_utf8_names_the_file(tmp_path):
    """`security.md` «Бинарные файлы» — мастер не в UTF-8: отказ с именем файла, код 1."""
    root, _, path = project(tmp_path)
    path.write_bytes(b"\xff\xfe## Requirements\n")
    done = run(root)
    assert done.returncode == 1 and "openspec/specs/demo/spec.md" in done.stderr and "UTF-8" in done.stderr, done.stderr


def test_missing_change_or_journal_is_refused(tmp_path):
    root, base, _ = project(tmp_path)
    assert run(root, "nope").returncode == 1
    (base / "decisions.json").unlink()
    done = run(root)
    assert done.returncode == 1 and "decisions.json" in done.stderr


def test_master_missing_is_a_note_not_a_refusal(tmp_path):
    """Мастер-спеки capability ещё нет: строка об этом, код 0, файлов не прибавилось."""
    root, _, path = project(tmp_path)
    path.unlink()
    done = run(root)
    assert done.returncode == 0 and "мастер-спеки нет" in done.stdout and not path.exists()


def test_crlf_master_keeps_line_endings_and_bom(tmp_path):
    """Мастер с CRLF и BOM после переписывания остаётся с CRLF и BOM: дифф — только ссылки."""
    root, _, path = project(tmp_path, crlf=True)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    run(root)
    data = path.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
    assert "(demo/F-21)" in data.decode("utf-8")


@pytest.mark.parametrize("tail", ["\n\n", "\n", ""])
def test_rewrite_keeps_line_count_and_file_tail(tmp_path, tail):
    """После переписывания в файле столько же строк и тот же хвост, что до него: дифф — только ссылки (F-51). Строки
    режутся по переводу строки, и `join` сам восстанавливает концевой перевод; второй, добавленный отдельно, удлинял бы файл
    пустой строкой при каждом запуске с заменами."""
    root, _, path = project(tmp_path, master=MASTER.rstrip("\n") + tail)
    before = path.read_bytes()
    assert run(root).returncode == 0
    after = path.read_bytes()
    assert after.count(b"\n") == before.count(b"\n")
    assert after.endswith(tail.encode()) and not after.endswith((tail + "\n").encode())
    assert b"(demo/F-21)" in after


# --- справка (F-35, F-65) ---------------------------------------------------------------------------------------------

def test_help_names_when_codes_markers_and_order():
    done = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0
    for word in ("Звать, когда", "Коды:", "Маркеры:", "Порядок:", "rules.specs", "/opsx:sync"):
        assert word in done.stdout, word


def test_trace_graph_help_names_its_area_without_rewrite_subcommand():
    """`record-anchors`: «Граф не пишет мастер» — у `trace_graph.py --help` подкоманды переписывания нет, справка называет область
    без правки артефактов."""
    done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "trace" / "trace_graph.py"), "--help"], capture_output=True,
                          text=True, encoding="utf-8")
    assert done.returncode == 0 and "артефакты изменения не правит" in done.stdout
    assert not re.search(r"anchor|rewrite|якор", done.stdout, re.IGNORECASE), done.stdout
    assert set(trace_graph.build_parser()._subparsers._group_actions[0].choices) == {"build", "report", "check", "freeze", "archive-gaps"}
