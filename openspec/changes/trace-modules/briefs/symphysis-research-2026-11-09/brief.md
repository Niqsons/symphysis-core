---
skill: symphysis-research
artifact: research
change: trace-modules
question: F-26
inputs:
  - openspec/changes/trace-modules/intent.md
  - openspec/changes/trace-modules/answers/2026-11-09.md
  - docs/analysis/requirements-traceability-graph-of-symphysis.md
  - docs/analysis/stores-and-context-pack-2026-11-02.md
  - upstream/openspec/
  - roots/roots.py
  - settings/symphysis_config.py
  - installer/lib/
  - tests/repository_structure.py
  - trace/trace_graph.py
  - openspec/schemas/symphysis/
  - research/skills/
  - decisions/skills/
  - step-help/
  - openspec/config.yaml
report: openspec/changes/trace-modules/briefs/symphysis-research-2026-11-09/report.md
---

Запись: `Как текущий форк хранит расширения metadata изменения и как продукт может разрешить объявленные репозитории и модули?`
Слово человека: «про форк не знаю. думаю, что нужно определить момент, когда модель анализирует репозиторий, для которого создается change (это может быть и несколько репозиториев, и изменение затрагивает несколько модулей в них), и сообщает -- есть ли модули или нет. Если нет -- то граф таких связей не содержит.»
Парковка: «В research проверить чтением и пробой текущего закреплённого форка: сохранность x-symphysis-components при new/status/instructions/archive и допустимую форму расширения .openspec.yaml. В roots/roots.py, settings/symphysis_config.py, installer/lib/ и tests/repository_structure.py найти действующие источники имён и локальных путей, вложенные модули, игнорируемые каталоги и режим без Git. Сопоставить docs/analysis/stores-and-context-pack-2026-11-02.md с кодом; не предполагать реализованными repos или store-механики из разбора. Личные symphysis.yaml и .symphysis/tools/journal-roots.json не читать. Вернуть находки с путями, цитатами и следом пробы; конструкцию вынести во второй круг.»
Выяснить:
1. Как текущий форк читает и сохраняет неизвестный x-symphysis-components в .openspec.yaml при new, status, instructions и archive? Проверить документацией/исходниками и пробой во временном каталоге; не менять общую сборку форка.
2. Какие реальные механики существуют для имён репозиториев, локальных путей, компонентов, repo/commit и store? Что из старого разбора ещё не реализовано? Личные карты не читать; исследовать только код и обезличенные временные примеры.
3. Как существующая проверка структуры находит модули, включая вложенную схему, какие ограничения у неё зашиты, что зависит от Git? Есть ли в продукте обход произвольных README модулей?
4. Какие текущие шаги instruction/скиллов реально анализируют исходные репозитории и могли бы дать результат «модули есть/нет»? Какие входы и выходы у этих мест? Где граф сейчас остаётся без структурных связей, если модулей нет? Момент анализа и конструкцию не выбирать.
Область: пути inputs выше, от корня worktree. Журнал не нужен: вопрос, выбранное слово и парковка приведены здесь. Дополнительное принятое уточнение F-16: продукт работает на любых репозиториях, модули могут быть в корне, src, modules и на любой глубине, у модуля должен быть README.md; symphysis — пример для догфудинга.

Жанр: устройство
Рабочий корень: `C:/Users/User/.codex/worktrees/990e/symphysis`; команды всегда с явным workdir или git -C. upstream — junction на общий исходник; только чтение, без сборки, установки и правок.
Писать: `openspec/changes/trace-modules/research/F-26.md`, `openspec/changes/trace-modules/research/F-26-probe/`, report по frontmatter. Проба пишет только в research/F-26-probe и временный каталог; не используй общий installer/payload, не вызывай глобальный install.
Не делать: править decisions.json, specs/, intent.md, код проекта и чужие файлы; спрашивать человека; читать вне inputs ради находок; обращаться в сеть; читать symphysis.yaml, .symphysis/tools/journal-roots.json и запрещённый список имён; делать коммиты.
Ты не один в кодовой базе: не отменяй чужие изменения и учитывай текущие файлы. Вторая парковка независимо работает в research/F-27.md и своём каталоге следов.
Применяй `X:/symphysis/.agents/skills/symphysis-research/SKILL.md`, шаги 4–8 и раздел «Водитель». Шаблон — `openspec/schemas/symphysis/templates/research.md`. Операционные инструкции AGENTS/CLAUDE и контекст-пакет читаются по правилам проекта; они не являются областью находок этой парковки.
Каждая находка — существующий путь от корня и дословная цитата с правильной строкой, прочитанная сейчас. Не найдено — с точными шаблонами поиска. След проб сохранить без абсолютных путей пользовательского профиля и без личных карт. Не подменяй поиск проектным решением. В отчёте: жанр, находок N, строк «не найдено» M, проба да/нет; файлы; открывшиеся вопросы; сигналы; не сделано.
