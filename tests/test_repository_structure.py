"""Проверка структуры репозитория на деревьях-фикстурах в `tmp_path` (живое дерево здесь не читается)."""
import subprocess

import pytest

import repository_structure as rs

ROOT_README = """# ядро

- [decisions/](decisions/) — модуль
- [viewer/](viewer/) — модуль
- [docs/](docs/) — контур разработки
"""


def fm(name, kind="доменный", body=""):
    return f"---\nname: {name}\nkind: {kind}\n---\n\n{body}"


def base_tree():
    return {
        "README.md": ROOT_README,
        "decisions/README.md": fm("decisions", body="Решения.\n"),
        "decisions/a.py": "print('a')\n",
        "viewer/README.md": fm("viewer", body="Просмотрщик.\n"),
        "viewer/b.py": "print('b')\n",
        "docs/guide.md": "руководство\n",
    }


def build(tmp_path, tree, untracked=None):
    """Дерево в tmp_path: файлы из `tree` в индексе git, из `untracked` — на диске вне git."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for rel, content in {**tree, **{k: v for k, v in (untracked or {}).items()}}.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    subprocess.run(["git", "-C", str(tmp_path), "add", "--"] + list(tree), check=True)
    return tmp_path


def joined(problems):
    return "\n".join(problems)


def test_эталонное_дерево_зелёное(tmp_path):
    build(tmp_path, base_tree())
    assert rs.check_repository(tmp_path) == []


# --- 1.1 README корня

def test_каталог_без_пометки_красный(tmp_path):
    tree = base_tree()
    tree["tools/x.py"] = "x\n"
    build(tmp_path, tree)
    assert "tools/" in joined(rs.check_root_readme(rs.Repo(tmp_path)))


def test_каталоги_корня_вне_git_не_требуются(tmp_path):
    build(tmp_path, base_tree(), untracked={".symphysis/a.txt": "a", "upstream/b.txt": "b", "node_modules/c.js": "c"})
    assert rs.check_root_readme(rs.Repo(tmp_path)) == []


def test_контур_разработки_с_README_модуля_красный(tmp_path):
    tree = base_tree()
    tree["docs/README.md"] = fm("docs")
    build(tmp_path, tree)
    assert "docs/" in joined(rs.check_root_readme(rs.Repo(tmp_path)))


def test_контур_разработки_с_README_без_frontmatter_зелёный(tmp_path):
    tree = base_tree()
    tree["docs/README.md"] = "# Документы\n"
    build(tmp_path, tree)
    assert rs.check_root_readme(rs.Repo(tmp_path)) == []


def test_строка_о_каталоге_которого_нет_красная(tmp_path):
    tree = base_tree()
    tree["README.md"] += "- [scripts/](scripts/) — контур разработки\n"
    build(tmp_path, tree)
    out = joined(rs.check_root_readme(rs.Repo(tmp_path)))
    assert "scripts/" in out and "README.md" in out


@pytest.mark.parametrize("line", [
    "- [docs](docs/) — контур разработки",
    "- [./docs/](./docs/) — контур разработки",
    "- [docs/](docs/) — служебный",
    "- [docs/](docs/)",
])
def test_неверная_форма_строки_корня_красная(tmp_path, line):
    tree = base_tree()
    tree["README.md"] = ROOT_README.replace("- [docs/](docs/) — контур разработки", line)
    build(tmp_path, tree)
    assert rs.check_root_readme(rs.Repo(tmp_path))


# --- 1.2 frontmatter

def test_имя_может_отличаться_от_каталога(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = fm("страница")
    build(tmp_path, tree)
    assert rs.check_module_frontmatter(rs.Repo(tmp_path)) == []


def test_род_вне_двух_значений_красный(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = fm("viewer", kind="служебный")
    build(tmp_path, tree)
    out = joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))
    assert "viewer/" in out and "служебный" in out


def test_род_технический_принят(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = fm("viewer", kind="технический")
    build(tmp_path, tree)
    assert rs.check_module_frontmatter(rs.Repo(tmp_path)) == []


def test_README_без_frontmatter_красный(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = "# Просмотрщик\n"
    build(tmp_path, tree)
    assert "viewer/" in joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))


def test_модуль_без_README_красный(tmp_path):
    tree = base_tree()
    del tree["viewer/README.md"]
    build(tmp_path, tree)
    assert "viewer/" in joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))


@pytest.mark.parametrize("name_line", ['name: ""', "name:", "name:    ", "name: '  '"])
def test_пустое_имя_красное(tmp_path, name_line):
    tree = base_tree()
    tree["viewer/README.md"] = f"---\n{name_line}\nkind: доменный\n---\n"
    build(tmp_path, tree)
    assert "viewer/" in joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))


def test_два_модуля_с_одним_именем_красные(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = fm("decisions")
    build(tmp_path, tree)
    out = joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))
    assert "decisions/" in out and "viewer/" in out


@pytest.mark.parametrize("value", ["!!python/object/apply:os.system ['x']", "!Tag decisions", "&a decisions", "*a"])
def test_тег_yaml_красный_и_не_исполняется(tmp_path, value):
    tree = base_tree()
    tree["viewer/README.md"] = f"---\nname: {value}\nkind: доменный\n---\n"
    build(tmp_path, tree)
    out = joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))
    assert "viewer/" in out and "тег" in out


def test_тег_в_роде_красный(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = "---\nname: viewer\nkind: !!str доменный\n---\n"
    build(tmp_path, tree)
    assert "viewer/" in joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))


def test_ручной_разбор_кавычек_комментария_и_crlf():
    fields, errors = rs.parse_frontmatter('﻿---\r\nname: "a b"  \r\nkind: технический # примечание\r\n---\r\n')
    # BOM снимает чтение файла; здесь проверяем остальное на тексте без него
    fields, errors = rs.parse_frontmatter('---\r\nname: "a b"  \r\nkind: технический # примечание\r\n---\r\n')
    assert (fields, errors) == ({"name": "a b", "kind": "технический"}, [])


def test_README_с_BOM_читается(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = b"\xef\xbb\xbf" + fm("viewer").encode("utf-8")
    build(tmp_path, tree)
    assert rs.check_module_frontmatter(rs.Repo(tmp_path)) == []


# --- 1.3 вложенные каталоги

def with_nested(tree, readme_body, dirs=("tests",)):
    tree["viewer/README.md"] = fm("viewer", body=readme_body)
    for d in dirs:
        tree[f"viewer/{d}/t.py"] = "t\n"
    return tree


def test_вложенный_каталог_описан(tmp_path):
    build(tmp_path, with_nested(base_tree(), "- [tests/](tests/) — тесты модуля\n"))
    assert rs.check_nested_dirs(rs.Repo(tmp_path)) == []


def test_каталог_появился_без_описания_красный(tmp_path):
    build(tmp_path, with_nested(base_tree(), "Только текст.\n"))
    out = joined(rs.check_nested_dirs(rs.Repo(tmp_path)))
    assert "viewer/" in out and "tests/" in out


def test_вложенный_каталог_вне_git_не_требуется(tmp_path):
    build(tmp_path, base_tree(), untracked={"viewer/__pycache__/x.pyc": b"\x00\x01"})
    assert rs.check_nested_dirs(rs.Repo(tmp_path)) == []


def test_ссылка_на_удалённый_каталог_красная(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = fm("viewer", body="- [fixtures/](fixtures/) — данные\n")
    build(tmp_path, tree)
    out = joined(rs.check_nested_dirs(rs.Repo(tmp_path)))
    assert "viewer/" in out and "fixtures/" in out


def test_ссылка_с_родительским_путём_не_засчитывается(tmp_path):
    # `../decisions/` не вложенный каталог viewer, а соседний модуль; настоящий `tests/` остаётся без описания
    tree = with_nested(base_tree(), "- [../decisions/](../decisions/) — сосед\n")
    build(tmp_path, tree)
    out = joined(rs.check_nested_dirs(rs.Repo(tmp_path)))
    assert "`tests/` не описан" in out and "decisions" not in out


def test_ссылка_через_обход_внутрь_модуля_нормализуется(tmp_path):
    tree = with_nested(base_tree(), "- [../viewer/tests/x/](../viewer/tests/x/) — глубже\n- [tests/](tests/) — тесты\n")
    build(tmp_path, tree)
    assert rs.check_nested_dirs(rs.Repo(tmp_path)) == []


@pytest.mark.parametrize("link", ["[tests](tests/)", "[./tests/](./tests/)", "[tests/](./tests/)", "[x/](tests/)"])
def test_другая_форма_ссылки_красная(tmp_path, link):
    build(tmp_path, with_nested(base_tree(), f"- {link} — тесты\n"))
    assert "форме" in joined(rs.check_nested_dirs(rs.Repo(tmp_path)))


def test_ссылка_без_строки_о_каталоге_красная(tmp_path):
    build(tmp_path, with_nested(base_tree(), "[tests/](tests/)\n"))
    assert "нет строки" in joined(rs.check_nested_dirs(rs.Repo(tmp_path)))


def test_ссылка_в_блоке_кода_не_считается(tmp_path):
    build(tmp_path, with_nested(base_tree(), "```\n- [tests/](tests/) — тесты\n```\n"))
    assert "не описан" in joined(rs.check_nested_dirs(rs.Repo(tmp_path)))


# --- 1.4 место модуля

def test_модуль_не_на_своём_месте_красный(tmp_path):
    tree = base_tree()
    tree["tools/sub/README.md"] = fm("sub", kind="технический")
    tree["tools/other.py"] = "o\n"
    tree["README.md"] += "- [tools/](tools/) — контур разработки\n"
    build(tmp_path, tree)
    assert "tools/sub/" in joined(rs.check_module_places(rs.Repo(tmp_path)))


def test_модуль_схемы_на_своём_месте(tmp_path):
    tree = base_tree()
    tree["openspec/schemas/symphysis/README.md"] = fm("symphysis", kind="технический")
    tree["openspec/schemas/symphysis/schema.yaml"] = "name: symphysis\n"
    tree["README.md"] += "- [openspec/](openspec/) — контур разработки\n"
    build(tmp_path, tree)
    assert rs.check_module_places(rs.Repo(tmp_path)) == []
    assert "openspec/schemas/symphysis" in rs.module_dirs(rs.Repo(tmp_path))


def test_вложенный_модуль_красный_с_обоими_каталогами(tmp_path):
    tree = base_tree()
    tree["decisions/inner/README.md"] = fm("inner")
    tree["decisions/inner/i.py"] = "i\n"
    build(tmp_path, tree)
    out = joined(rs.check_module_places(rs.Repo(tmp_path)))
    assert "decisions/inner/" in out and "decisions/" in out


# --- 1.5 копии

def test_копия_в_двух_модулях_красная_с_обоими_путями(tmp_path):
    tree = base_tree()
    tree["decisions/common.txt"] = "общий текст\n"
    tree["viewer/common.txt"] = "общий текст\n"
    build(tmp_path, tree)
    out = joined(rs.check_copies(rs.Repo(tmp_path)))
    assert "decisions/common.txt" in out and "viewer/common.txt" in out


def test_бинарная_копия_ловится_по_байтам(tmp_path):
    blob = bytes(range(256)) + b"\xff\xfe\x00\x80"
    tree = base_tree()
    tree["decisions/icon.bin"] = blob
    tree["viewer/media.bin"] = blob
    build(tmp_path, tree)
    out = joined(rs.check_copies(rs.Repo(tmp_path)))
    assert "decisions/icon.bin" in out and "viewer/media.bin" in out


def test_пустые_файлы_и_копии_внутри_одного_модуля_и_вне_модулей_не_считаются(tmp_path):
    tree = base_tree()
    tree["decisions/__init__.py"] = ""
    tree["viewer/__init__.py"] = ""
    tree["decisions/dup1.txt"] = "тот же\n"
    tree["decisions/dup2.txt"] = "тот же\n"
    tree["docs/copy.txt"] = "тот же\n"
    build(tmp_path, tree)
    assert rs.check_copies(rs.Repo(tmp_path)) == []


def test_разные_файлы_с_одним_именем_не_копии(tmp_path):
    tree = base_tree()
    tree["decisions/x.txt"] = "один\n"
    tree["viewer/x.txt"] = "два\n"
    build(tmp_path, tree)
    assert rs.check_copies(rs.Repo(tmp_path)) == []


# --- чужой frontmatter не делает README модульным (R7)

def test_чужой_frontmatter_в_контуре_не_красный(tmp_path):
    tree = base_tree()
    tree["docs/README.md"] = "---\ntitle: Документы\n---\n# Документы\n"
    build(tmp_path, tree)
    assert rs.check_repository(tmp_path) == []


def test_чужой_frontmatter_глубже_первого_уровня_не_красный(tmp_path):
    tree = base_tree()
    tree["docs/sub/README.md"] = "---\ntitle: Раздел\n---\n"
    tree["docs/sub/x.md"] = "x\n"
    build(tmp_path, tree)
    assert rs.check_repository(tmp_path) == []


# --- лишний ключ рядом с name и kind не отменяет README модуля

EXTRA = "---\nname: viewer\nkind: KIND\ndescription: что-то\n---\n"


def test_лишний_ключ_модуль_узнан_и_проверки_идут(tmp_path):
    tree = base_tree()
    tree["viewer/README.md"] = EXTRA.replace("KIND", "служебный")
    build(tmp_path, tree)
    assert "служебный" in joined(rs.check_module_frontmatter(rs.Repo(tmp_path)))


def test_лишний_ключ_в_контуре_красный(tmp_path):
    tree = base_tree()
    tree["docs/README.md"] = EXTRA.replace("KIND", "доменный")
    build(tmp_path, tree)
    assert "docs/" in joined(rs.check_root_readme(rs.Repo(tmp_path)))


def test_лишний_ключ_глубже_первого_уровня_красный(tmp_path):
    tree = base_tree()
    tree["decisions/inner/README.md"] = EXTRA.replace("KIND", "доменный")
    tree["decisions/inner/i.py"] = "i\n"
    build(tmp_path, tree)
    assert "decisions/inner/" in joined(rs.check_module_places(rs.Repo(tmp_path)))
