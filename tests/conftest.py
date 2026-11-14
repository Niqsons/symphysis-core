import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

# Модули ядра с кодом (F-18 A, F-20 A): тесты импортируют код из каталогов модулей, как точки входа в исходнике.
# В установке тот же код лежит одним каталогом `.symphysis/tools/` (F-19 A) — его раскладку дают `core_files`
# и `core_clone` ниже.
CODE_MODULES = ("roots", "decisions", "viewer", "attack", "consequences", "cli", "step-help", "trace", "openspec-run",
                "settings", "anchors", "runtime")
MODULE_DIRS = [ROOT / name for name in CODE_MODULES]
CORE_SUFFIXES = (".py", ".html", ".json")   # код и данные модуля; тексты `.md` установка кладёт в `docs/`

sys.path[:0] = [str(directory) for directory in MODULE_DIRS]

import journal  # noqa: E402  (после правки sys.path)


def core_files() -> list[Path]:
    """Код и данные модулей — то, что установка кладёт в `.symphysis/tools/`: скрипты, шаблон страницы, схема журнала
    (F-41 A). Имена в модулях не повторяются: установка плоская."""
    files = sorted((file for directory in MODULE_DIRS for file in directory.iterdir()
                    if file.is_file() and file.suffix in CORE_SUFFIXES), key=lambda file: file.name)
    names = [file.name for file in files]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"core_files: имя в двух модулях, установка плоская: {duplicates}"
    return files


def core_clone(clone: Path) -> Path:
    """Клон ядра в модульной раскладке: код и данные модулей в `<clone>/<модуль>/`, настоящий файл корней
    в `<clone>/tools/` (F-40 A). Возвращает `clone`."""
    for directory in MODULE_DIRS:
        (clone / directory.name).mkdir(parents=True, exist_ok=True)
        for file in directory.iterdir():
            if file.is_file() and file.suffix in CORE_SUFFIXES:
                shutil.copy(file, clone / directory.name / file.name)
    (clone / "tools").mkdir(exist_ok=True)
    shutil.copy(ROOT / "tools" / "journal-roots.json", clone / "tools" / "journal-roots.json")
    return clone


# --- скиллы, водители и общие файлы скиллов (F-67 A, F-35 A, F-66 A) --------
# Скилл и водитель лежат в модуле своей механики: `<модуль>/skills/<имя>/`, `<модуль>/agents/`. Установка кладёт
# общие файлы в `.symphysis/docs/`, а в исходнике у каждого свой модуль.

SHARED_SKILL_FILES = {path.name: path for path in (
    ROOT / "skill-shared" / "terms.md", ROOT / "skill-shared" / "driver.md", ROOT / "decisions" / "candidate.md",
    ROOT / "cli" / "journal-cli.md", ROOT / "settings" / "config.md", ROOT / "attack" / "attack-table.md",
    ROOT / "trace" / "module-declarations.md")}


def _in_modules(root: Path, pattern: str) -> list[Path]:
    """Пути по маске от каталогов первого уровня без точки в начале: `.claude/` после установки в самом ядре — не исходник."""
    root = Path(root)
    return sorted((path for path in root.glob(pattern) if not path.relative_to(root).parts[0].startswith(".")),
                  key=lambda path: path.name)


def skill_dirs(root: Path = ROOT) -> list[Path]:
    """Каталоги скиллов `symphysis-*` всех модулей `root`: `<модуль>/skills/<имя>/`, по имени скилла."""
    return [path for path in _in_modules(root, "*/skills/symphysis-*") if path.is_dir()]


def skill_dir(name: str) -> Path:
    """Каталог скилла по имени, в каком бы модуле он ни лежал."""
    found = [path for path in skill_dirs() if path.name == name]
    assert len(found) == 1, f"скилл {name}: найдено {[str(path) for path in found]}"
    return found[0]


def agent_files(root: Path = ROOT) -> list[Path]:
    """Тела водителей всех модулей `root`: `<модуль>/agents/symphysis-*-driver.md`, по имени файла."""
    return _in_modules(root, "*/agents/symphysis-*-driver.md")


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
FORK_VERSION = "1.16.1+symphysis.6"

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


def fake_status(root: Path, change="demo", done=(), ready=(), files=None, verdicts=None) -> dict:
    """`status --change <имя> --json` в форме форка, пути абсолютные. `done` и `ready` — идентификаторы, остальные `blocked`.
    `files` — артефакт -> файлы от каталога изменения; без него у готового файл по `outputPath`. `verdicts` — артефакт ->
    значение `verdict` (`ok`, `stale`, `mismatch`, `missing`), как форк отдаёт у артефактов с вердиктом."""
    files = files or {}
    verdicts = verdicts or {}
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
        if artifact in verdicts:
            entry["verdict"] = verdicts[artifact]
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


# --- проект OpenSpec со схемой из репозитория: тесты схемы, графа, скиллов ----

SCHEMAS = ROOT / "openspec" / "schemas"
# Каталог схемы в репозитории несёт и то, что установка в каталог схемы проекта не кладёт: тесты модуля схемы (F-23 A)
# и образец конфига (F-37 A). Проект теста получает схему такой, какой её ставит инсталлятор.
SCHEMA_DEV_ONLY = shutil.ignore_patterns("tests", "__pycache__", "config.symphysis.yaml", "README.md")


