# Tasks

Основание — `specs/` (что) и `design.md` (как). Открытые вопросы design,
меняющие задачи: 52 кандидата проб (F-28…F-79) и 5 предположений specs —
без слова человека; задачи ниже их не закрывают и считают допущениями
(`допущение: F-NN открыт`). Группа 1 — слово человека; группы 2–10 стоят
на ней там, где это сказано. Каждая задача — один сеанс.

## 1. Слово человека по открытому

- [ ] 1.1 Показать `decisions.html` (режимы «решения» и «атака»), получить промпт возврата по F-28…F-79 и внести его `apply`; зеркала `outcome` и сценарии Specify — скиллами проб — проверка: `journal.py check` зелёный, у каждого решённого кандидата `outcome`, в `notes[]` строки проб с ненулевыми исходами, `attack/artifacts.md` повторён
- [ ] 1.2 Решить пять предположений specs (детерминизм рендера; цели атаки без `research/`; гейт на пин; `references/` у viewer; `context` при слиянии) — записями журнала с вариантами и словом — проверка: пять записей F-NN со `decision`, слово «предположение» из spec.md снято или заменено ссылкой на F-NN

## 2. Журнал решений (decision-journal)

- [ ] 2.1 Сверить 10 сценариев `specs/decision-journal/spec.md` с `tests/test_journal_check.py`, `test_journal_apply.py`, `test_journal_schema.py`; недостающие дописать — проверка: `py -3.13 -X utf8 -m pytest -q tests/test_journal_check.py tests/test_journal_apply.py tests/test_journal_schema.py` зелёный; у каждого сценария в spec.md комментарий с именем теста
- [ ] 2.2 Тест «два `render-md` подряд совпадают байт в байт» (предположение спеки; допущение: F-41 открыт) — проверка: тест в `tests/test_journal_render.py` зелёный
- [ ] 2.3 Выход за корень в `evidence.path` (`../`, абсолютный хвост; парковка F-80, security.md) — тест, фиксирующий текущее поведение `_resolve`; правка — по решению человека — проверка: тест в `tests/test_journal_check.py` с путём `../` и ожидаемым вердиктом

## 3. Граф артефактов (artifact-graph)

- [ ] 3.1 Сверить 4 сценария `specs/artifact-graph/spec.md` с `tests/test_schema.py` — проверка: `py -3.13 -X utf8 -m pytest -q tests/test_schema.py` зелёный, сценарии «Новое изменение» и «Схема проходит валидацию форка» названы в тестах
- [ ] 3.2 Тупик `research` при нуле парковок «материалы» (допущение: F-36 открыт) — тест на `status --json` изменения без файлов `research/` после `decisions.json` без парковок — проверка: тест в `tests/test_schema.py` фиксирует `research: ready` навсегда или решение человека

## 4. Готовность по вердикту (verdict-readiness)

- [ ] 4.1 Сверить 6 сценариев `specs/verdict-readiness/spec.md` с тестами форка (`test/core/artifact-graph`, `test/commands/status`) и `tests/test_schema.py` — проверка: `pnpm --dir upstream/openspec test` без новых красных (8 EPERM symlink известны, `UPSTREAM.md`), `tests/test_schema.py` зелёный
- [ ] 4.2 README установщика: профиль клиента должен включать workflow `continue` (наблюдение прогона, шаг 1; `design.md` Migration Plan) — проверка: `grep -n continue installer/README.md` даёт строку с командой `openspec config`

## 5. Интервью брейншторма (brainstorm-interview)

- [ ] 5.1 Сверить 4 сценария `specs/brainstorm-interview/spec.md` с `tests/test_skills.py` (строки скилла: «брейншторм закончен по решению человека», порции 2–3, `notes[]` круга) — проверка: `py -3.13 -X utf8 -m pytest -q tests/test_skills.py` зелёный
- [ ] 5.2 Порядок правил §8 при N = 2 и D > 0 (допущение: F-40 открыт) — после слова человека правка `skills/symphysis-brainstorm/SKILL.md` и тест на текст — проверка: тест в `tests/test_skills.py`

## 6. Пробы требований (requirement-probes)

- [ ] 6.1 Сверить 4 сценария `specs/requirement-probes/spec.md` с `tests/test_skills.py` и `tests/test_journal_schema.py` (четыре исхода дословно, Dismiss без причины — код 1, канон — парковка ИБ) — проверка: pytest по двум файлам зелёный
- [ ] 6.2 Правило `validate_journal` «`outcome` без `decision` — код 1» (допущение: F-77 открыт, рекомендация A) — после слова человека — проверка: тест в `tests/test_journal_schema.py`

## 7. Атака артефактов (artifact-attack)

- [ ] 7.1 Сверить 5 сценариев `specs/artifact-attack/spec.md` с `tests/test_journal_render.py` (`parse_attack_md`: 7 ячеек, слуг вне списка, хеши) — проверка: pytest зелёный
- [ ] 7.2 `\|` в ячейке таблицы (допущение: F-30 открыт; наблюдение прогона, шаг 4) — тест, фиксирующий текущий отказ парсера (код 2); правка парсера — по решению человека — проверка: тест в `tests/test_journal_render.py`
- [ ] 7.3 Хеш цели и окончания строк (допущение: F-31 открыт) — тест: один `spec.md` с CRLF и с LF даёт разные `sha256`, вердикт устаревает — проверка: тест в `tests/test_journal_render.py` документирует поведение

## 8. Просмотрщик (decision-viewer)

- [ ] 8.1 Сверить 4 сценария `specs/decision-viewer/spec.md` с `tests/test_journal_render.py` (`render-html --attack`: код 0; битый файл: код 2, HTML не пишется) — проверка: pytest зелёный
- [ ] 8.2 Экранирование полей журнала в HTML (парковка F-82, security.md) — тест: слово человека `<script>alert(1)</script>` в `decisions.html` экранировано во всех местах вывода — проверка: тест в `tests/test_journal_render.py`

## 9. Перенос скиллов (skill-transfer)

- [ ] 9.1 Сверить 3 сценария `specs/skill-transfer/spec.md` с `tests/test_skills.py` (`TRANSLATION-NOTES.md` у каждого скилла; `references/*.md` с «Copyright» у скиллов с источником GSD; viewer без `references/` — предположение) — проверка: pytest зелёный
- [ ] 9.2 Цитаты `SKILL.md` с `путь:строка` находятся в `references/` дословно (допущение: F-78 открыт, рекомендация A) — после слова человека — проверка: тест в `tests/test_skills.py` по образцу `check` улик

## 10. Установщик (project-installer)

- [ ] 10.1 Сверить 5 сценариев `specs/project-installer/spec.md` с `installer/test` (слияние конфига, повторная установка, `check` с ванильным openspec, пустая `SYMPHYSIS_OPENSPEC`) — проверка: `cd installer && npm test` зелёный
- [ ] 10.2 Блок `context` при слиянии (предположение спеки, задача 1.2) — до решения строка README «`context` при слиянии не переносится» — проверка: `grep -n context installer/README.md`
- [ ] 10.3 Записать в журнал развилку «`install`/`check` против каталога без `openspec/` и drive-relative `--project`» (наблюдение прогона, шаг 1) с вариантами и рекомендацией — проверка: запись F-NN в `decisions.json`, `check` зелёный, `render-html` собран
