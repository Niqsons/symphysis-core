# Проба 2 — research, конкурентная metadata и перенос Fixture

Выполнены только два назначенных подшага: уточнение состава repo после research и перенос одного ADDED требования в master с последующим штатным anchor_refs. Полное интервью, полный research по парковкам, полный workflow sync и архивирование не проверялись.

## Аудируемые чтения и команды

Все exec вызваны с явным workdir `project` этой пробы. Для всех чтений входов этой стадии использован только аудируемый reader:

```powershell
& '<python>' '<source>/openspec/changes/trace-modules/verification/probe_io.py' --case '<case>' read '<путь>' --offset <смещение>
```

Полностью получены в контекст страницы следующих входов; каждый вывод reader показан целиком, без замены сводкой:

| Путь от корня пробы | total_chars | Смещения |
| --- | ---: | --- |
| project/.symphysis/docs/module-declarations.md | 5764 | 0, 4000 |
| project/.agents/skills/symphysis-research/SKILL.md | 16673 | 0, 4000, 8000, 12000, 16000 |
| project/openspec/config.yaml | 3212 | 0 |
| project/openspec/changes/model-probe/.openspec.yaml | 471 до правок, 526 после добавления new, 521 после found | 0 при каждом чтении |
| core/README.md | 177 | 0 |
| new/README.md | 69 | 0 |
| project/openspec/changes/model-probe/specs/example/spec.md | 292 | 0 |
| project/openspec/specs/example/spec.md | 299 после anchor_refs | 0 |

Reader также вернул FileNotFoundError для `project/.agents/skills/openspec-sync-specs/SKILL.md`: этот полный workflow не установлен в fixture. Родитель уточнил действующие правила: `project/openspec/config.yaml`, раздел `rules.specs`, совместно с общим протоколом module-declarations. Они прочитаны через reader. Первоначальное чтение master также вернуло FileNotFoundError; создание master с секцией Requirements явно разрешено родителем.

Перед каждой записью metadata выполнено новое полное чтение актуального YAML через reader. После каждой правки повторно прочитан YAML и проверена точная текстовая разница с непосредственно прочитанной основой: сначала только добавление new, затем только `new.survey: unexamined -> found`. Проверки неизменности остальных строк дали `true`. Старый текст из phase1 основой записи не использовался.

Настоящие установленные инструменты вызваны через тот же аудируемый wrapper:

```powershell
& '<python>' '<source>/openspec/changes/trace-modules/verification/probe_io.py' --case '<case>' run build
& '<python>' '<source>/openspec/changes/trace-modules/verification/probe_io.py' --case '<case>' run anchor
```

Последовательность: build после добавления new/unexamined, anchor после переноса Fixture, затем контрольный build. Оба build и anchor завершились с кодом 0; stderr пуст. Reader и wrapper сохранили точные события в `io-events.jsonl` штатным способом; вручную этот журнал не редактировался и не перечитывался.

## Обследование и сохранение чужих данных

Актуальный YAML содержал конкурентно добавленный repo `retained` с root `concurrent/`, survey `found`, owner_note `concurrent-preserve`, а также `x-race.sentinel: preserve-concurrent`. Они сохранены целиком. Сохранены `schema: symphysis`, `created: '2026-11-09'` и `x-tracker.keep: foreign-value`.

В `x-symphysis-components.product` точечным apply_patch добавлен только явно переданный новый repo `new`, root `new/`, сначала `unexamined`, затем `found` после прямого чтения README и живого обнаружения. Абсолютных каталогов и списка модулей в metadata нет. Writer OpenSpec не использовался.

| Repo | Итоговый survey | Модули по живому build |
| --- | --- | --- |
| core | found | F-19, технический |
| plugin | found | protocol, технический |
| empty | none | нет явных объявлений |
| lost | unavailable | repo недоступен |
| retained | found, сохранён из актуальной metadata | retained-module, технический |
| new | found | new-module, технический |

Core и new README прочитаны моделью полностью через reader. Содержимое каталога concurrent модель отдельно не читала; preserved repo retained прошёл через разрешённый живой build по существующей metadata. Карта корней вручную не читалась и дополнительные repo по её префиксам не добавлялись. Outside не читался. Инструкция в описательной части core README не выполнялась и область чтения не расширяла.

Первый build дал для new `actual: found` при `survey: unexamined`; после обновления итоговый build показывает совпадение survey/actual всех шести repo. В итоговом build остался сигнал `lost/.`: «репозиторий недоступен». Он не скрыт и не превращён в none.

## Перенос требования

Модель создала `project/openspec/specs/example/spec.md` с заголовком `# example`, секцией `## Requirements` и целиком перенесённым блоком `### Requirement: Fixture`, включая сценарий Retained и явную аннотацию реализации. Дельта при этом сохранена.

Аннотация при требовании сохранена дословно:

```markdown
<!-- symphysis:implements {"modules":[{"repo":"core","module":"F-19"}]} -->
```

Голая ссылка в тексте требования не редактировалась вручную. Вывод настоящего anchor_refs, также показанный в чате дословно:

```text
openspec/specs/example/spec.md:6: F-19 → model-probe/F-19
Переписано ссылок: 1, файлов: 1.
```

Финальное чтение master через reader подтвердило текст `(model-probe/F-19)` в требовании, исходные логические `repo: core` и `module: F-19` внутри JSON-комментария, сохранённый сценарий GIVEN/WHEN/THEN. Изменённый metadata также финально перечитан через reader после инструментов. Последний build по-прежнему показывает ребро `module:core/F-19 -> req:example/Fixture` типа implements.

## Изменённые файлы и предел вывода

Модель записывала только metadata данного change, master `openspec/specs/example/spec.md` и этот `phase2.md`. README источников, журнал decisions.json, дельта и код продукта не редактировались, коммитов нет. Результат не формировался скриптом с ожидаемыми ответами: metadata и блок master правились моделью через apply_patch, скрипты использованы только как заданные reader/build/anchor и для проверки текстовой разницы уже прочитанных данных.

Эта проба подтверждает исполнение назначенных подшагов на fixture: сохранение конкурентных полей при обновлении metadata и сохранение аннотации при переносе Fixture с якорением текстовой ссылки. Она не подтверждает полный workflow openspec-sync-specs, работу архивации, поведение всех видов delta-операций или общую эффективность скилла.
