---
skill: symphysis-research
artifact: research
change: trace-numbers-signals
question: F-24
inputs:
  - .claude/skills/openspec-sync-specs/SKILL.md
  - .claude/skills/openspec-archive-change/SKILL.md
  - upstream/openspec/src/core/specs-apply.ts
  - upstream/openspec/src/core/archive.ts
  - upstream/openspec/UPSTREAM.md
  - openspec/config.yaml
  - openspec/schemas/symphysis/schema.yaml
  - openspec/specs/
  - docs/GUIDE.md
  - trace/trace_graph.py
  - openspec/changes/archive/2026-11-06-trace-graph/decisions.md
report: openspec/changes/trace-numbers-signals/briefs/symphysis-research-2026-11-07-2/report.md
---

Исполнить шаги 4–8 скилла `symphysis-research` по одной парковке.

Запись: `Как ссылки на записи попадают в мастер-спеку при синхронизации: голыми `(F-NN)`, как сейчас, или в форме якоря?`

Слово человека: `«Как `/opsx:sync` переносит текст требования в мастер: код форка `upstream/openspec/src/core/specs-apply.ts` дословно, с комментариями, или модель по правилу; чем выполняется правило `rules.specs` о следе проб — кодом или моделью (F-147 изменения `trace-graph` говорит, что след в мастер попадал). Где дешевле переписать ссылки — правка форка по перечню `upstream/openspec/UPSTREAM.md` или шаг `trace_graph.py` после синхронизации до архива.»`

Человек выбрал вариант A (для связки находок, не для выбора): при переносе в мастер голые `F-NN` блока требования, включая маркеры `<!-- F-NN -->`, переписываются в форму якоря `<изменение>/F-NN`; дельта пишется по-прежнему; старые голые номера мастера остаются.

Выяснить:
1. Кто переносит текст дельты в мастер: скилл `/opsx:sync` (`.claude/skills/openspec-sync-specs/SKILL.md`) — модель правит мастер по шагам скилла, или CLI форка `openspec archive` (`upstream/openspec/src/core/archive.ts` → `specs-apply.ts`) — код применяет дельты; и что из этого делал проект на деле: коммиты `6c51cb8` «дельты module-structure перенесены в мастер-спеки» и `fd5f8bb` «архивировано trace-graph» (`git show --stat`, `git show` по файлам `openspec/specs/`).
2. Переносится ли текст требования дословно вместе с HTML-комментариями (след проб `<!-- проба … -->`, маркеры `<!-- F-NN -->`): по коду `specs-apply.ts` (`buildUpdatedSpec`, обращение с комментариями около строк 857 и 1313) и по факту — есть ли в `openspec/specs/*/spec.md` комментарии `<!-- проба` и `<!-- F-NN -->`, из каких коммитов они пришли (`git log -S`).
3. Чем выполняется правило `rules.specs` из `openspec/config.yaml` «след проб … в общую спеку при синхронизации не переносится»: кодом форка, шагом скилла sync или archive, или только памятью модели; где правило читается (`openspec instructions … --json`, скилл, схема `openspec/schemas/symphysis/schema.yaml`).
4. Где можно переписать голые `F-NN` блока требования в форму `<изменение>/F-NN` при переносе в мастер: точка в `specs-apply.ts` (цитатой), шаг скилла sync или archive, или подкоманда `trace_graph.py` после синхронизации до архива; какие места кода и документов задевает каждый путь — перечень правок `upstream/openspec/UPSTREAM.md`, `docs/GUIDE.md`, скиллы sync и archive, чтение мастера в `trace/trace_graph.py` (`_master_lines`, F-147). Связка с местом, без выбора.

Область: `.claude/skills/openspec-sync-specs/SKILL.md`, `.claude/skills/openspec-archive-change/SKILL.md`, `upstream/openspec/src/core/specs-apply.ts`, `upstream/openspec/src/core/archive.ts`, `upstream/openspec/UPSTREAM.md`, `openspec/config.yaml`, `openspec/schemas/symphysis/schema.yaml`, `openspec/specs/`, `docs/GUIDE.md`, `trace/trace_graph.py`, `openspec/changes/archive/2026-11-06-trace-graph/decisions.md`; история git файлов `openspec/specs/` (`git log`, `git show`) — в область входит.

Жанр: `устройство`

Среда: корень проекта — `X:\symphysis-trace-numbers-signals` (worktree ветки `feat/trace-numbers-signals`); git — через `git -C X:\symphysis-trace-numbers-signals`. Форк OpenSpec доступен по `upstream/` (junction на основной клон), его не собирать и не менять. Установленные скрипты — `.symphysis/tools/`; Python — `python -X utf8`. Шаблон `research.md` — поле `template` вывода `openspec instructions research --change trace-numbers-signals --json`. Если понадобится проба (например, `openspec archive` на временной копии проекта), она идёт во временном каталоге вне проекта (`%TEMP%`), след — в `research/F-24-probe/`.

Писать: `openspec/changes/trace-numbers-signals/research/F-24.md`, `openspec/changes/trace-numbers-signals/research/F-24-probe/`

Не делать: `decisions.json`, `specs/`, код проекта, форк в `upstream/`, вопросы человеку, чтение вне области, выбор варианта.
