"""Флаг «прочитано» у строки `предупреждение` (capability `warning-read-flag`): чистые функции блока `flags`
шаблона `viewer/playground-template.html`, вырезанные между маркерами-комментариями и прогнанные через node.
Заметка `notes[]` вида «предупреждение прочитано: <раздел>» опознаёт строку по разделу дословно; текст флага —
отдельный сегмент заметки через « · »; тяжесть читается первым словом ячейки."""
import json
import shutil
import subprocess

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import ROOT, journal_of
import journal

TEMPLATE = ROOT / "viewer" / "playground-template.html"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="нет node: функции шаблона не прогнать")

PREFIX = "предупреждение прочитано: "


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


def row(section, severity="предупреждение", claim="утверждение строки", support="по спеке не выводится", fix="вопрос человеку"):
    return {"claim": claim, "section": section, "lens": "claim-authority", "invariant": "и", "severity": severity,
            "support": support, "fix": fix}


def note(text):
    return {"date": "2026-11-07", "text": text}


def read_by_notes(tmp_path, notes, r):
    return run_js(tmp_path, "flags", "readByNotes(input.notes, input.row)", {"notes": notes, "row": r})


def is_warning(tmp_path, r):
    return run_js(tmp_path, "flags", "isWarning(input.row)", {"row": r})


# --- требование «Заметка «прочитано» опознаёт строку атаки по разделу» ---

def test_read_text_is_prefix_and_section_verbatim(tmp_path):
    text = run_js(tmp_path, "flags", "readText(input.row)", {"row": row("F-12, options.B")})
    assert text == PREFIX + "F-12, options.B"


def test_note_with_journal_section_flags_the_row(tmp_path):
    """Сценарий «Заметка с разделом журнала»."""
    assert read_by_notes(tmp_path, [note(PREFIX + "F-12, options.B")], row("F-12, options.B")) is True
    assert read_by_notes(tmp_path, [note(PREFIX + "F-12, options.B")], row("F-13, options.A")) is False


def test_two_rows_of_one_section_are_both_flagged(tmp_path):
    """Сценарий «Две строки одного раздела»: флаг ложится на каждую строку с этим разделом."""
    notes = [note(PREFIX + "design.md, Decisions")]
    assert read_by_notes(tmp_path, notes, row("design.md, Decisions", claim="первое")) is True
    assert read_by_notes(tmp_path, notes, row("design.md, Decisions", claim="второе")) is True


def test_note_joined_from_several_remarks_flags_the_named_section(tmp_path):
    """Сценарий «Заметка в общей строке замечаний»: сегменты через « · », не равенство всей заметки."""
    joined = PREFIX + "F-12, options.B · атака attack/decisions.md · claim-authority · «…» — спор: опора есть"
    assert read_by_notes(tmp_path, [note(joined)], row("F-12, options.B")) is True
    tail = "замечание к схеме · " + PREFIX + "F-15, options.A"
    assert read_by_notes(tmp_path, [note(tail)], row("F-15, options.A")) is True
    middle = "замечание · " + PREFIX + "F-16, options.A · ещё одно"
    assert read_by_notes(tmp_path, [note(middle)], row("F-16, options.A")) is True


def test_flag_text_inside_a_dispute_does_not_flag(tmp_path):
    """Сценарий «Текст флага внутри спора флага не даёт»: текст засчитывается только на границах сегмента."""
    dispute = "атака attack/decisions.md · claim-authority · «…» — спор: не согласен, что " + PREFIX + "F-12, options.B"
    assert read_by_notes(tmp_path, [note(dispute)], row("F-12, options.B")) is False
    longer = PREFIX + "F-12, options.B и ещё слова"
    assert read_by_notes(tmp_path, [note(longer)], row("F-12, options.B")) is False
    shorter_section = PREFIX + "F-12, options.B"
    assert read_by_notes(tmp_path, [note(shorter_section)], row("F-12, options")) is False


def test_whitespace_in_the_note_is_collapsed(tmp_path):
    """Сценарий «Пробелы в заметке схлопываются»: перенос строки и два пробела — один пробел, как у споров."""
    assert read_by_notes(tmp_path, [note("предупреждение   прочитано: F-12,\n  options.B")], row("F-12, options.B")) is True
    assert read_by_notes(tmp_path, [note(PREFIX + "F-12, options.B")], row("F-12,  options.B ")) is True


def test_note_without_a_row_flags_nobody(tmp_path):
    """Сценарий «Строка снята повтором атаки»: заметка без строки с таким разделом флага не даёт."""
    notes = [note(PREFIX + "F-30, options.A")]
    assert read_by_notes(tmp_path, notes, row("F-30, options.B")) is False
    assert read_by_notes(tmp_path, notes, row("F-31, options.A")) is False
    assert read_by_notes(tmp_path, [], row("F-30, options.A")) is False


# --- требование «Флаг только у предупреждений» ---

def test_demoted_blocker_is_a_warning(tmp_path):
    """Сценарий «Понижённый блокер несёт переключатель»: первое слово ячейки без учёта регистра."""
    assert is_warning(tmp_path, row("F-20, options.A", severity="предупреждение (решено человеком в F-09)")) is True
    assert is_warning(tmp_path, row("F-20, options.A", severity="Предупреждение")) is True
    assert read_by_notes(tmp_path, [note(PREFIX + "F-20, options.A")],
                         row("F-20, options.A", severity="предупреждение (решено человеком в F-09)")) is True


def test_unprovable_row_is_a_warning(tmp_path):
    """Сценарий «Невыводимое»: опора «по спеке не выводится» при тяжести `предупреждение`."""
    assert is_warning(tmp_path, row("F-21, options.A", support="по спеке не выводится")) is True


def test_blocker_and_reference_are_not_warnings(tmp_path):
    assert is_warning(tmp_path, row("F-20, options.A", severity="блокер")) is False
    assert is_warning(tmp_path, row("F-20, options.A", severity="справка")) is False
    assert is_warning(tmp_path, row("F-20, options.A", severity="warning")) is False


def test_note_as_apply_stores_it_flags_the_row(tmp_path):
    """Задача 3.2, сценарий «Отметка попадает в промпт»: текст заметки ровно в том виде, в каком его кладёт `apply`
    (вся строка «Замечания к схеме:» одной заметкой), даёт флаг названному разделу."""
    joined = PREFIX + "F-12, options.B · атака attack/decisions.md · claim-authority · «…» — спор: опора есть"
    j = journal_of()
    journal.apply_answers(j, journal.parse_answers("Замечания к схеме: " + joined + "\n"), "2026-11-07")
    assert j["notes"][-1]["text"] == joined
    assert read_by_notes(tmp_path, j["notes"], row("F-12, options.B")) is True
    assert read_by_notes(tmp_path, j["notes"], row("F-13, options.A")) is False


def test_note_with_a_blocker_section_does_not_flag(tmp_path):
    """Сценарий «Заметка с разделом блокера»: заметка есть, а флага у блокера нет."""
    notes = [note(PREFIX + "F-20, options.A")]
    assert read_by_notes(tmp_path, notes, row("F-20, options.A", severity="блокер")) is False
    assert read_by_notes(tmp_path, notes, row("F-20, options.A", severity="справка")) is False
