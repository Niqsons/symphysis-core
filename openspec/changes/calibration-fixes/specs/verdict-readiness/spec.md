# Spec Delta

## MODIFIED Requirements

### Requirement: Вердикт-артефакт готов только со `status: passed`
Форк OpenSpec SHALL считать артефакт, у которого в схеме объявлен `verdict: {frontmatter: status, value: passed}`, сделанным только когда его файл существует и несёт `status: passed`; `openspec status --json` SHALL показывать у такого артефакта `verdict: ok | missing | mismatch`, и зависящие артефакты SHALL оставаться `blocked`, пока вердикт не `ok` (F-02.B, F-13.B). Артефакт с признаком `optional: true` в схеме SHALL NOT требоваться для `isPlanningComplete` и SHALL NOT блокировать зависящие от него артефакты, пока его файла нет; при существующем файле SHALL действовать правило вердикта без скидок; гейт вызванной атаки держится, пока существует её файл (F-06.A, F-29.E).
<!-- проба краёв: форма=text, io, stateful, исходы: F-29 Specify -->
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

#### Scenario: Необязательный артефакт без файла
- **GIVEN** схема с `optional: true` у `attack-decisions` и изменение без `attack/decisions.md`
- **WHEN** выполняется `status --json`
- **THEN** `attack-decisions` показан с признаком `optional` и без вердикта, `proposal` — `ready`, `isPlanningComplete` от него не зависит

#### Scenario: Необязательный артефакт с файлом
- **GIVEN** та же схема и `attack/decisions.md` со `status: gaps_found`
- **WHEN** выполняется `status --json`
- **THEN** `verdict: mismatch`, `proposal` — `blocked`: вызванная атака гейтует как обязательная

#### Scenario: Файл вызванной атаки удалён
- **GIVEN** `attack/decisions.md` со `status: gaps_found` удалён из каталога изменения
- **WHEN** выполняется `status --json`
- **THEN** `attack-decisions` снова `optional` без файла, зависимые не `blocked`: удалённый файл читается как «атака не вызывалась»; если файл был закоммичен, его след остаётся в истории git

### Requirement: `continue` при расхождении вердикта не переписывает файл
Сгенерированный форком workflow `continue` (скилл и команда) SHALL при первом `ready`-артефакте с `verdict: mismatch` или `missing` при существующем файле не переписывать файл, а получить его instructions и выполнить их для вердикта, после чего перечитать `status`; это SHALL считаться единственным артефактом вызова (F-03.C). Workflow SHALL принимать имя артефакта вторым аргументом (`/opsx:continue <изменение> attack-artifacts`) и SHALL создавать или повторять именно его, если он `optional` и его зависимости выполнены; имя SHALL сравниваться точно с `id` схемы, иное — отказ с перечнем артефактов без записи файлов; без имени необязательные артефакты SHALL пропускаться (F-06.A, F-30.E, F-31.E).
<!-- проба краёв: форма=stateful, text, исходы: F-30 Specify, F-31 Specify -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Текст workflow несёт шаг вердикта
- **GIVEN** проект после `openspec init --tools claude` форком с workflow `continue` в профиле
- **WHEN** читается `.claude/skills/openspec-continue-change/SKILL.md`
- **THEN** в нём есть абзац с `verdict: "mismatch"`, «do NOT rewrite the file» и «STOP after it», тот же, что `VERDICT_CHECK` в `continue-change.ts`

#### Scenario: Вызов атаки по имени
- **GIVEN** изменение с `tasks` done и `attack-artifacts` (`optional`) без файла
- **WHEN** человек зовёт `/opsx:continue <имя> attack-artifacts`
- **THEN** выполняются instructions `attack-artifacts`, появляется `attack/artifacts.md` с вердиктом; `continue` без имени этот артефакт не создаёт

#### Scenario: Имя артефакта с опечаткой
- **GIVEN** вызов `/opsx:continue <имя> Attack-Artifacts` или `attack_artifacts`
- **WHEN** workflow разбирает аргумент
- **THEN** отказ с перечнем `id` артефактов схемы, ни один файл не записан, «похожий» артефакт не создаётся

#### Scenario: Повтор по имени при действительном вердикте
- **GIVEN** `attack/artifacts.md` со `status: passed`, хеши целей совпадают с текущими
- **WHEN** человек зовёт `/opsx:continue <имя> attack-artifacts`
- **THEN** файл не переписывается, проход идёт только по строкам «не пройдено», человеку сообщается, что вердикт действителен