def run_openspec_raw(project, *args, returncode=0):
    """`openspec <args>` из форка с `cwd=project`: `CompletedProcess` с обоими потоками.
    Код выхода не равен ожидаемому `returncode` (по умолчанию 0) — AssertionError с обоими потоками.
    Конфиг и данные пользователя подменены пустыми каталогами рядом с проектом: пользовательская
    схема не заслонит проектную."""
    env = dict(os.environ,
               XDG_CONFIG_HOME=str(project.parent / "xdg-config"),
               XDG_DATA_HOME=str(project.parent / "xdg-data"),
               OPENSPEC_TELEMETRY="0", OPENSPEC_NO_UPDATE_CHECK="1",
               OPENSPEC_NO_COMPLETIONS="1", NO_COLOR="1")
    done = subprocess.run(["node", str(FORK_BIN), *args], cwd=project, env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=120)
    assert done.returncode == returncode, (
        f"openspec {' '.join(args)} -> код {done.returncode}, ждали {returncode}\n"
        f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}")
    return done


def run_openspec(project, *args, returncode=0):
    """`openspec <args>` из форка с `cwd=project`. С `--json` — разобранный JSON, иначе — stdout."""
    done = run_openspec_raw(project, *args, returncode=returncode)
    if "--json" not in args:
        return done.stdout
    # перед JSON CLI печатает строку-предупреждение («Schema commands are experimental…»)
    return json.JSONDecoder().raw_decode(done.stdout[done.stdout.index("{"):])[0]


def make_project(tmp_path, schema="symphysis", change="demo", config=None, change_fixture=None):
    """Проект OpenSpec с пустым изменением: схема копируется из `openspec/schemas/<schema>`,
    изменение создаётся через `openspec new change` (`openspec init` не нужен). `config` — текст
    `openspec/config.yaml`; без него в конфиге одна строка `schema: <schema>`. `change_fixture` —
    каталог с файлами готового изменения: он копируется в `openspec/changes/<change>/` вместо
    `openspec new change`, так что `.openspec.yaml` берётся из фикстуры."""
    src = SCHEMAS / schema
    assert src.is_dir(), f"нет схемы {src.relative_to(ROOT)}"
    proj = tmp_path / "proj"
    (proj / "openspec" / "specs").mkdir(parents=True)
    (proj / "openspec" / "changes").mkdir()
    if config is None:
        config = f"schema: {schema}\n"
    (proj / "openspec" / "config.yaml").write_text(config, encoding="utf-8", newline="\n")
    shutil.copytree(src, proj / "openspec" / "schemas" / schema, ignore=SCHEMA_DEV_ONLY)
    if change_fixture is None:
        run_openspec(proj, "new", "change", change, "--schema", schema)
    else:
        assert change_fixture.is_dir(), f"нет фикстуры {change_fixture.relative_to(ROOT)}"
        shutil.copytree(change_fixture, proj / "openspec" / "changes" / change)
    return proj


def real_project(tmp_path: Path, *changes: str, name="proj") -> tuple[Path, dict]:
    """Проект со схемой symphysis из репозитория и изменениями `changes`, созданными настоящим форком."""
    project = tmp_path / name
    (project / "openspec" / "specs").mkdir(parents=True)
    (project / "openspec" / "changes").mkdir()
    (project / "openspec" / "config.yaml").write_text("schema: symphysis\n", encoding="utf-8", newline="\n")
    shutil.copytree(SCHEMAS / "symphysis", project / "openspec" / "schemas" / "symphysis", ignore=SCHEMA_DEV_ONLY)
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


# --- общее для тестов `decisions` и тестов, вынесенных в каталоги модулей (M1) ----------------

def evidence_of(j):
    return j["records"][0]["options"][0]["evidence"][0]


def run_check(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "journal.py"), "check", *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


def setting_journal(**fork_changes) -> dict:
    """Факт постановки F-01 и развилка F-02 с вариантами A и B; `fork_changes` — поля развилки."""
    fact = {"id": "F-01", "question": "критерий готовности", "kind": "факт", "status": "решён",
            "addressee": "постановка", "depends_on": [], "delivery": "", "options": [], "antipodes": [],
            "recommendation": None, "decision": None, "reversibility": None, "outcome": None,
            "parking": [], "dispute": "", "consequences": "F-02",
            "evidence": [{"path": "openspec/changes/x/intent.md", "quote": "критерий"}], "comments": []}
    fork = {"id": "F-02", "question": "развилка?", "kind": "развилка", "status": "открыт",
            "addressee": "человек", "depends_on": ["F-01"], "delivery": "",
            "options": [{"letter": "A", "text": "как в постановке", "added": False, "unlikely": None, "evidence": []},
                        {"letter": "B", "text": "иначе, чем в постановке", "added": False, "unlikely": None,
                         "evidence": []}],
            "antipodes": [], "recommendation": None, "decision": None, "reversibility": None, "outcome": None,
            "parking": [], "dispute": "", "consequences": "", "evidence": [], "comments": [], **fork_changes}
    return {"title": "т", "source": "decisions.json", "records": [fact, fork]}


