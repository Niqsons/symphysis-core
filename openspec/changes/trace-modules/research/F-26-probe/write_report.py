"""Assemble F-26 evidence using current literal source lines and verify citations."""
from pathlib import Path
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CHANGE = ROOT / 'openspec/changes/trace-modules'
PREFIX = 'openspec/changes/trace-modules/research/F-26-probe/'
citations = []

def cite(path, needle, explanation, fragment=None):
    lines = (ROOT / path).read_text(encoding='utf-8-sig').splitlines()
    matches = [(n, line) for n, line in enumerate(lines, 1) if needle in line]
    if not matches or len({line for _, line in matches}) != 1:
        raise ValueError((path, needle, len(matches)))
    number, line = matches[0]
    quote = fragment if fragment is not None else line.strip()
    assert quote in line and '\n' not in quote
    citations.append((path, number, quote))
    return f'- `{path}:{number}` «{quote}»: {explanation}'

groups = []
groups.append(('1. Metadata: расширение хранится в YAML, но не в типизированном результате чтения. Проверены CLI и публичный helper уже собранного форка; новая сборка не делалась.', [
    cite('upstream/openspec/docs/cli.md', '**Keep your own metadata:**', 'документирован верхнеуровневый ключ с префиксом `x-`; продолжение документации ограничивает префикс нижним регистром, непустым именем без пробелов и запрещает расширения внутри `initiative`.'),
    cite('upstream/openspec/src/utils/change-metadata.ts', 'export const EXTENSION_KEY_PATTERN', '`x-symphysis-components` отвечает текущей форме ключа; вложенное содержимое этого расширения OpenSpec не типизирует.'),
    cite('upstream/openspec/src/utils/change-metadata.ts', 'keys back from the raw YAML first', 'writer предназначен для нового файла; при перезаписи требуется вернуть неизвестные ключи из сырого YAML, иначе они теряются.'),
    cite('upstream/openspec/src/utils/change-utils.ts', "throw new Error(`Change '${name}' already exists", '`new` не дописывает metadata в существующий change; новый файл создаёт writer с известными полями.'),
    cite(PREFIX + 'summary.txt', 'new creates only known metadata;', '`new` создал обычный metadata без расширения; после добавления вложенного components повторный new отказал, status, обе формы instructions, strict validation и archive оставили все байты metadata прежними.', fragment='new creates only known metadata; repeated new refuses; status/instructions(json,text)/strict validation/archive preserve exact metadata bytes'),
    cite(PREFIX + 'summary.txt', 'extensionAfterRewrite', 'helper вернул только schema/created/skip_specs, неизвестных предупреждаемых ключей не было; запись прочитанного объекта в том же временном файле удалила расширение.', fragment='extensionAfterRewrite\\\":false'),
]))
groups.append(('2а. Имена и пути: старый разбор описывает проект расширения, а текущий читатель настроек такой карты не принимает. Корни улик разрешают пути, а снимок графа хранит префикс и HEAD, без имени компонента.', [
    cite('docs/analysis/stores-and-context-pack-2026-11-02.md', '**Найдено: личная карта.**', 'в разборе предложен `repos:`; это описание замысла, проверка ниже показывает расхождение с текущим кодом.'),
    cite('settings/symphysis_config.py', 'settings.signals.append(f"{FILE_NAME}: неизвестный ключ {group}")', 'неизвестная группа настроек даёт сигнал, а не регистрацию репозитория; в KEYS есть consequences, edge_probe, drivers, attack.'),
    cite(PREFIX + 'summary.txt', 'repos is not accepted as repository map', 'синтетический repos отклонён `_apply`; полный read_settings в python -I упёрся в отсутствующий PyYAML, поэтому это проверка классификации уже разобранной карты, а не успешного YAML-чтения.', fragment='symphysis.yaml: неизвестный ключ repos'),
    cite('roots/roots.py', '"""Префикс пути улики -> каталог', 'действующая карта относится к префиксам улик и каталогам; личный файл карты не читался.'),
    cite('roots/roots.py', '"""Файл улики по самому длинному подходящему префиксу', 'вложенный путь разрешается по самому длинному префиксу с защитой от выхода за корень; проба с явной обезличенной картой работает без Git.'),
    cite('trace/trace_graph.py', '# Снимок `graph/req-graph.json`: поля графа', 'текущая фиксация происхождения — prefix/commit корней улик; это не объявление модулей или многоуровневый components/repo intake.'),
]))
groups.append(('2б. Store существует в OpenSpec как дом планирования с собственной регистрацией; это отдельная механика от заявленной карты исходных репозиториев.', [
    cite('upstream/openspec/src/core/store/foundation.ts', '  local_path: string;', 'у backend записи store есть локальный путь; рядом определены тип git, необязательные remote/branch и реестр version/stores.'),
    cite('upstream/openspec/docs/agent-contract.md', 'OpenSpec does not route a store', 'контракт прямо ограничивает store: задачи по исходным репозиториям он не маршрутизирует.', fragment='OpenSpec does not route a store\'s tasks to repos, so the declaring project is the current one, not every repo the change touches.'),
    cite(PREFIX + 'summary.txt', 'setup --no-init-git and declared', 'в изолированном global data создан store без Git; `store:` указатель привёл new/status к root.source=declared, .git не появился.', fragment='setup --no-init-git and declared store pointer new/status succeed; no .git exists'),
    cite('installer/lib/install.js', '/** Короткий хеш HEAD клона или null:', 'инсталлятор знает HEAD собственного клона для версии установки; это не снимок исходного repo, названного компонентом.'),
]))
groups.append(('3. Проверка структуры — гейт самого ядра, с привязкой к Git и формату README. Она обнаруживает часть вложенных модулей именно для сообщения о запрещённом размещении.', [
    cite('tests/repository_structure.py', 'out = subprocess.run(["git", "-C", str(self.root), "ls-files", "-z"]', 'обход строится из Git index; не добавленные туда файлы, включая игнорируемые в пробе, не участвуют. Уже отслеживаемый файл не исчезает из index из-за .gitignore; это не общий обход диска.'),
    cite('tests/repository_structure.py', 'return {"name", "kind"} <= keys', 'для вложенного README нужны оба поля frontmatter; одного наличия README недостаточно.'),
    cite('tests/repository_structure.py', 'found = {d for d, m in marks.items()', 'модуль первого уровня берётся по пометке «модуль» в README корня; далее отдельно добавляется константа openspec/schemas/symphysis и вложенные README с frontmatter.'),
    cite('tests/repository_structure.py', '"""1.4: модуль — каталог первого уровня', 'вложенная схема — специальное исключение; любой другой модуль на глубине получает замечание, как и модуль внутри модуля.'),
    cite(PREFIX + 'summary.txt', '"step": "module-detection"', 'на обезличенной структуре найдены top, src/deep/marked и специально зашитая схема; src/deep/marked запрещён по месту. Plain README, ignored и untracked не найдены.', fragment='"found": ["openspec/schemas/symphysis", "src/deep/marked", "top"]'),
    cite(PREFIX + 'summary.txt', 'CalledProcessError from git ls-files;', 'каталог без Git приводит к exit 128, альтернативного режима у Repo нет. Git установлен в среде; отсутствие самого исполняемого Git отдельно не проверялось.', fragment='CalledProcessError from git ls-files; no fallback'),
]))
groups.append(('4а. Текущие места чтения исходников: brainstorm, research и общий workflow propose уже предусматривают разведку по задаче; формального результата «модули есть/нет» в них сейчас нет. Ни один из этих пунктов не назначает будущий момент анализа.', [
    cite('decisions/skills/symphysis-brainstorm/SKILL.md', 'Затем выполни запрос данных: прочитай запрос человека', 'вход — intent и названные человеком материалы; продолжение шага ищет имена/литералы, выход — факты с уликами в журнале.'),
    cite('research/skills/symphysis-research/SKILL.md', '- Область чтения: файлы и каталоги проекта', 'исследование ограничено областью парковки/улик/intent, у водителя inputs brief; выход — отдельный research/F-NN.md, журнал меняет второй круг.'),
    cite('upstream/openspec/src/core/templates/workflows/propose.ts', '- **Inspect the relevant project before drafting**:', 'workflow сначала читает context/rules и соразмерно изучает код, тесты, конфигурацию и документацию вне openspec; следующий пункт допускает отдельный дом планирования. Это текст инструкции, журнал прогона модели не снимался.'),
    cite('openspec/schemas/symphysis/schema.yaml', 'Найденное — путь, строка, дословная цитата', 'результат research задан как найдено/не найдено с цитатами, а не обязательный реестр модулей.'),
]))
groups.append(('4б. Граф сейчас читает только артефакты изменения: структурной оси модулей нет и при наличии README. Отдельного существующего переключателя «модулей нет» исследование не обнаружило.', [
    cite('trace/trace_graph.py', 'READERS = {"decisions": _read_records', 'читатели перечислены для decisions, specs, consequences, security и tasks; README/metadata не являются источником структурных узлов.'),
    cite('trace/trace_graph.py', '#     <вид узла: cap, req, scn, task, rec, sec, branch>', 'текущие виды — capability, requirement, scenario, task, record, security, branch; вида module/component/repository в конфигурации нет.'),
]))

