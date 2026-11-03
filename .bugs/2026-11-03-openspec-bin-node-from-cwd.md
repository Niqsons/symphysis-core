# Инсталлятор исполняет файлы из корня чужого проекта вместо node, python и git

**Найден:** 2026-11-03, обзором соседнего скрипта и пробой на Windows. **Ветка:** fix/openspec-bin-cwd.

## Что сломано
`symphysis install` и `symphysis check` в проекте, где в корне лежит `node.cmd`, `python.exe` или `git.exe`,
исполняют этот файл: код чужого проекта запускается с правами человека.

## Корень
Windows ищет голое имя программы сначала в каталоге вызова. Шим npm `openspec.cmd` без `node.exe` рядом зовёт
голое `node`, а форк шёл с `cwd` проекта (`runOpenspec`). Прямые вызовы `python` и `git` ищет `libuv` так же.
Охранную переменную `NoDefaultCurrentDirectoryInExePath` `libuv` читает из окружения своего процесса, не из `options.env`.

## Как воспроизвести
Проект с `node.cmd`, пишущим маркер, шим `openspec.cmd` с `@node %*`, `SYMPHYSIS_OPENSPEC` на него, переменная снята:
`runOpenspec(["--version"], { cwd })` оставляет `marker.txt`. Тесты «Каталог вызова» в `installer/test/openspec-bin.test.js`
(только Windows; контрольный тест подтверждает, что ключа в окружении проверки нет: среда может задавать его сама).

## Чем закрыто
`spawnTool` в `installer/lib/openspec-bin.js` ставит переменную в `process.env`; все запуски в `lib/` и `bin/` идут через неё,
а окружение вызова форка несёт её же (ключ снят без учёта регистра, дубля нет). `scripts/build-vendor.js` не тронут:
идёт с `cwd` форка, не проекта.
