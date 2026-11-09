# -*- coding: utf-8 -*-
"""Страница просмотрщика — модуль `viewer`: `render_html` (шаблон и пять меток), схема решения
(`scheme_payload`, `parse_scheme`), снимок «справки нет» (`no_help_snapshot`). Данные страницы собирает
`journal_render._viewer_payload` (модуль `decisions`): viewer зависит от decisions, не наоборот."""
from __future__ import annotations

import json
import re
import base64
import copy
import hashlib
import os
from pathlib import Path

from journal_render import CONTRACT, _viewer_payload
from runtime_context import context as _execution_context

__all__ = [
    "TEMPLATE_PATH", "PLACEHOLDER", "PLACEHOLDER_ATTACK", "PLACEHOLDER_SCHEME", "PLACEHOLDER_HELP", "PLACEHOLDER_LINKS",
    "parse_scheme", "scheme_payload", "no_help_snapshot", "embed_help_resources", "render_html",
]


TEMPLATE_PATH = Path(__file__).resolve().with_name("playground-template.html")   # рядом с кодом в обеих раскладках (F-20)
PLACEHOLDER = "__JOURNAL_JSON__"
PLACEHOLDER_ATTACK = "__ATTACK_JSON__"
PLACEHOLDER_SCHEME = "__SCHEME_JSON__"
PLACEHOLDER_HELP = "__HELP_JSON__"
PLACEHOLDER_LINKS = "__LINKS_JSON__"


def _embed(obj) -> str:
    """JSON для `<script>` шаблона: `</` экранируется как `<\\/`, чтобы текст не закрыл `<script>`,
    `<!--` — как `\\u003c!--`, чтобы текст не открыл в скрипте «экранированное» состояние разбора HTML."""
    return json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/").replace("<!--", "\\u003c!--")


# --- scheme.md ----------------------------------------------------------------

RE_FENCE = re.compile(r"^ {0,3}(`{3,})[ \t]*([^`]*?)[ \t]*$")
NO_SCHEME = {"exists": False, "text": None, "blocks": 0, "first_line": None, "mermaid": None}


def parse_scheme(text: str) -> dict:
    """`scheme.md`: текст первого непустого блока mermaid, число непустых блоков и строка файла, с которой
    блок начинается, для номера строки в ошибке. BOM и CRLF не мешают; блок внутри другой ограды — не блок.
    Плагин разбирает файл сам, оба разбора сверяются набором `tests/fixtures/scheme/cases.json`."""
    fence = None
    blocks = []
    for number, line in enumerate(text.removeprefix("\ufeff").replace("\r\n", "\n").split("\n"), 1):
        match = RE_FENCE.match(line)
        if fence is None:
            if match:
                fence = {"length": len(match[1]), "mermaid": match[2] == "mermaid", "first": number + 1, "body": []}
        elif match and not match[2] and len(match[1]) >= fence["length"]:
            blocks.append(fence)
            fence = None
        else:
            fence["body"].append(line)
    if fence:
        blocks.append(fence)
    filled = [b for b in blocks if b["mermaid"] and "".join(b["body"]).strip()]
    if not filled:
        return {"text": None, "blocks": 0, "first_line": None}
    return {"text": "\n".join(filled[0]["body"]).rstrip("\n") + "\n", "blocks": len(filled), "first_line": filled[0]["first"]}


def _mermaid_src(out: Path) -> str | None:
    """Путь от страницы до файла mermaid проекта: страница вне проекта его не получает и показывает текст (F-39)."""
    here = Path(out).resolve().parent
    for up, base in enumerate([here, *here.parents]):
        if (base / ".symphysis" / "tools").is_dir():
            return "../" * up + ".symphysis/tools/mermaid.min.js"
    return None


def scheme_payload(scheme_path: Path, out: Path) -> dict:
    """Что страница `out` получает о файле `scheme_path`: своя метка шаблона, вне `_viewer_payload`, поэтому
    в `view-json` текст схемы не уходит (F-25). Не текст файла — файл без блока, а не отказ сборки."""
    path = Path(scheme_path)
    selected = _execution_context()
    mermaid = None if selected and selected["scope"] == "global" else _mermaid_src(out)
    if selected and selected["scope"] == "local" and "assets" in selected["resources"]:
        # The resolver excludes absent or modified optional executable assets.
        # A relative loader must not resurrect those bytes or search another store.
        mermaid = None
        asset = selected["resources"]["assets"].get("mermaid")
        store = Path(selected["store"]["root"]).resolve()
        if asset and Path(out).resolve().is_relative_to(store):
            try:
                mermaid = os.path.relpath(asset, Path(out).resolve().parent).replace(os.sep, "/")
            except ValueError:
                pass
    if not path.is_file():
        return {**NO_SCHEME, "mermaid": mermaid}
    return {"exists": True, **parse_scheme(path.read_text(encoding="utf-8", errors="replace")), "mermaid": mermaid}


