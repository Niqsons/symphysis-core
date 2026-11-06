"""Каждый `test_*.py` из git лежит под одним из `testpaths` в `pytest.ini`: тест нового модуля не пропадает молча."""
import configparser
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_paths(ini: Path) -> list[str]:
    parser = configparser.ConfigParser()
    parser.read(ini, encoding="utf-8")
    return parser["pytest"]["testpaths"].split()


def strays(ini: Path, files: list[str]) -> list[str]:
    """Тесты вне всех путей `ini`."""
    paths = [path.rstrip("/") for path in read_paths(ini)]
    return [file for file in files
            if Path(file).name.startswith("test_") and file.endswith(".py")
            and not any(file.startswith(path + "/") for path in paths)]


def git_test_files() -> list[str]:
    done = subprocess.run(["git", "ls-files", "*test_*.py"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True)
    return done.stdout.split()


def test_strays_names_the_file_outside_testpaths(tmp_path):
    ini = tmp_path / "pytest.ini"
    ini.write_text("[pytest]" + chr(10) + "testpaths =" + chr(10) + "    tests" + chr(10) + "    a/tests" + chr(10), encoding="utf-8")
    assert strays(ini, ["tests/test_x.py", "a/tests/test_y.py", "b/tests/test_z.py", "b/helper.py"]) == [
        "b/tests/test_z.py"]


def test_every_git_test_file_is_under_testpaths():
    files = git_test_files()
    assert files, "git ls-files не дал ни одного теста"
    assert strays(ROOT / "pytest.ini", files) == []
