"""Две проверки описи в `journal.py check`: место названо путём, цитата стоит в коде дословно (F-128.A)."""
import json
import subprocess
import sys

import journal
from conftest import ROOT, fork_record, journal_of

TOOL = ROOT / "tools" / "journal.py"
NOT_ANALYSED = "[!!] consequences.md: {} — нет ни разбора, ни исключения с причиной"


def project(tmp_path, consequences=None, code=None, sites=("src/Foo.java",)):
    """Каталог изменения с журналом на `sites`, файлами кода `code` и описью; вернёт (журнал, файл корней)."""
    for rel, text in (code or {"src/Foo.java": "if (a || b) throw q;\n"}).items():  # `q` — цитата улики `fork_record`
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    file = tmp_path / "decisions.json"
    journal.save_journal(file, journal_of(fork_record("F-01", "A", A=list(sites))))
    if consequences is not None:
        (tmp_path / "consequences.md").write_text(consequences, encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    return file, roots


def run_check(file, roots, *flags):
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "check", str(file), "--roots", str(roots), *flags],
                          capture_output=True, text=True, encoding="utf-8")


def inventory_signals(stdout):
    return [line for line in stdout.splitlines() if "consequences.md" in line]


def test_site_not_analysed(tmp_path):
    """Сценарий «Место не разобрано»."""
    done = run_check(*project(tmp_path, "**Состав:** ветки отказа, допущения\n\n## Опись\n"))
    assert done.returncode == 0
    assert inventory_signals(done.stdout) == [NOT_ANALYSED.format("src/Foo.java")]


def test_strict_mode(tmp_path):
    """Сценарий «Строгий режим»."""
    file, roots = project(tmp_path, "## Опись\n")
    assert run_check(file, roots, "--strict").returncode == 2


def test_strict_mode_clean_inventory_is_zero(tmp_path):
    file, roots = project(tmp_path, "- **Проверка** — `src/Foo.java:1` «a || b»\n")
    assert run_check(file, roots, "--strict").returncode == 0


def test_site_added_by_the_model(tmp_path):
    """Сценарий «Место добавлено моделью»: сверка идёт только по списку, файл сверх списка не сигналит."""
    done = run_check(*project(tmp_path, "- **Foo** — `src/Foo.java:1` «a || b»\n- **Bar** (`src/Bar.java`) — допущение: есть\n"))
    assert done.returncode == 0 and inventory_signals(done.stdout) == []


def test_no_inventory_yet(tmp_path):
    """Сценарий «Описи ещё нет»."""
    file, roots = project(tmp_path)
    done = run_check(file, roots, "--strict")
    assert done.returncode == 0 and inventory_signals(done.stdout) == []


def test_other_spelling_of_the_path(tmp_path):
    """Сценарий «Другое написание пути»: обратная косая и `:строка` закрывают место, префикс корня — тот же."""
    done = run_check(*project(tmp_path, "- **Foo** — `src\\Foo.java:270` «a || b»\n"))
    assert inventory_signals(done.stdout) == []

    other = tmp_path / "prefixed"
    other.mkdir()
    code = {"calibration/src/Foo.java": "if (a || b) return;\n"}
    done = run_check(*project(other, "- **Foo** — `calibration\\src\\Foo.java:270` «a || b»\n", code=code,
                              sites=("calibration/src/Foo.java",)))
    assert inventory_signals(done.stdout) == []


def test_other_prefix_is_another_file(tmp_path):
    """Сверка с границами пути: путь с другим префиксом или длинней — другой файл, место не закрыто."""
    for text in ("- `calibration/src/Foo.java` разобран\n", "- `xsrc/Foo.java` разобран\n",
                 "- `src/Foo.javascript` разобран\n", "- `src/Foo.java.bak` разобран\n"):
        done = run_check(*project(tmp_path, text))
        assert inventory_signals(done.stdout) == [NOT_ANALYSED.format("src/Foo.java")], text


def test_path_closes_the_site_in_any_markup(tmp_path):
    for text in ("- `src/Foo.java:12` «a || b»\n", "(`src/Foo.java`)\n", "src/Foo.java.\n", "**src/Foo.java**\n",
                 "| src/Foo.java | причина |\n", "./src/Foo.java — причина\n"):
        done = run_check(*project(tmp_path, text))
        assert inventory_signals(done.stdout) == [], text


def test_quote_is_not_in_the_file(tmp_path):
    """Сценарий «Цитаты нет в файле дословно»: разбор держит `||`, номер строки не сверяется."""
    done = run_check(*project(tmp_path, "- **Foo** — `src/Foo.java:7` «a || c»\n"))
    assert done.returncode == 0
    assert inventory_signals(done.stdout) == ["[!!] consequences.md: src/Foo.java «a || c» — цитаты нет дословно"]


def test_quote_with_pipes_apostrophe_and_backtick_is_found(tmp_path):
    """Край F-39: `||`, апостроф, обратный апостроф, неверный номер строки — сигнала нет."""
    code = {"src/Foo.java": "if (a || b) throw new Error('нет `тут`');\n"}
    text = "- **Foo** — `src/Foo.java:999` «a || b) throw new Error('нет `тут`')»\n"
    done = run_check(*project(tmp_path, text, code=code))
    assert inventory_signals(done.stdout) == []


def test_quote_runs_to_the_last_guillemet_of_the_line(tmp_path):
    """Предположение б: цитата — до последней `»` в строке; внутренние кавычки и таблица ей не мешают."""
    code = {"src/Foo.java": "сказал «да» и ушёл\n"}
    for text in ("- `src/Foo.java:1` «сказал «да» и»\n", "| src/Foo.java:1 «сказал «да» и» | ветка |\n",
                 "src/Foo.java:1 «сказал «да» и»\n"):
        done = run_check(*project(tmp_path, text, code=code))
        assert inventory_signals(done.stdout) == [], text