def _runtime_manifest(selected: dict) -> dict:
    runtime = selected["runtime"]
    manifest = json.loads(Path(runtime["manifestPath"]).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != 1 or manifest.get("scope") != "global" or manifest.get("generation") != runtime["generation"] or not isinstance(manifest.get("files"), list) or not all(isinstance(entry, dict) for entry in manifest["files"]):
        raise ValueError("Поколение ресурса изменилось")
    return manifest


def _owned_asset(selected: dict, source: str) -> bytes:
    """Executable bytes are only canonical resources of the selected manifest, never journal data."""
    runtime = selected["runtime"]
    root = Path(runtime["root"]).resolve(strict=True)
    file = Path(runtime["toolsRoot"]) / Path(source).name
    manifest = _runtime_manifest(selected)
    entries = [entry for entry in manifest.get("files", [])
               if entry.get("source") == source and entry.get("projection") is not True]
    if len(entries) != 1 or not file.is_file() or file.is_symlink() or not file.resolve(strict=True).is_relative_to(root):
        raise ValueError("Ресурс выбранной поставки отсутствует")
    if not Path(entries[0]["path"]).is_absolute() or Path(entries[0]["path"]).resolve(strict=True) != file.resolve(strict=True):
        raise ValueError("Ресурс не принадлежит выбранному runtime")
    content = file.read_bytes()
    if hashlib.sha256(content).hexdigest() != entries[0].get("sha256"):
        raise ValueError("Ресурс выбранной поставки повреждён")
    return content


def _global_mermaid(selected: dict) -> dict:
    try:
        content = _owned_asset(selected, "tools/mermaid.min.js")
        content.decode("utf-8", errors="strict")
        license_text = _owned_asset(selected, "tools/mermaid.LICENSE").decode("utf-8", errors="strict")
        return {"encoding": "base64", "data": base64.b64encode(content).decode("ascii"),
                "sha256": hashlib.sha256(content).hexdigest(), "license": license_text}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return {"encoding": "base64", "data": None,
                "error": "Mermaid выбранной global-поставки отсутствует или повреждён: показан текст схемы. Восстанови эту поставку."}


def embed_help_resources(help_snapshot: dict, selected: dict | None = None, skill_install_dir: Path | str | None = None) -> dict:
    """Global skill bodies remain escaped text data; explicit alternative lookup never supplies executable JS."""
    selected = _execution_context() if selected is None else selected
    if not selected or selected["scope"] != "global":
        return help_snapshot
    result = copy.deepcopy(help_snapshot)
    result["skill_bodies"] = {}
    store_root = Path(selected["store"]["root"]).resolve(strict=True)
    runtime_root = Path(selected["runtime"]["root"]).resolve(strict=True)
    for step in result.get("steps", []):
        for skill in step.get("skills", []):
            body_id = f"skill-{len(result['skill_bodies'])}"
            skill["body_id"] = body_id
            payload = {"name": skill.get("name"), "text": None, "source": skill.get("base")}
            try:
                name, relative = skill.get("name"), skill.get("path")
                if not isinstance(name, str) or not re.fullmatch(r"symphysis-[a-z0-9-]+", name) or not isinstance(relative, str):
                    raise ValueError("Скилл не найден")
                rel = Path(relative)
                if rel.is_absolute() or ":" in relative or ".." in rel.parts or len(rel.parts) < 2 or rel.parts[-2:] != (name, "SKILL.md"):
                    raise ValueError("Путь скилла не подтверждён")
                if skill.get("base") == "project":
                    base = store_root
                elif skill.get("base") == "install":
                    base = runtime_root if skill_install_dir is None else Path(skill_install_dir).resolve(strict=True)
                else:
                    raise ValueError("Источник скилла не подтверждён")
                file = (base / rel).resolve(strict=True)
                if not file.is_file() or not file.is_relative_to(base):
                    raise ValueError("Скилл выходит за выбранный источник")
                if skill.get("base") == "install" and base == runtime_root:
                    canonical = selected["resources"].get("skills", {}).get(name)
                    if not canonical or Path(canonical).resolve(strict=True) != file:
                        raise ValueError("Скилл не принадлежит выбранной поставке")
                    # Verify the canonical file through its own manifest entry, not by name alone.
                    manifest = _runtime_manifest(selected)
                    entries = [entry for entry in manifest.get("files", []) if entry.get("source") == f"skills/{name}/SKILL.md"
                               and entry.get("projection") is not True and Path(entry["path"]).resolve(strict=True) == file]
                    if len(entries) != 1 or entries[0].get("sha256") != hashlib.sha256(file.read_bytes()).hexdigest():
                        raise ValueError("Скилл выбранной поставки повреждён")
                payload["text"] = file.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeError, ValueError, KeyError, TypeError):
                payload["error"] = "Тело скилла выбранного источника недоступно; другая установка не подставляется."
            result["skill_bodies"][body_id] = payload
    return result


