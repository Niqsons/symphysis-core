"""Справка `journal.py`: перечень команд и тексты `--help`."""
# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import run_cli
import journal


def test_apply_help_says_render_is_a_separate_step():
    text = " ".join(run_cli("apply", "-h").stdout.split())
    assert "render-md" in text and "render-html" in text and "не рендерит" in text
    assert "apply" in " ".join(journal.__doc__.split())


def test_cli_apply_md4h_help_tells_the_flow():
    run = run_cli("apply-md4h", "--help")
    assert run.returncode == 0
    text = " ".join(run.stdout.split())
    assert "render-md" in text and "md4h" in text and "comments[]" in text
    assert "не рендерит" in text
    assert "--render" in text


def test_cli_lists_apply_md4h_among_the_commands():
    run = run_cli("--help")
    assert run.returncode == 0 and "apply-md4h" in run.stdout


def test_docs_state_unmatched_prefix_and_check_exit_code():
    doc = " ".join(journal.__doc__.split())
    assert "корня для пути нет" in doc and "отката на корень symphysis нет" in doc
    helptext = " ".join(run_cli("-h").stdout.split())
    assert "негодный по схеме журнал — код 1" in helptext
