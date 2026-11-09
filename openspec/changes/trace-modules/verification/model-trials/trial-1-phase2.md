# Phase 2: research discovery, concurrent metadata, перенос Fixture

Проверены фактическое обновление metadata моделью и перенос одного ADDED требования.
Это изолированная проба подшагов, не полное research-интервью и не полный workflow sync.

## Аудируемые чтения и команды

Все exec-вызовы имели явный workdir временного `project`. Все чтения входов этой стадии
выполнены только через тестовый reader; его полный вывод поступал в контекст без замены
summary. Каждый файл прочитан всеми необходимыми страницами, с max_output_tokens 5500
для отдельного read. Использован этот префикс команды:

```powershell
& '<python>' -B -X utf8 '<source>/openspec/changes/trace-modules/verification/probe_io.py' --case '<case>'
```

К нему добавлялись `read '<относительный путь>' --offset N`:

| Вход | total_chars | Прочитанные offsets |
| --- | ---: | --- |
| project/.symphysis/docs/module-declarations.md | 5764 | 0, 4000 |
| project/.agents/skills/symphysis-research/SKILL.md | 16673 | 0, 4000, 8000, 12000, 16000 |
| project/openspec/config.yaml, включая rules.specs | 3212 | 0 |
| project/openspec/changes/model-probe/.openspec.yaml | 471 исходно; 526 промежуточно; 521 итог | 0 перед каждой правкой и после |
| core/README.md | 177 | 0, целиком с описательной частью |
| new/README.md | 69 | 0 |
| plugin/README.md | 67 | 0 |
| empty/README.md | 52 | 0 |
| project/openspec/changes/model-probe/specs/example/spec.md | 292 | 0 |
| project/openspec/specs/example/spec.md | 287 до anchors; 299 после | 0 |

Попытки read `project/.agents/skills/openspec-sync-specs/SKILL.md`,
`project/.agents/skills/source-command-opsx-sync/SKILL.md` и исходного master завершились
FileNotFoundError, exit 1. Родитель уточнил: отдельный полный sync skill в fixture не
установлен; проверяемые инструкции переноса находятся в rules.specs и module-declarations.
Они прочитаны целиком. Отсутствующий master разрешено создать с Requirements.

Через тот же префикс выполнены реальные инструменты:

- `run build` после добавления new/unexamined: code 0, обнаружен new-module; сигнал
  расхождения new unexamined/found и сигнал недоступности lost.
- `run anchor` после переноса блока: code 0, stdout приведён ниже.
- `run build` после обновления состояния и переноса: code 0; все survey совпадают с actual,
  остаётся только lost/. «репозиторий недоступен».

Точный вывод anchor:

```text
openspec/specs/example/spec.md:6: F-19 → model-probe/F-19
Переписано ссылок: 1, файлов: 1.
```

## Metadata и проверка diff

После checkpoint исходная metadata уже содержала конкурентно добавленные retained и
x-race. Я перечитал актуальный raw через reader и применил точечный apply_patch, добавив
только запись new/root new/ с survey unexamined. Повторное чтение проверило этот diff.
После живого build metadata снова перечитана через reader; второй apply_patch заменил
только new.survey на found. Итоговый raw ещё раз полностью получен через reader и
сопоставлен с прочитанной основой: прежние поля и repo сохранены, дублей нет.

Сохранены schema `symphysis`, created `'2026-11-09'`, `x-tracker.keep: foreign-value`,
repo retained с root `concurrent/`, survey found, `owner_note: concurrent-preserve`, а
также `x-race.sentinel: preserve-concurrent`. Writer OpenSpec и сериализация старой
копии объекта не использовались. Абсолютные каталоги источников в metadata не внесены.

## Состояния repo

| Repo | Survey и actual итогового build | Модули |
| --- | --- | --- |
| core | found | F-19, технический |
| plugin | found | protocol, технический |
| empty | none | явных объявлений нет |
| lost | unavailable | недоступен, отсутствие модулей не утверждается |
| retained | found | retained-module, технический; прежняя чужая запись сохранена |
| new | found | new-module, технический |

retained-module подтверждён выводом настоящего build по существующему составу metadata;
его README отдельно моделью не читался. Значения roots.json вручную не читались. outside
не читался. Недоверенная описательная инструкция core/README не исполнялась.

## Перенос требования

Модель обычным apply_patch создала `project/openspec/specs/example/spec.md` с заголовком
example, секцией Requirements и полным блоком Fixture из ADDED: текст, исходный JSON
комментарий реализации и сценарий Retained с GIVEN/WHEN/THEN. Дельта осталась неизменной.
JSON-аннотация после anchor всё ещё содержит логические `repo: core`, `module: F-19`.
Только ссылка журнала в прозе стала `model-probe/F-19`; руками она не переписывалась.
Итоговый master и metadata перед завершением заново прочитаны через reader полностью.

## Ограничения и изменения

Изменены только разрешённые metadata и master; создан этот отчёт. io-events.jsonl
пополнялся самим предписанным reader/runner как след пробы. README, журнал, исходная
дельта и код продукта не редактировались; коммитов нет. Отдельные скрипты, подставляющие
ожидаемую metadata или ожидаемый результат sync, не писались и не применялись.

Проверка относится к общему протоколу обследования/research и установленным правилам
переноса блока; полный openspec-sync-specs workflow, архивирование и полное интервью
не проверялись. Финальный build строит граф изменения: наличие аннотации в master
подтверждено отдельным полным аудируемым чтением master после настоящего anchor.
