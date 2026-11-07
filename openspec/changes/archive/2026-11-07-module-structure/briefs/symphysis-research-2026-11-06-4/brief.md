---
skill: symphysis-research
artifact: research
change: module-structure
question: F-32
inputs:
  - installer/README.md
  - installer/package.json
  - vscode/README.md
  - vscode/package.json
  - vscode/package.mjs
  - vscode/.vscodeignore
  - vscode/test/
  - vscode/node_modules/@vscode/vsce/
  - https://docs.npmjs.com/cli/v10/configuring-npm/package-json
  - https://code.visualstudio.com/api/working-with-extensions/publishing-extension
report: openspec/changes/module-structure/briefs/symphysis-research-2026-11-06-4/report.md
---

Исполнить шаги 4–8 скилла `symphysis-research` по одной парковке.

Запись: `Как README модуля уживается с README пакета: `installer/README.md` — README пакета npm, корневой README плагина — README `.vsix`?`

Слово человека: `«Как страница пакета npm и вкладка расширения VS Code показывают YAML frontmatter в README — проверить сборкой пакета (`npm pack`, `vsce package`) и кодом показа, не по памяти. Умеет ли `vsce package` брать README не из корня (`--readme-path`) и что тогда читает `test/package-readme.ts`. Где в обоих случаях может жить описание модуля или репозитория, не попадая на страницу пакета. Где читать: `vscode/package.mjs`, `vscode/test/package-readme.ts`, `installer/package.json`.»`

Выяснить:
1. Что `vsce package` делает с README: откуда берёт файл, умеет ли брать его не из корня (`--readme-path` или иное), меняет ли текст (ссылки, frontmatter) — код `vscode/node_modules/@vscode/vsce/` и документация по адресу из области; проба — `vsce ls` или сборка пакета во временный каталог.
2. Как `vscode/package.mjs` зовёт `vsce` и что читает `vscode/test/package-readme.ts` и тесты упаковки (`vscode/test/`): откуда берётся README для проверки, что изменится, если README пакета ляжет по другому пути.
3. Откуда npm берёт README пакета `installer/` и можно ли указать другой файл — документация `package.json` по адресу из области и проба `npm pack --dry-run` в `installer/` (список файлов пакета).
4. Как YAML frontmatter в начале README выглядит на странице пакета npm и во вкладке расширения VS Code — только то, что подтверждается кодом, документацией из области или пробой; показ на сайтах пробой не проверить — тогда «не найдено» с «искал:».

Область: `installer/README.md`, `installer/package.json`, `vscode/README.md`, `vscode/package.json`, `vscode/package.mjs`, `vscode/.vscodeignore`, `vscode/test/`, `vscode/node_modules/@vscode/vsce/`; сеть — только `https://docs.npmjs.com/cli/v10/configuring-npm/package-json` и `https://code.visualstudio.com/api/working-with-extensions/publishing-extension`.

Жанр: `проверка`

Среда: корень проекта — `X:\symphysis-module-structure` (worktree ветки `feat/module-structure`). Установки `.symphysis/` в нём нет: общие файлы скиллов — `X:\symphysis\.symphysis\docs\`, скрипты — `tools/` корня проекта, шаблон `research.md` — поле `template` вывода `openspec instructions research --change module-structure --json` (запускать с `OPENSPEC_TELEMETRY=0`). Пути плагина в находках — с префиксом `vscode/` (каталог `X:\symphysis-vscode`), как в `openspec/changes/module-structure/probes/journal-roots.json`. Проба — только во временном каталоге системы и в `research/F-32-probe/`; рабочие деревья ядра и плагина не меняются, пакет в реестр не публикуется.

Писать: `openspec/changes/module-structure/research/F-32.md`, `openspec/changes/module-structure/research/F-32-probe/`

Не делать: `decisions.json`, `specs/`, код проекта, вопросы человеку, чтение вне области, публикация пакетов.
