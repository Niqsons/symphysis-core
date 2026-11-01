# Spec Delta

## Purpose
Готовность вердикт-артефакта считает форк OpenSpec по `status` во frontmatter, а не по наличию файла; workflow `continue` при расхождении зовёт атаку; F-02, F-03, F-13, F-20, F-21.

## ADDED Requirements

### Requirement: Вердикт-артефакт готов только со `status: passed`
Форк OpenSpec SHALL считать артефакт, у которого в схеме объявлен `verdict: {frontmatter: status, value: passed}`, сделанным только когда его файл существует и несёт `status: passed`; `openspec status --json` SHALL показывать у такого артефакта `verdict: ok | missing | mismatch`, и зависящие артефакты SHALL оставаться `blocked`, пока вердикт не `ok` (F-02.B, F-13.B).
<!-- проба краёв: форма=text, io, исходы: F-68 открыт, F-69 открыт -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Файл с gaps_found
- **GIVEN** `attack/decisions.md` со `status: gaps_found`
- **WHEN** выполняется `openspec status --change <имя> --json`
- **THEN** `attack-decisions` — `ready` с `verdict: mismatch`, `proposal` — `blocked`, `nextSteps` содержит «has verdict status=gaps_found but passed is required»

#### Scenario: Файл без ключа
- **GIVEN** `attack/decisions.md` без `status` во frontmatter
- **WHEN** выполняется `status --json`
- **THEN** `verdict: missing`, артефакт `ready`, подсказка «exists but has no verdict»

#### Scenario: Вердикт passed
- **GIVEN** `attack/decisions.md` со `status: passed`
- **WHEN** выполняется `status --json`
- **THEN** `attack-decisions` — `done` с `verdict: ok`, `proposal` — `ready`

### Requirement: `continue` при расхождении вердикта не переписывает файл
Сгенерированный форком workflow `continue` (скилл и команда) SHALL при первом `ready`-артефакте с `verdict: mismatch` или `missing` при существующем файле не переписывать файл, а получить его instructions и выполнить их для вердикта, после чего перечитать `status`; это SHALL считаться единственным артефактом вызова (F-03.C).
<!-- проба краёв: форма=stateful, исходы: F-70 открыт -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Текст workflow несёт шаг вердикта
- **GIVEN** проект после `openspec init --tools claude` форком с workflow `continue` в профиле
- **WHEN** читается `.claude/skills/openspec-continue-change/SKILL.md`
- **THEN** в нём есть абзац с `verdict: "mismatch"`, «do NOT rewrite the file» и «STOP after it», тот же, что `VERDICT_CHECK` в `continue-change.ts`

### Requirement: Форк пинует upstream и разбирает выпуски до втягивания
Форк SHALL нести в `UPSTREAM.md` коммит и версию базы upstream, таблицу правок с коммитами и таблицу выпусков upstream с решением «втягивать или нет»; `openspec --version` SHALL отличать форк от ванильного пакета строкой `1.15.0-symphysis.1` (F-03.C следствия, F-21).
<!-- проба краёв: форма=text, исходы: F-71 открыт, F-72 открыт -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Версия форка
- **GIVEN** собранный `dist/` форка
- **WHEN** выполняется `node upstream/openspec/bin/openspec.js --version`
- **THEN** stdout — `1.15.0-symphysis.1`

#### Scenario: Новый выпуск upstream
- **GIVEN** upstream выпустил версию новее базы форка
- **WHEN** решается, втягивать ли её
- **THEN** в `UPSTREAM.md` появляется строка таблицы «Выпуски upstream» с датой разбора и решением до любого слияния — предположение: порядок «разбор до слияния» принят словом человека (F-03), но проверяет его только чтение `UPSTREAM.md`; решить: нужен ли гейт (тест на пин) или достаточно соглашения
