import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "tools"))

import journal  # noqa: E402  (после правки sys.path)


def missing_evidence_roots() -> list[str]:
    """Корни улик из `default_roots()` (файл `tools/journal-roots.json`),
    которых на этой машине нет: `префикс -> путь`."""
    return [f"{prefix} -> {path}" for prefix, path in journal.default_roots().items() if not path.exists()]


# Тест на настоящем журнале и настоящих корнях: на машине без корней — пропуск, не красное.
requires_evidence_roots = pytest.mark.skipif(
    bool(missing_evidence_roots()),
    reason="на этой машине нет корней улик: " + "; ".join(missing_evidence_roots()))


FORK_BIN = ROOT / "upstream" / "openspec" / "bin" / "openspec.js"
FORK_DIST = ROOT / "upstream" / "openspec" / "dist" / "cli" / "index.js"


def fork_unavailable() -> str:
    """Почему CLI форка на этой машине не запустить; пустая строка — можно."""
    if shutil.which("node") is None:
        return "нет node в PATH"
    if not FORK_BIN.exists():
        return f"нет {FORK_BIN.relative_to(ROOT).as_posix()}: форк не клонирован (upstream/ в .gitignore)"
    if not FORK_DIST.exists():
        return f"форк не собран: нет {FORK_DIST.relative_to(ROOT).as_posix()} (pnpm build в upstream/openspec)"
    return ""


# Тест через CLI форка: без node или без собранного форка — пропуск, не красное.
requires_fork = pytest.mark.skipif(bool(fork_unavailable()), reason=fork_unavailable() or "форк на месте")


# --- шим форка: `tests/fixtures/fork-shim/` --------------------------------

FORK_SHIM = FIX / "fork-shim"
FORK_VERSION = "1.15.0-symphysis.4"

# Граф схемы в порядке объявления: артефакт -> что требует, что пишет. Настоящий вывод сверяет `test_step_help.py`.
SCHEMA_GRAPH = {
    "intent": ([], "intent.md"),
    "decisions": (["intent"], "decisions.json"),
    "research": (["decisions"], "research/**/*.md"),
    "attack-decisions": (["research"], "attack/decisions.md"),
    "proposal": (["research", "attack-decisions"], "proposal.md"),
    "specs": (["proposal"], "specs/**/*.md"),
    "consequences": (["specs"], "consequences.md"),
    "design": (["proposal", "consequences"], "design.md"),
    "security": (["specs"], "security.md"),
    "tasks": (["specs", "design"], "tasks.md"),
    "attack-artifacts": (["specs", "design", "security", "tasks"], "attack/artifacts.md"),
}
OPTIONAL_ARTIFACTS = ("attack-decisions", "attack-artifacts")
APPLY_REQUIRES = ["tasks", "security", "attack-artifacts"]


ALL_STEPS = ["intent", "decisions", "viewer", "research", "attack-decisions", "proposal", "specs", "consequences",
             "design", "security", "tasks", "attack-artifacts", "apply", "sync", "archive"]


def steps_text(ids=ALL_STEPS) -> str:
    """`steps.md` с заметными текстами: шаг и подраздел читаются в выводе, настоящий текст ещё будет меняться."""
    sections = {"Зачем": "why", "Механики": "mechanics", "Если пропустить": "if_skipped", "Что смотреть": "what_to_check",
                "Команда": "command"}
    parts = ["# Тексты шагов\n"]
    for step in ids:
        parts.append(f"## {step}\n\nНазвание {step}\n")
        parts += [f"### {title}\n\n{key} {step}\n" for title, key in sections.items()]
        if step == "intent":
            parts.append("### Как готовить\n\nгде искать материалы\n")
    return "\n".join(parts)


def fork_reply(body="", code=0, hang=0, stderr="", stderr_encoding="utf-8") -> dict:
    """Ответ шима на один вызов: словарь идёт в stdout JSON-ом, строка как есть."""
    stdout = json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else body
    return {"stdout": stdout, "stderr": stderr, "stderr_encoding": stderr_encoding, "code": code, "hang": hang}


