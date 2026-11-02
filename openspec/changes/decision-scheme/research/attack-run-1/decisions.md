---
status: gaps_found
target: decisions.json
target_sha256: 32bd168e859d79db609a139e3a85ba4e3b96af502f19478ebf522ef059b1698c
---

# Атака журнала решений

<!-- status: gaps_found | passed. target_sha256 — SHA-256 decisions.json после `check --write`, на момент атаки: правка журнала после атаки обесценивает вердикт. -->
<!-- Проход 1, 2026-11-01: файла атаки не было. `check --write`: улик сверено 211 из 211, поэтому строк о найденности цитат нет; смысл цитат и утверждения записей сверялись чтением. Раздел — запись и поле; поля без содержимого раздела не дают. Номера строк `decisions.json:NNNN` — по файлу после `check --write`. Все 26 решений сверены со строками `answers/`. -->

| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |
| --- | --- | --- | --- | --- | --- | --- |
| «Пути улик — от корня проекта; префикс `vscode/`» (`decisions.json:4`) | intro | claim-extraction | названный корень улик есть в файле корней | справка | есть: `.symphysis/tools/journal-roots.json:1` «"vscode/": "X:/symphysis-vscode"» | — |
| чисто | F-01, question | coverage | — | справка | есть | — |
| чисто | F-01, evidence | coverage | — | справка | есть | — |
| чисто | F-02, question | coverage | — | справка | есть | — |
| чисто | F-02, evidence | coverage | — | справка | есть | — |
| чисто | F-03, question | coverage | — | справка | есть | — |
| чисто | F-03, evidence | coverage | — | справка | есть | — |
| чисто | F-04, question | coverage | — | справка | есть | — |
| чисто | F-04, evidence | coverage | — | справка | есть | — |
| чисто | F-05, question | coverage | — | справка | есть | — |
| чисто | F-05, evidence | coverage | — | справка | есть | — |
| чисто | F-06, question | coverage | — | справка | есть | — |
| чисто | F-06, evidence | coverage | — | справка | есть | — |
| чисто | F-07, question | coverage | — | справка | есть | — |
| чисто | F-07, evidence | coverage | — | справка | есть | — |
| чисто | F-08, question | coverage | — | справка | есть | — |
| чисто | F-08, evidence | coverage | — | справка | есть | — |
| чисто | F-09, question | coverage | — | справка | есть | — |
| чисто | F-09, evidence | coverage | — | справка | есть | — |
| чисто | F-10, question | coverage | — | справка | есть | — |
| чисто | F-10, evidence | coverage | — | справка | есть | — |
| чисто | F-11, question | coverage | — | справка | есть | — |
| чисто | F-11, evidence | coverage | — | справка | есть | — |
| чисто | F-12, question | coverage | — | справка | есть | — |
| чисто | F-12, evidence | coverage | — | справка | есть | — |
| чисто | F-12, consequences | coverage | — | справка | есть | — |
| «поле `nodes` у записи запрещено схемой журнала» (`decisions.json:358`) | F-13, question | claim-authority | запрет стоит на объекте записи, а не только на корне файла | справка | есть: `docs/journal.schema.json:134` «"additionalProperties": false,» внутри `record` с `:129`; цитата улики встречается в файле 12 раз, `check` указал первую, `:7`, это корень | — |
| чисто | F-13, evidence | coverage | — | справка | есть | — |
| чисто | F-13, consequences | coverage | — | справка | есть | — |
| чисто | F-14, question | coverage | — | справка | есть | — |
| чисто | F-14, evidence | coverage | — | справка | есть | — |
| чисто | F-14, consequences | coverage | — | справка | есть | — |
| чисто | F-15, question | coverage | — | справка | есть | — |
| чисто | F-15, evidence | coverage | — | справка | есть | — |
| чисто | F-15, consequences | coverage | — | справка | есть | — |
| «номер контракта, его проверка и ещё пять работ» (`decisions.json:484`) | F-16, question | claim-authority | счёт работ равен таблице контракта | справка | есть: чтением `docs/repo-contract.md:112-118`, семь строк таблицы «Ещё не сделано» | — |
| чисто | F-16, evidence | coverage | — | справка | есть | — |
| чисто | F-16, consequences | coverage | — | справка | есть | — |
| чисто | F-17, question | coverage | — | справка | есть | — |
| чисто | F-17, evidence | coverage | — | справка | есть | — |
| чисто | F-17, consequences | coverage | — | справка | есть | — |
| чисто | F-18, question | coverage | — | справка | есть | — |
| чисто | F-18, evidence | coverage | — | справка | есть | — |
| чисто | F-18, consequences | coverage | — | справка | есть | — |
| чисто | F-19, question | coverage | — | справка | есть | — |
| чисто | F-19, options | coverage | — | справка | есть | — |
| чисто | F-19, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-19, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:2` «- F-19: A — (без слова)» | — |
| чисто | F-19, reversibility | coverage | — | справка | есть | — |
| чисто | F-19, consequences | coverage | — | справка | есть | — |
| чисто | F-20, question | coverage | — | справка | есть | — |
| чисто | F-20, options | coverage | — | справка | есть | — |
| «контрактный тест без починки дефекта шаблона сразу покраснеет» (`decisions.json:786`) | F-20, recommendation | claim-authority | сила довода равна силе улики | предупреждение (выбор A от этого довода не зависит, теста ещё нет) | нет: `docs/repo-contract.md:115` «по-видимому, покраснеет»; `:114` тест ещё не сделан | правка записи |
| решение A, без слова | F-20, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:3` «- F-20: A — (без слова)» | — |
| чисто | F-20, reversibility | coverage | — | справка | есть | — |
| чисто | F-20, consequences | coverage | — | справка | есть | — |
| чисто | F-21, question | coverage | — | справка | есть | — |
| чисто | F-21, options | coverage | — | справка | есть | — |
| чисто | F-21, recommendation | coverage | — | справка | есть | — |
| решение C со словом | F-21, decision | context-compliance | слово по смыслу за выбранный вариант | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:5` «- F-21: C — «Оставим текст, лучше он, чем ничего.»» | — |
| чисто | F-21, reversibility | coverage | — | справка | есть | — |
| «панель исчезает у всех журналов, страница становится шире» (`decisions.json:897`) | F-21, consequences | context-compliance | следствие решения не противоречит более позднему решению | блокер | нет: F-54.E `decisions.json:3528` «Панель схемы включается и выключается поверх любого режима», «карточки видны рядом с рисунком»; строка `notes[]` `decisions.json:3639` приводит к решениям F-39 и F-54, F-21 не назван | правка записи |
| чисто | F-21, evidence | coverage | — | справка | есть | — |
| «Внутри страницы: 451–457 мс» (`decisions.json:893`) | F-21, parking | claim-authority | диапазон покрывает все измерения | предупреждение (выброс у невыбранного способа, выбор не меняет) | нет: `openspec/changes/decision-scheme/research/F-21-probe/probe.log:25` «"ms":1004» — один из трёх замеров; `openspec/changes/decision-scheme/research/F-21.md:36` его называет, запись нет | правка записи |
| чисто | F-22, question | coverage | — | справка | есть | — |
| чисто | F-22, options | coverage | — | справка | есть | — |
| чисто | F-22, recommendation | coverage | — | справка | есть | — |
| решение A со словом | F-22, decision | context-compliance | слово по смыслу за выбранный вариант | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:6` «Поэтому по слову человека.» | — |
| чисто | F-22, reversibility | coverage | — | справка | есть | — |
| чисто | F-22, consequences | coverage | — | справка | есть | — |
| чисто | F-23, question | coverage | — | справка | есть | — |
| чисто | F-23, options | coverage | — | справка | есть | — |
| чисто | F-23, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-23, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:7` «- F-23: A — (без слова)» | — |
| чисто | F-23, reversibility | coverage | — | справка | есть | — |
| «При B растёт грамматика `apply`, это контракт ядра с плагином…» (`decisions.json:1064`) при решении A | F-23, consequences | context-compliance | следствия записи идут из выбранного варианта | предупреждение (отвергнутый вариант назван явно, план в заблуждение не введёт) | нет: всё поле про B, следствий выбранного A в нём нет | правка записи |
| чисто | F-24, question | coverage | — | справка | есть | — |
| вариант B: «Да, сигналом, не стопом, как в прежней редакции дизайна» (`decisions.json:1103`) | F-24, options | claim-authority | «уже было» у варианта подтверждается файлом | предупреждение (ложный довод у отвергнутого варианта, выбранный A с дизайном совпадает) | нет: цитата улики `vscode/docs/design-part1-viewer.md:376` — про вкладку расширения, а `:594-595` «расширение показывает сигнал, `check` его не ловит» | правка записи |
| чисто | F-24, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-24, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:8` «- F-24: A — (без слова)» | — |
| «Сверку можно добавить позже сигналом в `tools/journal_cli.py`» (`decisions.json:1130`) | F-24, reversibility | claim-authority | путь отмены исполним на условиях ядра | предупреждение (уровень «обратимо» держится и без этой сверки) | нет: `vscode/docs/design-part1-viewer.md:595` «синтаксис mermaid понимает только JS»; `:235` «Р19. Ядро без внешних пакетов» | правка записи |
| «заменяется подсказкой «узел не найден» побочным цветом» (`decisions.json:1135`) | F-24, consequences | context-compliance | следствие идёт из выбранного варианта | предупреждение (цвет настраиваемый, цели не мешает) | нет: в F-24.A и F-06 цвета нет; `vscode/docs/design-part1-viewer.md:301-302` ставит «ссылка на несуществующий узел» в выделяющийся уровень | правка записи |
| чисто | F-25, question | coverage | — | справка | есть | — |
| чисто | F-25, options | coverage | — | справка | есть | — |
| «Ядру незачем знать о схеме» (`decisions.json:1182`) | F-25, recommendation | context-compliance | довод не опровергнут более поздним решением | предупреждение (выбор источника для вкладки от этого не меняется; поле на стыке линзы) | нет: F-21.C и F-39.A велят `render-html` подставлять текст `scheme.md`, `decisions.json:2208` «текст схемы своей меткой шаблона» | правка записи |
| решение A, без слова | F-25, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:9` «- F-25: A — (без слова)» | — |
| чисто | F-25, reversibility | coverage | — | справка | есть | — |
| чисто | F-25, consequences | coverage | — | справка | есть | — |
| парковка закрыта решением F-42.A | F-25, parking | claim-extraction | названная запись есть и решена так, как сказано | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-2.md:5` «- F-42: A — (без слова)» | — |
| чисто | F-26, question | coverage | — | справка | есть | — |
| чисто | F-26, options | coverage | — | справка | есть | — |
| чисто | F-26, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-26, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:10` «- F-26: A — (без слова)» | — |
| чисто | F-26, reversibility | coverage | — | справка | есть | — |
| чисто | F-26, consequences | coverage | — | справка | есть | — |
| чисто | F-26, parking | coverage | — | справка | есть | — |
| чисто | F-27, question | coverage | — | справка | есть | — |
| чисто | F-27, options | coverage | — | справка | есть | — |
| чисто | F-27, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-27, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:11` «- F-27: A — (без слова)» | — |
| «состояние показа в `workspaceState`» (`decisions.json:1356`) | F-27, reversibility | claim-authority | «уже есть» подтверждается кодом | справка | есть: `vscode/src/host/viewerPanel.ts:120` «workspaceState.get» | — |
| чисто | F-27, consequences | coverage | — | справка | есть | — |
| чисто | F-28, question | coverage | — | справка | есть | — |
| вариант A: «плашка с ошибкой mermaid и номером строки» (`decisions.json:1378`) | F-28, options | claim-authority | обещанный номер строки верен на измеренных случаях | предупреждение (прежний рисунок и плашка работают, неверен только номер в части ошибок) | нет: `openspec/changes/decision-scheme/research/F-21-probe/probe.log:56` незакрытая скобка на строке 2 даёт «Parse error on line 8:»; `openspec/changes/decision-scheme/research/F-21.md:82` «F-28 обещает номер строки.»; `grep -c first_line decisions.json` — 0, вопрос отчёта в журнал не перенесён | правка записи |
| чисто | F-28, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-28, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:12` «- F-28: A — (без слова)» | — |
| чисто | F-28, reversibility | coverage | — | справка | есть | — |
| чисто | F-28, consequences | coverage | — | справка | есть | — |
| чисто | F-29, question | coverage | — | справка | есть | — |
| вариант A: «кнопки «−», «+», «вписать», перетаскивание зажатой мышью без переключателя» (`decisions.json:1446`) | F-29, options | context-compliance | выбранный вариант, отступающий от факта постановки, несёт `deviation` | предупреждение (критерий читается двояко, человек выбрал A, видя рядом вариант B с кнопкой) | нет: F-04 `openspec/changes/decision-scheme/intent.md:48` «кнопки переключения масштаба и перетаскивания схемы»; кнопки перетаскивания у A нет, поля `deviation` нет, у D такая пометка стоит | вопрос человеку |
| «Задача на десятки строк» (`decisions.json:1509`) | F-29, recommendation | claim-authority | число в доводе измерено | предупреждение | по спеке не выводится: вкладки ещё нет, `vscode/docs/design-part1-viewer.md:559` даёт всей вкладке «~400», долю масштаба не называет | вопрос человеку |
| решение A, без слова | F-29, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:13` «- F-29: A — (без слова)» | — |
| чисто | F-29, reversibility | coverage | — | справка | есть | — |
| чисто | F-29, consequences | coverage | — | справка | есть | — |
| чисто | F-30, question | coverage | — | справка | есть | — |
| вариант B: хеш в версии манифеста, «видно в окне расширений» (`decisions.json:1560`) | F-30, options | claim-authority | упаковщик принимает такую версию | справка | есть: `vscode/node_modules/@vscode/vsce/out/validation.js:68` «if (!semver.valid(version))»: суффикс проходит; запрет `vscode/node_modules/@vscode/vsce/out/publish.js:268` только для публикации, а `vscode/package.json:7` «"private": true». Показ в окне расширений чтением не проверить | — |
| чисто | F-30, recommendation | coverage | — | справка | есть | — |
| решение B, без слова | F-30, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:14` «- F-30: B — (без слова)» | — |
| чисто | F-30, reversibility | coverage | — | справка | есть | — |
| чисто | F-30, consequences | coverage | — | справка | есть | — |
| чисто | F-31, question | coverage | — | справка | есть | — |
| вариант A: «как при старом ядре… «Внести» закрыта» (`decisions.json:1628`) | F-31, options | claim-authority | «уже есть» подтверждается кодом | справка | есть: `vscode/src/webview/App.tsx:258` «view.failure ?»: любой отказ ядра закрывает кнопку; `:312` «Ниже — журнал, каким он был до этого.» | — |
| чисто | F-31, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-31, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:15` «- F-31: A — (без слова)» | — |
| чисто | F-31, reversibility | coverage | — | справка | есть | — |
| чисто | F-31, consequences | coverage | — | справка | есть | — |
| чисто | F-32, question | coverage | — | справка | есть | — |
| чисто | F-32, options | coverage | — | справка | есть | — |
| чисто | F-32, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-32, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01.md:16` «- F-32: A — (без слова)» | — |
| чисто | F-32, reversibility | coverage | — | справка | есть | — |
| чисто | F-32, consequences | coverage | — | справка | есть | — |
| «Страница рисует `scheme.md` из `file://` при трёх способах доставки mermaid» (`decisions.json:1763`) | F-33, question | claim-authority | факт называет условия замера | предупреждение (наблюдение верно для Chrome, при переносе потеряна граница) | нет: `openspec/changes/decision-scheme/research/F-21.md:86` «Проверено только в Chrome. Edge и Firefox не проверял.»; `grep -c Chrome decisions.json` — 0 | правка записи |
| чисто | F-33, evidence | coverage | — | справка | есть | — |
| чисто | F-33, consequences | coverage | — | справка | есть | — |
| чисто | F-34, question | coverage | — | справка | есть | — |
| чисто | F-34, evidence | coverage | — | справка | есть | — |
| чисто | F-34, consequences | coverage | — | справка | есть | — |
| чисто | F-35, question | coverage | — | справка | есть | — |
| чисто | F-35, evidence | coverage | — | справка | есть | — |
| «нужна начальная прокрутка к верхнему узлу, это уходит в дизайн» (`decisions.json:1861`) | F-35, consequences | context-compliance | в следствиях факта нет конструкции без развилки | предупреждение (дизайна ещё нет, опоры на этот факт пока нет) | нет: предписание в факте, развилки о прокрутке нет; `openspec/changes/decision-scheme/research/F-21.md:81` «Проверял только в колонке страницы, во вкладке плагина не проверял.» | правка записи |
| «вдвое легче полной» (`decisions.json:1875`) | F-36, question | claim-authority | число в записи равно измерению | справка | есть: `openspec/changes/decision-scheme/research/F-21-probe/probe.log:17-18` 5494801 и 2811424 байт, доля 0,51 | — |
| чисто | F-36, evidence | coverage | — | справка | есть | — |
| чисто | F-36, consequences | coverage | — | справка | есть | — |
| чисто | F-37, question | coverage | — | справка | есть | — |
| чисто | F-37, evidence | coverage | — | справка | есть | — |
| чисто | F-37, consequences | coverage | — | справка | есть | — |
| «Потолок пришёл из текста выбранного варианта B, в слове его нет» (`decisions.json:2001`) | F-38, question | claim-authority | «уже есть» подтверждается файлом | справка | есть: `docs/plan-implementation.journal.md:173` «кругов не больше двух» в варианте, `:181` в слове потолка нет; `openspec/changes/symphysis-schema/design.md:354` «какое первее? — открыта» | — |
| чисто | F-38, evidence | coverage | — | справка | есть | — |
| чисто | F-38, consequences | coverage | — | справка | есть | — |
| чисто | F-39, question | coverage | — | справка | есть | — |
| «страница остаётся 143 КБ» (`decisions.json:2082`) | F-39, options | claim-authority | число в записи равно измерению | предупреждение (снимок на 14 решениях: страница растёт с журналом, а не от mermaid, довод выбора не меняется) | нет: `wc -c decisions.html` — 223275 байт; `openspec/changes/decision-scheme/research/F-21-probe/probe.log:5` «base-text.html                142693» | правка записи |
| чисто | F-39, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-39, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-2.md:2` «- F-39: A — (без слова)» | — |
| «где он живёт, ещё не решено» (`decisions.json:2203`) | F-39, reversibility | context-compliance | решённое не описано как открытое | предупреждение (устарела одна фраза, решение F-53 стоит отдельной записью) | нет: F-53 решён B, файл вне git, `decisions.json:3405` | правка записи |
| «Кроме D: CSP в `<meta>` страницы…» (`decisions.json:2208`): следствия не называют прежние тексты, которые выбор отменяет | F-39, consequences | context-compliance | следствие решения называет прежние решения и требования, которые оно меняет | предупреждение (решение человека по его же парковке, не хватает перечня правок; поле на стыке линзы) | нет: `vscode/docs/design-part1-viewer.md:219` «Ядро symphysis от mermaid не зависит.»; `openspec/specs/decision-viewer/spec.md:9` «в один файл»; `skills/symphysis-viewer/SKILL.md:21` «HTML-страница из одного файла» | правка записи |
| чисто | F-40, question | coverage | — | справка | есть | — |
| вариант B: «200–225 мс до рисунка против 374–402» (`decisions.json:2245`) | F-40, options | claim-authority | диапазон покрывает все измерения | предупреждение (выброс говорит за выбранный A, решение не меняется) | нет: `openspec/changes/decision-scheme/research/F-21-probe/probe.log:41` «"ms":1292» — один из трёх замеров; `openspec/changes/decision-scheme/research/F-21.md:56` его называет, запись нет | правка записи |
| «Разница около 0,8 МБ в сжатом виде» (`decisions.json:2291`) | F-40, recommendation | claim-authority | число в записи равно измерению | справка | есть: `openspec/changes/decision-scheme/research/F-21-probe/probe.log:17-18` gzip 1570966 и 746681, разность 824285 байт | — |
| решение A, без слова | F-40, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-2.md:3` «- F-40: A — (без слова)» | — |
| чисто | F-40, reversibility | coverage | — | справка | есть | — |
| чисто | F-40, consequences | coverage | — | справка | есть | — |
| чисто | F-41, question | coverage | — | справка | есть | — |
| чисто | F-41, options | coverage | — | справка | есть | — |
| чисто | F-41, recommendation | coverage | — | справка | есть | — |
| решение B, без слова | F-41, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-2.md:4` «- F-41: B — (без слова)» | — |
| чисто | F-41, reversibility | coverage | — | справка | есть | — |
| чисто | F-41, consequences | coverage | — | справка | есть | — |
| чисто | F-42, question | coverage | — | справка | есть | — |
| чисто | F-42, options | coverage | — | справка | есть | — |
| чисто | F-42, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-42, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-2.md:5` «- F-42: A — (без слова)» | — |
| чисто | F-42, reversibility | coverage | — | справка | есть | — |
| чисто | F-42, consequences | coverage | — | справка | есть | — |
| чисто | F-43, question | coverage | — | справка | есть | — |
| чисто | F-43, options | coverage | — | справка | есть | — |
| чисто | F-43, recommendation | coverage | — | справка | есть | — |
| решение B, без слова | F-43, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-2.md:6` «- F-43: B — (без слова)» | — |
| чисто | F-43, reversibility | coverage | — | справка | есть | — |
| «Правятся тесты плагина и страницы, где проверяется текст заголовка» (`decisions.json:2586`) при решении B «Оставить как есть» | F-43, consequences | context-compliance | следствия записи идут из выбранного варианта | блокер | нет: следствие взято из отвергнутых A и C, `decisions.json:2581` «Ничего не меняется.»; заголовок есть только в `tools/playground-template.html:164` и `vscode/src/webview/App.tsx:328`, `grep -rln "Замечания к схеме и плану"` по `tests`, `installer`, `vscode/test` — ноль файлов | правка записи |
| чисто | F-44, question | coverage | — | справка | есть | — |
| чисто | F-44, options | coverage | — | справка | есть | — |
| «Это и сказано в слове к F-07» (`decisions.json:2662`) | F-44, recommendation | claim-extraction | `F-NN` без имени журнала указывает на запись этого журнала | предупреждение (F-38 называет журнал `symphysis-schema`, смысл восстановим) | нет: здесь F-07 — факт без слова; слово в `docs/plan-implementation.journal.md:181` | правка записи |
| решение A, без слова | F-44, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-2.md:7` «- F-44: A — (без слова)» | — |
| чисто | F-44, reversibility | coverage | — | справка | есть | — |
| «Правятся §8 и приёмка скилла, требование `brainstorm-interview` и тест на текст» (`decisions.json:2676`) | F-44, consequences | claim-extraction | названный тест существует | предупреждение (тест можно написать заново, цели не мешает) | нет: `grep -rln "третьего круга"` и `N = 2` по `tests` — ноль файлов; `tests/test_skills.py:136` проверяет только строку отказа | правка записи |
| «в трёх последних журналах 0 из 153», «в этом журнале 7 из 20» (`decisions.json:2682`) | F-45, question | claim-authority | снимок назван снимком | предупреждение (числа верны на начало круга 3, разницу внёс сам журнал) | нет: у этого журнала `grep -c '"kind": "развилка"'` — 26, `grep -c '"other":'` — 5; у остальных сходятся: 74 и 6, 54 и 0, 79 и 0 | правка записи |
| чисто | F-45, evidence | coverage | — | справка | есть | — |
| чисто | F-45, consequences | coverage | — | справка | есть | — |
| «антипод — одна строка в описании полей, без шага и без проверки» (`decisions.json:2738`) | F-46, question | claim-authority | «уже есть» подтверждается файлом | справка | есть: `grep -n антипод skills/symphysis-brainstorm/SKILL.md` — строка 198 о коде `check`, описание поля `:156`; `tools/journal_model.py:399-406` сверяет только существование варианта | — |
| чисто | F-46, evidence | coverage | — | справка | есть | — |
| чисто | F-46, consequences | coverage | — | справка | есть | — |
| «база до первого действия 50 216» (`decisions.json:2780`) | F-47, question | claim-authority | число в записи равно улике | предупреждение (расхождение в два токена, выводы не меняет) | нет: `openspec/changes/decision-scheme/research/antipodes-probe/probe.log:42` «запись кеша 50214»; `grep -c 50216 probe.log` — 0 | правка записи |
| чисто | F-47, evidence | coverage | — | справка | есть | — |
| чисто | F-47, consequences | coverage | — | справка | есть | — |
| «Файла настроек ещё нет», «ещё не реализовано» (`decisions.json:2871`) | F-48, question | claim-authority | «ещё нет» подтверждается измерением | справка | есть: `ls symphysis.yaml` — нет файла; `ls openspec/changes/implementation-consequences/` — нет `tasks.md` | — |
| чисто | F-48, evidence | coverage | — | справка | есть | — |
| чисто | F-48, consequences | coverage | — | справка | есть | — |
| чисто | F-49, question | coverage | — | справка | есть | — |
| чисто | F-49, evidence | coverage | — | справка | есть | — |
| чисто | F-49, consequences | coverage | — | справка | есть | — |
| чисто | F-50, question | coverage | — | справка | есть | — |
| чисто | F-50, options | coverage | — | справка | есть | — |
| «Цена по замеру — 30–40 с на журнал из 54 развилок» (`decisions.json:3069`) | F-50, recommendation | claim-authority | число в записи равно измерению с точностью округления | справка | есть: `openspec/changes/decision-scheme/research/antipodes-probe/probe.log:30-35` 29,5–42,1 с | — |
| решение C со словом | F-50, decision | context-compliance | слово по смыслу за выбранный вариант | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:2` «- F-50: C — «Отличное дополнение, что человек может внести свой вариант, и окажется, что он на самом деле антипод.»» | — |
| чисто | F-50, reversibility | coverage | — | справка | есть | — |
| «Проход идёт в том же контексте, не субагентом» (`decisions.json:3083`) | F-50, consequences | context-compliance | конструкция в следствии выбрана словом человека | предупреждение (текст был виден в варианте F-51.B, отдельного выбора не было) | нет: в варианте C `decisions.json:3015` только «Оба прохода: до показа и после выбора.»; `decisions.json:2780` о причине долгого прогона субагента «почему, не выяснено» | вопрос человеку |
| «Правятся шаги 6 и 7 и приёмка скилла `symphysis-brainstorm`» (`decisions.json:3083`) | F-50, consequences | context-compliance | перечень правок покрывает выбранный вариант | предупреждение (перечень неполон, но §8 правится и по F-44) | нет: строка круга, где стоит итог «антиподов N», — шаг 8 `skills/symphysis-brainstorm/SKILL.md:233` и `openspec/specs/brainstorm-interview/spec.md:24` | правка записи |
| чисто | F-51, question | coverage | — | справка | есть | — |
| вариант B: «30–40 с на Sonnet и на glm-5.2 в одном контексте» (`decisions.json:3122`) | F-51, options | claim-authority | условие замера названо верно | предупреждение | по спеке не выводится: расхождение: цель «в одном контексте», улика `openspec/changes/decision-scheme/research/antipodes-probe/probe.log:29` «один и тот же текст, 41 993 символа, без инструментов», отдельный вызов `/api/generate` и `claude -p`. Проход внутри рабочей сессии не мерен | вопрос человеку |
| «По критерию из слова к F-14» (`decisions.json:3210`) | F-51, recommendation | claim-extraction | `F-NN` без имени журнала указывает на запись этого журнала | предупреждение (F-48 цитирует то же слово, смысл восстановим) | нет: здесь F-14 — факт о пробе mermaid; слово в `openspec/changes/implementation-consequences/decisions.md:243` | правка записи |
| решение B, без слова | F-51, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:3` «- F-51: B — (без слова)» | — |
| чисто | F-51, reversibility | coverage | — | справка | есть | — |
| «При A или C строка уходит сессии ядра через человека…» (`decisions.json:3224`) при решении B | F-51, consequences | context-compliance | следствия записи идут из выбранного варианта | предупреждение (отвергнутые варианты названы явно, план в заблуждение не введут) | нет: всё поле про A и C, следствий выбранного B в нём нет | правка записи |
| пары A и C с F-50.D, A с F-50.E | F-51, antipodes | context-compliance | оба антипода не выбраны одновременно | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:2-3` F-50 решён C, F-51 решён B | — |
| чисто | F-52, question | coverage | — | справка | есть | — |
| вариант B: «Если выбрать оба, это становится строкой атаки.» (`decisions.json:3263`) при доводе «ошибка модели станет замком на слове человека» | F-52, options | context-compliance | следствие не возвращает снятый замок | предупреждение (слово человека проходит, держится только шаг proposal до правки записи) | нет: `skills/symphysis-attack/SKILL.md:180` «оба антипода решены» с тяжестью блокер, `:234` `passed` только без блокеров; ошибочная пара модели остановит шаг, а следствия F-52 скилла атаки не называют | вопрос человеку |
| «Sonnet в 2 прогонах из 4», «18 пар внутри одной развилки» (`decisions.json:3303`) | F-52, recommendation | claim-authority | число в записи равно измерению | справка | есть: `openspec/changes/decision-scheme/research/antipodes-probe/probe.log:16` и `:32` два случая, `:36` «из них внутри одной развилки 18» | — |
| решение B, без слова | F-52, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:4` «- F-52: B — (без слова)» | — |
| «`apply` антиподы не сверяет» (`decisions.json:3312`) | F-52, reversibility | claim-authority | «уже есть» подтверждается измерением | справка | есть: `grep -n -i antipod tools/journal_apply.py` — ноль строк | — |
| чисто | F-52, consequences | coverage | — | справка | есть | — |
| пары A и B с F-50.E | F-52, antipodes | context-compliance | оба антипода не выбраны одновременно | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:2` F-50 решён C | — |
| чисто | F-53, question | coverage | — | справка | есть | — |
| чисто | F-53, options | coverage | — | справка | есть | — |
| чисто | F-53, recommendation | coverage | — | справка | есть | — |
| решение B, без слова | F-53, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:5` «- F-53: B — (без слова)» | — |
| «Строка в `installer/package.json` и список `sync-payload.js`» (`decisions.json:3411`) | F-53, reversibility | claim-authority | перечень правок совпадает с кодом инсталлятора | блокер | нет: `installer/lib/install.js:95` пропускает в `.symphysis/tools/` только `journal*.py` и `playground-template.html`; `installer/scripts/sync-payload.js:43-45` копирует файл с тем же относительным путём, из `node_modules` он ляжет не в `tools/`. Без правки этих мест F-39.A молча покажет текст, `decisions.json:2082` «иначе текст» | правка записи |
| чисто | F-53, consequences | coverage | — | справка | есть | — |
| чисто | F-54, question | coverage | — | справка | есть | — |
| чисто | F-54, options | coverage | — | справка | есть | — |
| чисто | F-54, recommendation | coverage | — | справка | есть | — |
| решение E, вариант добавлен человеком, со словом | F-54, decision | context-compliance | слово по смыслу за выбранный вариант | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:6-7` «добавлен вариант E», «люди устанут переключать режимы» | — |
| чисто | F-54, reversibility | coverage | — | справка | есть | — |
| чисто | F-54, consequences | coverage | — | справка | есть | — |
| «В этом изменении не делается.» (`decisions.json:3524`) | F-54, parking | context-compliance | граница объёма стоит на слове человека | предупреждение (возможность вне критериев `intent.md`, цели изменения не мешает) | нет: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:7` «мы еще внедрим всякие разные сценарии» о сроке молчит; парковка адресату «человек» без `finding`, а формат `scheme.md` войдёт в контракт | вопрос человеку |
| чисто | F-55, question | coverage | — | справка | есть | — |
| вариант A: «Шаги выпуска из контракта проходятся как проверка.» (`decisions.json:3543`) | F-55, options | context-compliance | выбранный вариант исполним при своём порядке слияний | предупреждение (критерий F-09 требует только `e2e:vsix`, шаги 1 и 2 сверх него; поле на стыке линзы) | нет: `docs/repo-contract.md:79` «Хеши из `Needs:` достижимы из `main` ядра», `:80` тесты на worktree `main` ядра; про слияние ядра в `main` вариант A молчит, оно названо только в B | вопрос человеку |
| чисто | F-55, recommendation | coverage | — | справка | есть | — |
| решение A, без слова | F-55, decision | context-compliance | решение в журнале равно строке ответа человека | справка | есть: `openspec/changes/decision-scheme/answers/2026-11-01-3.md:8` «- F-55: A — (без слова)» | — |
| чисто | F-55, reversibility | coverage | — | справка | есть | — |
| чисто | F-55, consequences | coverage | — | справка | есть | — |
| итоги кругов: «решений 14, фактов 18», «решений 6, фактов 6», «решений 6, фактов 5» (`decisions.json:3619`, `:3627`, `:3635`) | notes[] | claim-authority | счёт в строке равен записям круга | справка | есть: счётом по `id` журнала: развилки F-19…F-32, F-39…F-44, F-50…F-55; факты F-01…F-18, F-33…F-38, F-45…F-49 | — |
| «антиподов среди 26 решений нет» (`decisions.json:3639`) | notes[] | context-compliance | несовместимые выбранные варианты отмечены парой или приведён текст прежнего решения | предупреждение (F-39 сам делает F-21.C запасным путём, человек выбрал F-39 после F-21) | нет: F-21.C `decisions.json:845` «без рисунка» и F-39.A `decisions.json:2082` «Рисунок, если рядом есть файл mermaid»; текст F-21.C не приведён | правка записи |

Счёт прохода 1: строк 243, блокеров 3, предупреждений 29, из них «по спеке не выводится» 2, справок 211, «не пройдено» 0.

Вердикт: `status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью `блокер` или `предупреждение`; строки `справка` не блокируют.