scope = ['roots/roots.py', 'settings/symphysis_config.py', 'installer/lib', 'trace/trace_graph.py', 'step-help/step_help.py', 'research/skills/symphysis-research/SKILL.md', 'decisions/skills/symphysis-brainstorm/SKILL.md', 'openspec/schemas/symphysis/schema.yaml', 'openspec/config.yaml']
searches = [
    ('x-symphysis-components|repos:|git archive|materials/|intake.py', scope),
    ('repository_structure|module_dirs|README\\.md', scope),
    ('module|component|модул|компонент', ['trace/trace_graph.py', 'openspec/config.yaml', 'openspec/schemas/symphysis/schema.yaml']),
]
search_log = []
for pattern, paths in searches:
    done = subprocess.run(['rg', '-n', pattern, *paths], cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace')
    search_log.extend(['command: rg -n ' + json.dumps(pattern, ensure_ascii=False) + ' ' + ' '.join(paths), 'exit: ' + str(done.returncode), done.stdout.rstrip(), done.stderr.rstrip(), ''])
(HERE / 'searches.txt').write_text('\n'.join(search_log), encoding='utf-8')

brief = (CHANGE / 'briefs/symphysis-research-2026-11-09/brief.md').read_text(encoding='utf-8-sig').split('---', 2)[2].strip()
brief = brief.split('\nЖанр:', 1)[0]
body = ['---', 'genre: устройство', 'question: F-26', 'brief: |', *['  ' + line for line in brief.splitlines()], '---', '', '# F-26 · Как текущий форк хранит расширения metadata изменения и как продукт может разрешить объявленные репозитории и модули?', '', '## Найдено', '']
for lead, findings in groups:
    body.extend([lead, '', *findings, ''])

negative = [
    '- не найдено: исполняемый потребитель `x-symphysis-components`, карта `repos:` и снятие исходных репозиториев по `git archive` в проверенных механизмах продукта; старый разбор сам по себе не подтверждает реализацию.\n  искал: `x-symphysis-components|repos:|git archive|materials/|intake.py` в `roots/roots.py`, `settings/symphysis_config.py`, `installer/lib`, `trace/trace_graph.py`, `step-help/step_help.py`, `research/skills/symphysis-research/SKILL.md`, `decisions/skills/symphysis-brainstorm/SKILL.md`, `openspec/schemas/symphysis/schema.yaml`, `openspec/config.yaml`; совпадений нет (след `research/F-26-probe/searches.txt`). Это ограниченное отрицание по области brief, не заявление обо всех файлах машины.',
    '- не найдено: продуктовый вызов `repository_structure`/`module_dirs` или общий обход произвольных README исходных модулей в проверенных точках продукта.\n  искал: `repository_structure|module_dirs|README\\.md` в `roots/roots.py`, `settings/symphysis_config.py`, `installer/lib`, `trace/trace_graph.py`, `step-help/step_help.py`, `research/skills/symphysis-research/SKILL.md`, `decisions/skills/symphysis-brainstorm/SKILL.md`, `openspec/schemas/symphysis/schema.yaml`, `openspec/config.yaml`; совпадений нет. Обход installer/lib относится к копированию payload, а `_walk_references` roots — к значениям журнала, не к каталогам.',
    '- не найдено: обязательный машинный или инструкционный выход «модули есть/нет» и условный режим структурных связей графа.\n  искал: `module|component|модул|компонент` в `trace/trace_graph.py`, `openspec/config.yaml`, `openspec/schemas/symphysis/schema.yaml`; единственное совпадение — комментарий про раскладку исходников ядра, не механизм анализа модулей. Тексты brainstorm/research/propose прочитаны по находкам выше.',
]
questions = [
    'Какой контракт переносит логическое имя объявленного repo в локальный корень исследования: корни улик уже работают, `repos:` из старого разбора текущим читателем не принят? Источники: stores-and-context-pack, settings, roots; конструкция здесь не выбрана.',
    'Кто и каким способом дописывает расширение в существующий metadata, сохраняя сырые неизвестные ключи, если публичный writer их удаляет? Источники: change-metadata.ts и metadata-helper пробы.',
    'Как фиксируется результат анализа README при произвольной глубине и при отсутствии Git, учитывая, что текущий гейт ядра решает другую задачу? Источник: tests/repository_structure.py и module-detection пробы.',
    'Какой вход получает анализатор исходников, если planning root — store и затронуты несколько repo, а OpenSpec сам задачи по repo не маршрутизирует? Источник: agent-contract.md; момент анализа здесь не назначен.',
]
body.extend(['## Не найдено', '', *[line + '\n' for line in negative], '## Проба', '', '- Условия: `python -I -X utf8 openspec/changes/trace-modules/research/F-26-probe/probe.py`. Только свежий временный каталог и собственный research; isolated HOME/USERPROFILE/APPDATA/LOCALAPPDATA/XDG_*; OPENSPEC_TELEMETRY=0, DO_NOT_TRACK=1, CI=true. Исходник и dist общего форка не изменялись, сеть не использовалась, установки и сборки не было.', '- Проверяемый runtime: существующий `upstream/openspec/bin/openspec.js` → dist, версия `1.16.1+symphysis.5`, HEAD `71c41a656f284f87bb32b341f7713841ad63569d`. Хеши metadata source/dist сохранены. Исходник и dist прочитаны, полная эквивалентность всей сборки исходнику не доказывалась.', '- След: `research/F-26-probe/probe.py`, `research/F-26-probe/results.json`, `research/F-26-probe/summary.txt`, `research/F-26-probe/searches.txt`.', '- Первый запуск: код 1 из-за отсутствия PyYAML у python -I при дополнительной проверке синтетического repos; все предыдущие metadata/store/structure проверки успели пройти. След сохранён: `research/F-26-probe/results-first-run.json`, `research/F-26-probe/summary-first-run.txt`. Причина дословно: `symphysis.yaml: нет пакета PyYAML — выполнить: python -m pip install pyyaml`.', '- Повторный запуск: код 0, PASS. При отсутствии PyYAML отдельно записано ограничение и проверен `_apply` на синтетическом словаре; реальный YAML-читатель не выдан за успешный. Структура без Git ожидаемо дала exit 128, CLI new существующего change ожидаемо exit 1.', '- CLI archive проверен на spec-driven с skip_specs: true, заполненными proposal/design/tasks и без spec delta; специфические hooks сторонних схем и fallback копирования между томами не проверялись. Прогона модели нет: описанные места чтения кода — содержимое инструкций, а не доказательство полученного моделью контекста.', '', '## Вопросы, которые открылись', '', *['- ' + question for question in questions], ''])
text = '\n'.join(body)
target = CHANGE / 'research/F-26.md'
if target.exists():
    raise RuntimeError('F-26.md exists; refusing to overwrite')
target.write_text(text, encoding='utf-8')
for path, number, quote in citations:
    assert quote in (ROOT / path).read_text(encoding='utf-8-sig').splitlines()[number - 1]
assert text.count('- не найдено:') == len(negative)
assert text.count('  искал:') == len(negative)
(HERE / 'verification.json').write_text(json.dumps({'citations': len(citations), 'citationsVerified': len(citations), 'notFound': len(negative), 'allNotFoundHaveSearch': True, 'probeExit': 0, 'sourceAndProductEdits': False}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
report = ['# Итог', '', 'жанр: устройство', f'находок {len(citations)}', f'строк «не найдено» {len(negative)}', 'проба да', '', '## Файлы', '', '- `openspec/changes/trace-modules/research/F-26.md`', *['- `openspec/changes/trace-modules/research/F-26-probe/' + name + '`' for name in ['probe.py', 'write_report.py', 'results.json', 'summary.txt', 'searches.txt', 'verification.json', 'results-first-run.json', 'summary-first-run.txt']], '', '## Вопросы человеку', '', *['- ' + q for q in questions], '- Области нет: нет; все inputs существуют.', '', '## Сигналы', '', '- Первый запуск пробы: exit 1; причина — `symphysis.yaml: нет пакета PyYAML — выполнить: python -m pip install pyyaml`. След сохранён. Повторный запуск: exit 0, с явно ограниченной проверкой `_apply` вместо успешного YAML-чтения.', '- Ожидаемые отрицательные исходы: повторный new exit 1; module detector вне Git exit 128.', '- Строк `[!!]` вызванные пробы не печатали. Критериев приёмки, оставшихся невыполненными в шагах 4–8, нет; все цитаты повторно сверены по строке.', '', '## Не сделано', '', '- Не назначены момент анализа, формат данных модулей и способ разрешения объявленного repo. Журнал, intent, specs и продуктовый код не менялись; коммиты не делались.', '- Не читались личные symphysis.yaml, journal-roots.json и запрещённый список. Нет сети, установки, общей сборки и правок форка.', '- Не проверены новый build, чужие схемы/hooks archive, реальные приватные repo, отсутствие Git executable и поведение модели; это пределы доказанного результата.', '']
(CHANGE / 'briefs/symphysis-research-2026-11-09/report.md').write_text('\n'.join(report), encoding='utf-8')
print(json.dumps({'findings': len(citations), 'notFound': len(negative), 'verified': len(citations), 'probe': True}, ensure_ascii=False))