def install_fork_shim(directory: Path, version=FORK_VERSION, **replies) -> Path:
    """Кладёт шим в `directory` и возвращает путь к нему: на Windows `openspec.cmd`, иначе `openspec`. `version` — строка
    версии или готовый `fork_reply`; `replies` — ответы `status`, `status_all`, `apply`, каждый `fork_reply`."""
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy(FORK_SHIM / "fork_shim.py", directory)
    name = "openspec.cmd" if os.name == "nt" else "openspec"
    shim = Path(shutil.copy(FORK_SHIM / name, directory))
    shim.chmod(0o755)
    scenario = {"version": fork_reply(version + "\n") if isinstance(version, str) else version, **replies}
    (directory / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
    return shim


def fork_calls(directory: Path) -> list[dict]:
    """Вызовы шима из `directory` по порядку: `argv`, `env`, `cwd`, `pid`."""
    calls = directory / "calls.jsonl"
    if not calls.exists():
        return []
    return [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]


def fork_env(bin_dir: Path | None = None, **extra) -> dict:
    """Окружение вызова, где настоящего форка нет: в `PATH` только `bin_dir` и системный каталог."""
    system = [str(Path(os.environ["SystemRoot"]) / "System32")] if os.name == "nt" else ["/usr/bin", "/bin"]
    env = {key: value for key, value in os.environ.items() if key != "SYMPHYSIS_OPENSPEC"}
    env["PATH"] = os.pathsep.join(([str(bin_dir)] if bin_dir else []) + system)
    env["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
    env["FORK_SHIM_PYTHON"] = sys.executable
    return {**env, **extra}


def fake_status(root: Path, change="demo", done=(), ready=(), files=None) -> dict:
    """`status --change <имя> --json` в форме форка, пути абсолютные. `done` и `ready` — идентификаторы, остальные `blocked`.
    `files` — артефакт -> файлы от каталога изменения; без него у готового файл по `outputPath`."""
    files = files or {}
    change_dir = Path(root) / "openspec" / "changes" / change
    artifacts, paths = [], {}
    for artifact, (requires, output) in SCHEMA_GRAPH.items():
        existing = files.get(artifact, [output] if artifact in done else [])
        status = "done" if artifact in done else "ready" if artifact in ready else "blocked"
        entry = {"id": artifact, "outputPath": output, "status": status, "requires": requires}
        if status == "blocked":
            entry["missingDeps"] = [need for need in requires if need not in done]
        if artifact in OPTIONAL_ARTIFACTS:
            entry.update(optional=True, fileExists=bool(existing))
        artifacts.append(entry)
        paths[artifact] = {"outputPath": output, "resolvedOutputPath": str(change_dir / output),
                           "existingOutputPaths": [str(change_dir / rel) for rel in existing]}
    return {"changeName": change, "schemaName": "symphysis",
            "planningHome": {"kind": "repo", "root": str(root), "changesDir": str(Path(root) / "openspec" / "changes"),
                             "defaultSchema": "spec-driven"},
            "changeRoot": str(change_dir), "artifactPaths": paths, "isPlanningComplete": False, "isComplete": False,
            "applyRequires": APPLY_REQUIRES, "nextSteps": [], "artifacts": artifacts}


def fake_apply(state="blocked", total=0, complete=0, missing=()) -> dict:
    """`instructions apply --change <имя> --json` в форме форка."""
    return {"changeName": "demo", "schemaName": "symphysis", "state": state, "missingArtifacts": list(missing),
            "progress": {"total": total, "complete": complete, "remaining": total - complete}, "instruction": "..."}


def fake_status_all(*names: str) -> dict:
    """`status --all --json`: у каждого изменения своя запись `changeName`; нет изменений — форма форка с `message`."""
    if not names:
        return {"changes": [], "message": "No active changes."}
    return {"changes": [{"changeName": name, "artifacts": []} for name in names]}


# --- настоящий форк: `requires_fork` ---------------------------------------

def real_env(tmp_path: Path) -> dict:
    """Окружение вызова с настоящим форком: конфиг и данные пользователя подменены пустыми каталогами."""
    return {**os.environ, "SYMPHYSIS_OPENSPEC": str(FORK_BIN), "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
            "XDG_DATA_HOME": str(tmp_path / "xdg-data")}


def real_fork(project: Path, env: dict, *args) -> str:
    done = subprocess.run(["node", str(FORK_BIN), *args], cwd=project, env={**env, "OPENSPEC_TELEMETRY": "0"},
                          capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def real_project(tmp_path: Path, *changes: str, name="proj") -> tuple[Path, dict]:
    """Проект со схемой symphysis из репозитория и изменениями `changes`, созданными настоящим форком."""
    project = tmp_path / name
    (project / "openspec" / "specs").mkdir(parents=True)
    (project / "openspec" / "changes").mkdir()
    (project / "openspec" / "config.yaml").write_text("schema: symphysis\n", encoding="utf-8", newline="\n")
    shutil.copytree(ROOT / "openspec" / "schemas" / "symphysis", project / "openspec" / "schemas" / "symphysis")
    env = real_env(tmp_path)
    for change in changes:
        real_fork(project, env, "new", "change", change, "--schema", "symphysis")
    return project, env


def one_record_journal(path: str, quote: str) -> dict:
    """Минимальный годный журнал: одна развилка, один вариант, одна улика."""
    evidence = {"path": path, "quote": quote}
    option = {"letter": "A", "text": "вариант", "added": False, "unlikely": None, "evidence": [evidence]}
    record = {"id": "F-01", "question": "вопрос?", "kind": "развилка", "status": "открыт",
              "addressee": "", "depends_on": [], "delivery": "", "options": [option],
              "antipodes": [], "recommendation": None, "decision": None, "reversibility": None,
              "outcome": None, "parking": [], "dispute": "", "consequences": "",
              "evidence": [], "comments": []}
    return {"title": "т", "source": "s.md", "records": [record]}


def fork_record(record_id: str, chosen: str | None = "A", **options: list[str]) -> dict:
    """Развилка с вариантами `A=[пути улик]`, …: `chosen` — выбранная буква, `None` — открытая развилка."""
    opts = [{"letter": letter, "text": "вариант", "added": False, "unlikely": None,
             "evidence": [{"path": path, "quote": "q"} for path in paths]}
            for letter, paths in options.items()]
    decision = None if chosen is None else {"option": chosen, "word": "", "date": "2026-11-01"}
    return {"id": record_id, "question": "вопрос?", "kind": "развилка",
            "status": "открыт" if chosen is None else "решён", "addressee": "человек", "depends_on": [],
            "delivery": "", "options": opts, "antipodes": [], "recommendation": None, "decision": decision,
            "reversibility": None, "outcome": None, "parking": [], "dispute": "", "consequences": "",
            "evidence": [], "comments": []}


def journal_of(*records: dict) -> dict:
    return {"title": "т", "source": "s.md", "records": list(records)}