def test_line_without_quote_is_not_parsed(tmp_path):
    """Строку без цитаты судит человек или атака, скрипт форму не разбирает (F-128.A)."""
    done = run_check(*project(tmp_path, "- **Foo** — `src/Foo.java:7` ветка где-то здесь\n"))
    assert inventory_signals(done.stdout) == []


def test_file_without_failure_branches(tmp_path):
    """Сценарий «Файл без веток отказа»: строка без цитаты закрывает место по пути."""
    text = "- **Foo** (`src/Foo.java`): веток отказа не найдено, искал: `throw`, `catch`\n"
    done = run_check(*project(tmp_path, text))
    assert done.returncode == 0 and inventory_signals(done.stdout) == []


def test_only_assumptions(tmp_path):
    """Сценарий «Только допущения»: место закрыто по пути, цитат нет."""
    text = "**Состав:** допущения; ветки отказа выключены настройкой\n\n- **Foo** (`src/Foo.java`) — допущение: читает файл целиком\n"
    done = run_check(*project(tmp_path, text))
    assert done.returncode == 0 and inventory_signals(done.stdout) == []


def test_all_columns_off(tmp_path):
    """Сценарий «Все колонки выключены»: файл с причиной сверки мест не даёт."""
    done = run_check(*project(tmp_path, "**Причина:** все колонки выключены настройками\n"))
    assert done.returncode == 0 and inventory_signals(done.stdout) == []


def test_started_before_the_artifact(tmp_path):
    """Сценарий «Изменение, начатое до артефакта»: строка 1.1 сверки мест не даёт и не красит `--strict`."""
    file, roots = project(tmp_path, "# Последствия: x\r\n\r\n**Причина:** шаг появился позже\r\n")
    assert inventory_signals(run_check(file, roots).stdout) == []
    assert run_check(file, roots, "--strict").returncode == 0


def test_reason_inside_a_line_does_not_turn_the_check_off(tmp_path):
    """Шаблон держит `**Причина:**` образцом в комментарии: оставленный комментарий сверку не снимает."""
    text = "<!-- Нечего разбирать: вместо разделов строка «**Причина:** механизмов нет». -->\n\n## Опись\n"
    done = run_check(*project(tmp_path, text))
    assert inventory_signals(done.stdout) == [NOT_ANALYSED.format("src/Foo.java")]


def test_reason_file_still_has_its_quotes_checked(tmp_path):
    """Причина снимает только сверку мест: неверная цитата остаётся неверной."""
    done = run_check(*project(tmp_path, "**Причина:** шаг появился позже\n\n`src/Foo.java:1` «нет такого»\n"))
    assert inventory_signals(done.stdout) == ["[!!] consequences.md: src/Foo.java «нет такого» — цитаты нет дословно"]


def test_inventory_path_with_dotdot_is_not_read(tmp_path):
    """security.md, пути с `../`: цитата вне корня файл не читает и называет причину."""
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("секрет\n", encoding="utf-8")
    done = run_check(*project(root, "- `src/Foo.java:1` «a || b»\n- `../secret.txt:1` «секрет»\n"))
    assert inventory_signals(done.stdout) == ["[!!] consequences.md: ../secret.txt «секрет» — вне корня"]


def test_absolute_path_in_the_citation_is_normalized(tmp_path):
    """Цитата с абсолютным путём внутри корня сверяется по тому же пути, что и список мест."""
    absolute = str(tmp_path / "src" / "Foo.java")
    done = run_check(*project(tmp_path, f"- `src/Foo.java` разобран\n- `{absolute}:1` «a || b»\n"))
    assert inventory_signals(done.stdout) == []


def test_quote_in_missing_file_names_the_reason(tmp_path):
    done = run_check(*project(tmp_path, "- `src/Foo.java` разобран\n- `src/Nope.java:1` «x»\n"))
    assert inventory_signals(done.stdout) == ["[!!] consequences.md: src/Nope.java «x» — файла нет"]


def test_binary_code_file_is_unchecked_not_a_signal(tmp_path):
    """Как у улик: «не проверить» — `[--]`, `--strict` не красит."""
    file, roots = project(tmp_path, "- `src/Foo.java:1` «a || b»\n- `src/Bin.dat:1` «x»\n")
    (tmp_path / "src" / "Bin.dat").write_bytes(b"\x00\x01\x02")
    done = run_check(file, roots, "--strict")
    assert done.returncode == 0
    assert inventory_signals(done.stdout) == ["[--] consequences.md: src/Bin.dat — не проверить: бинарный файл"]


def test_inventory_not_utf8_is_unchecked(tmp_path):
    file, roots = project(tmp_path)
    (tmp_path / "consequences.md").write_bytes("опись".encode("cp1251"))
    done = run_check(file, roots, "--strict")
    assert done.returncode == 0
    assert inventory_signals(done.stdout) == ["[--] consequences.md: не проверить: не UTF-8"]


def test_check_output_still_starts_with_the_evidence_line(tmp_path):
    """`symphysis check` берёт строку «улик сверено» из вывода: сверка описи её не трогает."""
    done = run_check(*project(tmp_path, "## Опись\n"))
    assert "улик сверено" in done.stdout.splitlines()[0]


def test_module_does_not_read_settings():
    """F-128.A: сверка не смотрит на `symphysis.yaml`, строка `**Состав:**` ей не нужна."""
    source = (ROOT / "tools" / "journal_consequences.py").read_text(encoding="utf-8")
    assert "symphysis_config" not in source and "symphysis.yaml" not in source and "**Состав:**" not in source
