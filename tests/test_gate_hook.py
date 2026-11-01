"""Хук гейта имён: что уходит, то и проверяется; без гейта хук отказывает, а не пропускает.
Настоящий список имён живёт вне репозиториев, поэтому гейт здесь — заглушка с тем же договором: файлы в аргументах,
рабочий каталог — дерево проверки, код 1 при находке."""
import os
import subprocess
import sys
from pathlib import Path

from conftest import ROOT

HOOK = ROOT / "tools" / "hooks" / "gate_hook.py"
INSTALL = ROOT / "tools" / "hooks" / "install_hooks.py"
ZERO = "0" * 40
STUB = """\
import os, sys
if os.environ.get("STUB_NEED_HOSTS") and not os.path.isfile(os.path.join("tools", "allowed-hosts.txt")):
    print("[!!] нет allowed-hosts"); sys.exit(1)
bad = [f for f in sys.argv[1:] if "ЗАПРЕТ" in open(f, encoding="utf-8").read()]
for f in bad:
    print(f"[!!] {f}")
sys.exit(1 if bad else 0)
"""


def git(repo, *args, env=None, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", env=env, check=check)


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    for key, value in (("user.name", "x"), ("user.email", "x@example.org"), ("core.autocrlf", "false")):
        git(path, "config", key, value)
    return path


def commit(repo: Path, name: str, text: str, message: str = "изменение") -> str:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    git(repo, "add", name)
    git(repo, "commit", "-q", "--no-verify", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def env_with_gate(tmp_path: Path, **extra) -> dict:
    gate = tmp_path / "gate_stub.py"
    gate.write_text(STUB, encoding="utf-8")
    return dict(os.environ, SYMPHYSIS_GATE=str(gate), PYTHONUTF8="1", **extra)


def hook(repo, mode, env, *args, stdin=""):
    return subprocess.run([sys.executable, str(HOOK), mode, *args], cwd=repo, env=env, input=stdin,
                          capture_output=True, text=True, encoding="utf-8")


def with_remote(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path / "w")
    bare = tmp_path / "r.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", str(bare))
    return repo


def test_pre_commit_passes_clean_and_stops_a_forbidden_name(tmp_path):
    repo = make_repo(tmp_path / "w")
    env = env_with_gate(tmp_path)
    (repo / "a.md").write_text("чисто\n", encoding="utf-8")
    git(repo, "add", "a.md")
    assert hook(repo, "pre-commit", env).returncode == 0
    (repo / "a.md").write_text("тут ЗАПРЕТ\n", encoding="utf-8")
    git(repo, "add", "a.md")
    res = hook(repo, "pre-commit", env)
    assert res.returncode == 1 and "a.md" in res.stdout


def test_pre_commit_checks_the_index_not_the_working_copy(tmp_path):
    """В индексе имя, в рабочей копии его уже нет: уйдёт индекс."""
    repo = make_repo(tmp_path / "w")
    env = env_with_gate(tmp_path)
    (repo / "a.md").write_text("ЗАПРЕТ\n", encoding="utf-8")
    git(repo, "add", "a.md")
    (repo / "a.md").write_text("чисто\n", encoding="utf-8")
    assert hook(repo, "pre-commit", env).returncode == 1


def test_tracker_key_is_stopped_by_pattern_and_known_prefixes_pass(tmp_path):
    repo = make_repo(tmp_path / "w")
    env = env_with_gate(tmp_path)
    (repo / "a.md").write_text("задача XYZ-123\n", encoding="utf-8")  # gate-ok: образец ключа
    git(repo, "add", "a.md")
    res = hook(repo, "pre-commit", env)
    assert res.returncode == 1 and "XYZ-123" in res.stdout and "a.md" in res.stdout  # gate-ok: образец ключа
    (repo / "a.md").write_text("алгоритм SHA-256, кодировка UTF-16, запись F-12\n", encoding="utf-8")
    git(repo, "add", "a.md")
    assert hook(repo, "pre-commit", env).returncode == 0
    (repo / "a.md").write_text("пример XYZ-123  gate-ok\n", encoding="utf-8")
    git(repo, "add", "a.md")
    assert hook(repo, "pre-commit", env).returncode == 0


def test_no_gate_refuses_instead_of_passing(tmp_path):
    repo = make_repo(tmp_path / "w")
    env = dict(os.environ, SYMPHYSIS_GATE=str(tmp_path / "нет.py"), PYTHONUTF8="1")
    (repo / "a.md").write_text("чисто\n", encoding="utf-8")
    git(repo, "add", "a.md")
    res = hook(repo, "pre-commit", env)
    assert res.returncode == 2 and "гейт" in res.stdout


def test_repo_allowed_hosts_reach_the_gate(tmp_path):
    """Гейт читает `tools/allowed-hosts.txt` рабочего каталога: дерево проверки несёт файл проекта."""
    repo = make_repo(tmp_path / "w")
    env = env_with_gate(tmp_path, STUB_NEED_HOSTS="1")
    (repo / "a.md").write_text("чисто\n", encoding="utf-8")
    git(repo, "add", "a.md")
    assert hook(repo, "pre-commit", env).returncode == 1
    (repo / "tools").mkdir()
    (repo / "tools" / "allowed-hosts.txt").write_text("example.org\n", encoding="utf-8")
    assert hook(repo, "pre-commit", env).returncode == 0


def test_pre_push_sees_only_what_leaves(tmp_path):
    """Имя в уже опубликованном коммите новому пушу не мешает, а имя в уходящем его останавливает."""
    repo = with_remote(tmp_path)
    env = env_with_gate(tmp_path)
    commit(repo, "old.md", "ЗАПРЕТ\n", "старый")
    git(repo, "push", "-q", "--no-verify", "origin", "main")
    clean = commit(repo, "new.md", "чисто\n")
    line = f"refs/heads/main {clean} refs/heads/main {ZERO}\n"
    assert hook(repo, "pre-push", env, "origin", "url", stdin=line).returncode == 0
    dirty = commit(repo, "bad.md", "новый ЗАПРЕТ\n")   # то же содержимое было бы уже опубликованным объектом
    res = hook(repo, "pre-push", env, "origin", "url", stdin=f"refs/heads/main {dirty} refs/heads/main {ZERO}\n")
    assert res.returncode == 1 and "bad.md" in res.stdout and "old.md" not in res.stdout


def test_pre_push_reads_commit_messages(tmp_path):
    repo = with_remote(tmp_path)
    env = env_with_gate(tmp_path)
    sha = commit(repo, "a.md", "чисто\n", "сообщение с ЗАПРЕТ")
    res = hook(repo, "pre-push", env, "origin", "url", stdin=f"refs/heads/main {sha} refs/heads/main {ZERO}\n")
    assert res.returncode == 1 and sha[:8] in res.stdout


def test_pre_push_ignores_a_branch_deletion(tmp_path):
    repo = with_remote(tmp_path)
    env = env_with_gate(tmp_path)
    commit(repo, "a.md", "ЗАПРЕТ\n")
    assert hook(repo, "pre-push", env, "origin", "url", stdin=f"(delete) {ZERO} refs/heads/x {'1' * 40}\n").returncode == 0


def test_installed_hook_runs_in_a_worktree_older_than_the_hook(tmp_path):
    """Сценарий, ради которого хук лежит в `.git/hooks`: ветка старше хука, свой worktree, новый коммит с именем."""
    repo = with_remote(tmp_path)
    env = env_with_gate(tmp_path)
    base = commit(repo, "a.md", "чисто\n")
    commit(repo, "tools/x.md", "чисто\n")
    wt = tmp_path / "old"
    git(repo, "worktree", "add", "-q", "-b", "old", str(wt), base)
    res = subprocess.run([sys.executable, str(INSTALL), "--project", str(repo)], capture_output=True, text=True, encoding="utf-8", env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    (wt / "bad.md").write_text("ЗАПРЕТ\n", encoding="utf-8")
    git(wt, "add", "bad.md")
    git(wt, "commit", "-q", "--no-verify", "-m", "c")
    push = git(wt, "push", "-q", "origin", "old", env=env, check=False)
    assert push.returncode != 0 and "bad.md" in push.stderr + push.stdout


def test_install_refuses_to_overwrite_a_foreign_hook(tmp_path):
    repo = make_repo(tmp_path / "w")
    hooks = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    hooks = (repo / hooks if not hooks.is_absolute() else hooks) / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    res = subprocess.run([sys.executable, str(INSTALL), "--project", str(repo)], capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, PYTHONUTF8="1"))
    assert res.returncode == 2 and "pre-push" in res.stdout
    assert (hooks / "pre-push").read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"