def deviating(target="F-01", letter="B", **fork_changes) -> dict:
    """Журнал `setting_journal`, у варианта `letter` развилки F-02 — `deviation: target`."""
    j = setting_journal(**fork_changes)
    next(o for o in j["records"][1]["options"] if o["letter"] == letter)["deviation"] = target
    return j


HEADER_LINK = "### Решения по журналу [j.md](http://j.md), 2026-10-29:\n\n"


def sample_journal():
    """Учебные развилки, парковка с находкой и факты со спорами."""
    return journal.import_md(FIX / "journal-sample.md")


def rec_of(j, rid):
    return next(r for r in j["records"] if r["id"] == rid)


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "journal.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


FIXTURE = FIX / "md4h-feedback.md"


def line_of(path, needle):
    """Номер (с единицы) первой строки файла, где есть needle; файл читается как лежит на диске."""
    for n, line in enumerate(Path(path).read_bytes().decode("utf-8").split("\n"), 1):
        if needle in line:
            return n
    raise AssertionError(f"{needle!r} в {path} не найдено")


def rendered(tmp_path, j, name="d.md"):
    """Рендер журнала на диске, как его пишет `render-md`: CRLF."""
    md = tmp_path / name
    md.write_text(journal.render_md(j), encoding="utf-8", newline="\r\n")
    return md


def fixture_text():
    """Фикстура как лежит на диске — с CRLF."""
    return FIXTURE.read_bytes().decode("utf-8")


def comments_of(j, rid):
    return next(r for r in j["records"] if r["id"] == rid)["comments"]


TEMPLATE = ROOT / "viewer" / "playground-template.html"


def strip_check_fields(j):
    """Копия журнала без полей, которых в markdown нет (см. `render_md`): поля сверки улик
    `line/found/verdict`, `reversibility` и `comments` записи, `text` рекомендации, `generated` журнала —
    их источник только JSON."""
    j = copy.deepcopy(j)
    j.pop("generated", None)
    for rec in j["records"]:
        rec["reversibility"] = None
        rec["comments"] = []
        if rec["recommendation"]:
            rec["recommendation"].pop("text", None)
        for ev in rec["evidence"] + [e for o in rec["options"] for e in o["evidence"]]:
            for key in ("line", "found", "verdict"):
                ev.pop(key, None)
    return j


def html_fixture(tmp_path, quote):
    """Журнал с одной уликой и файл корней: всё внутри `tmp_path`, машина не важна."""
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    src = tmp_path / "j.json"
    journal.save_journal(src, one_record_journal("a.md", quote))
    return src, roots


ATTACK_FIX = FIX / "attack"


FAKE_SHA = "0123456789abcdef" * 4


node = shutil.which("node")


requires_node = pytest.mark.skipif(node is None, reason="нет node: шаблон просмотрщика не прогнать")


def smoke(tmp_path, html, state=None):
    """Итог `viewer-smoke.js`: панели режимов и промпт; `state` — состояние браузера, `__suffixes__` в нём —
    значения ключей `:mode` и `:attack`."""
    page = tmp_path / "v.html"
    page.write_text(html, encoding="utf-8", newline="\n")
    args = [node, str(FIX / "viewer-smoke.js"), str(page)]
    if state is not None:
        (tmp_path / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        args.append(str(tmp_path / "state.json"))
    run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def deviation_journal():
    """Факт постановки F-01 и решённая развилка F-02: вариант B отступает от F-01, A — нет."""
    j = one_record_journal("intent.md", "критерий")
    fact = j["records"][0]
    fact.update(kind="факт", status="решён", addressee="постановка", options=[],
                evidence=[{"path": "intent.md", "quote": "критерий"}])
    fork = copy.deepcopy(one_record_journal("a.md", "q")["records"][0])
    fork["options"].append({"letter": "B", "text": "наследование", "added": False, "unlikely": None,
                            "evidence": [], "deviation": "F-01"})
    fork.update(id="F-02", status="решён", addressee="человек", depends_on=["F-01"],
                decision={"option": "B", "word": "", "date": "2026-10-31"})
    j["records"].append(fork)
    assert journal.validate_journal(j) == []
    return j


def scheme_embedded(html):
    start = html.index("const SCHEME = ") + len("const SCHEME = ")
    return json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))[0]


def render_page(tmp_path, scheme=None, out=None):
    src = tmp_path / "decisions.json"
    journal.save_journal(src, sample_journal())
    if scheme is not None:
        (tmp_path / "scheme.md").write_text(scheme, encoding="utf-8", newline="")
    out = out or tmp_path / "page.html"
    run = run_cli("render-html", src, "--out", out)
    assert run.returncode == 0, run.stderr
    return out.read_text(encoding="utf-8"), src


def embedded_attack(html):
    """Список атак, встроенный в страницу на место метки `__ATTACK_JSON__`."""
    start = html.index("const ATTACK = ") + len("const ATTACK = ")
    return json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))[0]
