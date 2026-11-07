# Spec Delta

## ADDED Requirements

### Requirement: `check` называет состав устаревшего вердикта
Команда `journal.py check` при файле `attack/decisions.md` рядом с журналом SHALL печатать строки состава по `stale-verdict-scope` с маркером `[..] атака журнала: …`, когда SHA-256 журнала не равен `target_sha256`; при файле `attack/artifacts.md` — `[..] атака артефактов: …` с изменившимися целями. При совпавших хешах строк SHALL NOT быть. Строки — сведения: код выхода SHALL оставаться прежним и с `--strict` (F-19, F-18).

#### Scenario: Записи добавлены после вердикта
- **GIVEN** `attack/decisions.md` со `status: passed` на F-01–F-79, журнал несёт F-01–F-139
- **WHEN** выполняется `journal.py check decisions.json`
- **THEN** stdout несёт `[..] атака журнала: после вердикта добавлено 60 записей: F-80–F-139`, код 0

#### Scenario: Хеш совпал
- **GIVEN** SHA-256 журнала равен `target_sha256`
- **WHEN** выполняется `journal.py check decisions.json`
- **THEN** строк `[..] атака журнала` нет

#### Scenario: Состав не меняет код `--strict`
- **GIVEN** журнал без строк `[!!]`, вердикт атаки устарел
- **WHEN** выполняется `journal.py check --strict decisions.json`
- **THEN** строка `[..] атака журнала` есть, код 0

#### Scenario: Файла атаки нет
- **GIVEN** в каталоге изменения нет `attack/`
- **WHEN** выполняется `journal.py check decisions.json`
- **THEN** строк `[..] атака` нет, остальные проверки прежние

#### Scenario: Файл атаки не разбирается
<!-- F-30 -->
- **GIVEN** `attack/decisions.md` без строки `---`
- **WHEN** выполняется `journal.py check decisions.json`
- **THEN** stdout несёт `[!!] attack/decisions.md: файл атаки не разбирается: <причина>`, остальные проверки идут, код 0, с `--strict` 2

<!-- проба краёв: форма=io, text, stateful, исходы: F-30 Specify -->
<!-- проба запретов: исходы: нет -->