def no_help_snapshot(reason: str) -> dict:
    """Снимок «расчёта нет»: поля те же, что у `step_help.compute`, причина в `error`, времени снятия нет."""
    return {"contract": CONTRACT, "taken_at": None, "versions": {"openspec": None, "symphysis": None}, "change": None,
            "changes": None, "error": reason, "current_step": None, "current_text": None, "turn": None,
            "next_by_status": None, "forks": None, "tasks": None, "steps": [], "rebuild": None}


def render_html(journal: dict, template: Path, attacks: list[dict] | None = None, journal_sha256: str | None = None,
                scheme: dict | None = None, help_snapshot: dict | None = None, links: dict | None = None, *,
                resource_context: dict | None = None, skill_install_dir: Path | str | None = None) -> str:
    """Шаблон просмотрщика с журналом вместо `__JOURNAL_JSON__`, списком атак вместо `__ATTACK_JSON__`, схемой вместо
    `__SCHEME_JSON__`, справкой вместо `__HELP_JSON__` и картой ссылок на файлы вместо `__LINKS_JSON__`; все пять меток обязательны. Улики берутся такими, какие в журнале
    (`check --write` или сверка в памяти). Дата сборки `generated` — из журнала, если она
    там есть; своей даты рендер не ставит, и два рендера одного журнала совпадают: снимок справки и его время снятия
    добавляет CLI, из памяти на метку встаёт снимок «расчёта нет» (F-46).

    `attacks` — результаты `parse_attack_md` как есть (режим «атака» просмотрщика); без них
    на место метки встаёт `[]`. `journal_sha256` — SHA-256 файла журнала по байтам, его считает
    CLI: в payload он ключ `sha256`, по нему просмотрщик сверяет хеш цели из frontmatter атаки
    с журналом; ключа нет, если хеш не подан — рендер из памяти файла не знает. `notes[]`
    журнала отдаются режиму «проверка»; остальной payload прежний. Метки подставляются за один
    проход, чтобы текст журнала, похожий на метку, не был подставлен второй раз."""
    html = Path(template).read_text(encoding="utf-8")
    marks = (PLACEHOLDER, PLACEHOLDER_ATTACK, PLACEHOLDER_SCHEME, PLACEHOLDER_HELP, PLACEHOLDER_LINKS)
    for mark in marks:
        if mark not in html:
            raise ValueError(f"в шаблоне нет метки {mark}")
    selected = _execution_context() if resource_context is None else resource_context
    diagram = {key: copy.deepcopy(value) for key, value in (scheme or NO_SCHEME).items() if key in NO_SCHEME}
    # The executable field cannot be supplied by a journal, a snapshot or an arbitrary scheme dict.
    if selected and selected["scope"] == "global":
        diagram["mermaid"] = None
        diagram["mermaidData"] = _global_mermaid(selected)
    help_snapshot = embed_help_resources(help_snapshot or no_help_snapshot("Справка на этой странице не считалась."), selected, skill_install_dir)
    filled = {PLACEHOLDER: _embed(_viewer_payload(journal, journal_sha256)), PLACEHOLDER_ATTACK: _embed(attacks or []),
              PLACEHOLDER_SCHEME: _embed(diagram),
              PLACEHOLDER_HELP: _embed(help_snapshot),
              PLACEHOLDER_LINKS: _embed(links or {"root": None, "files": {}})}
    return "".join(filled.get(part, part) for part in re.split("(" + "|".join(marks) + ")", html))
