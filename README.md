# symphysis-core

Компонент «ядро» схемы OpenSpec `symphysis`: схема, скиллы, инструменты журнала
решений и инсталлятор. Репозиторий — `symphysis-core`, выпускается пакетом npm
`@niqsons/symphysis`. Контракт с плагином — [docs/repo-contract.md](docs/repo-contract.md).

## Каталоги первого уровня

- [attack/](attack/) — модуль: шаг атаки
- [cli/](cli/) — модуль: фасад командной строки журнала
- [consequences/](consequences/) — модуль: шаг последствий
- [decisions/](decisions/) — модуль: журнал решений
- [installer/](installer/) — модуль: инсталлятор, пакет npm
- [openspec-run/](openspec-run/) — модуль: запуск форка OpenSpec
- [probes/](probes/) — модуль: пробы краёв и запретов
- [research/](research/) — модуль: шаг исследования
- [roots/](roots/) — модуль: корни улик и поиск цитат
- [settings/](settings/) — модуль: личные настройки `symphysis.yaml`
- [skill-shared/](skill-shared/) — модуль: общие файлы скиллов
- [step-help/](step-help/) — модуль: справка о шаге
- [trace/](trace/) — модуль: граф трассируемости
- [viewer/](viewer/) — модуль: страница просмотра развилок
- [.bugs/](.bugs/) — контур разработки: заметки об ошибках
- [docs/](docs/) — контур разработки: планы, разборы, контракт с плагином
- [openspec/](openspec/) — контур разработки: изменения и мастер-спеки; внутри лежит модуль схемы `openspec/schemas/symphysis/`
- [tests/](tests/) — контур разработки: общие тесты и проверка структуры
- [tools/](tools/) — контур разработки: инструменты разработки, хуки гейта имён, списки допусков
- [vendor/](vendor/) — контур разработки: тарбол форка OpenSpec
