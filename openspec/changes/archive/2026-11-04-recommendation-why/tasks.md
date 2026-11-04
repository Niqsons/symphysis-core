# Tasks

## 1. Ядро: показ причины и импорт

- [x] 1.1 Написать тесты по сценариям `decision-journal`: «Есть поле `text`», «Импорт составной рекомендации», «Круговой разбор», «Старый журнал с полем `text`» — проверка: `py -3.13 -m pytest tests/test_journal_render.py tests/test_journal_validator.py -q` падает только на новых тестах про `text`
- [x] 1.2 `_render_recommendation` в `tools/journal_render.py` пишет всегда `вариант — why`; `test_render_writes_recommendation_from_raw_text` переписан под это правило — проверка: тесты «Есть поле `text`», «Поля `text` нет» зелёные
- [x] 1.3 `_parse_recommendation` в `tools/journal_model.py` не пишет `text`; `test_recommendation_keeps_the_raw_line_as_text` переписан — проверка: `tests/test_journal_render.py` зелёный, в том числе `test_render_md_roundtrip`
- [x] 1.4 В `docs/journal.schema.json` описание `text`: только старые журналы, показ и поиск его не читают — проверка: `py -3.13 -m pytest tests/test_journal_schema.py -q`, архивные журналы остаются годными
- [x] 1.5 Убрать запасной показ `|| rec.recommendation.text` в `tools/playground-template.html:848`; браузерный тест по сценарию страницы «Есть поле `text`» — проверка: `py -3.13 -m pytest tests/test_viewer_browser.py -q`
- [x] 1.6 Тест-страховка F-30: ядро не читает `text` рекомендации в `tools/` — проверка: тест зелёный на коде и красный при подставленном чтении, подстановка не остаётся в коммите

## 2. Ядро: скиллы

- [x] 2.1 Тест в `tests/test_skills.py`: ни один скилл не называет `text` у рекомендации, в образцах его нет — проверка: тест падает на нынешних `symphysis-brainstorm`, `symphysis-edge-probe`, `symphysis-consequences`
- [x] 2.2 `skills/symphysis-brainstorm/SKILL.md:178`: `recommendation {option, why}`, `why` описан как причина выбора этого варианта против других — проверка: тест 2.1 по этому файлу зелёный
- [x] 2.3 `skills/symphysis-edge-probe/SKILL.md:274` и образец `skills/symphysis-consequences/SKILL.md:289` без `text` — проверка: тест 2.1 зелёный целиком
- [x] 2.4 `skills/symphysis-attack/SKILL.md`, линза `context-compliance`: находка о `why`, пересказывающем вариант; новой линзы нет — проверка: чтение строки и `py -3.13 -m pytest tests/test_schema.py tests/test_skills.py -q`, закрытый список линз не изменился
- [x] 2.5 Полный прогон ядра — проверка: `py -3.13 -m pytest -q` и `npm test` в `installer/` зелёные; `check_names` по изменённым файлам даёт код 0
- [x] 2.6 По итогу ревью: `skills/symphysis-prohibition-probe/SKILL.md` и `skills/symphysis-consequences/SKILL.md` тоже описывают `why` как причину, требование `brainstorm-interview` говорит обо всех скиллах, которые пишут развилки — проверка: тест 2.1 по четырём скиллам зелёный

## 3. Плагин

- [x] 3.1 Рабочее дерево `X:\symphysis-vscode-recommendation-why`, ветка `feat/recommendation-why` от `main`, зависимости копией через `npm ci` — проверка: `npm run typecheck` зелёный до правок
- [x] 3.2 `src/webview/Card.tsx` показывает `вариант — why`; тест «составная рекомендация пишется строкой как написана» заменён сценарием «Карточка при поле `text`» — проверка: `npm test`
- [x] 3.3 `src/webview/CheckView.tsx` показывает `вариант — why`, новых тестов режима нет (F-31) — проверка: `npm run typecheck`
- [x] 3.4 `src/shared/search.ts` не ищет по `text`; `test/unit/search.test.ts` переписан по сценариям «Слово только в `text`» и «Слово в причине» — проверка: `npm test`
- [x] 3.5 Страховка F-30: убрать `text?` из типа рекомендации в `src/shared/types.ts` — проверка: `npm run typecheck` зелёный на коде и красный при подставленном чтении, подстановка не остаётся в коммите
- [x] 3.6 Прогон плагина на дереве ядра этого изменения — проверка: с `SYMPHYSIS_ROOT=X:\symphysis-recommendation-why` зелёные `npm run typecheck`, `npm test`, `npm run e2e`, без пропусков

## 4. Приёмка

- [x] 4.1 Человек открывает в плагине журнал со старым `text`, например запись F-06 архива `2026-11-02-calibration-fixes`: под вариантами видна причина — проверка: слово человека
- [x] 4.2 Показ подтверждён на этом журнале: у рекомендаций F-19–F-22 в плагине видна причина — проверка: слово человека
