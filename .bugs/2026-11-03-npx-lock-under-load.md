# Тест инсталлятора через настоящий npx плавающе падает с ECOMPROMISED

**Найден:** 2026-11-03, полный `pytest` на ветке с большим числом браузерных тестов (около 3-5 падений из 10). **Ветка:** fix/npx-lock-under-load

## Что сломано
`tests/test_installer.py::test_installer_node_tests_pass` красный, внутри падает `installer/test/npx.test.js`:
`npm error code ECOMPROMISED` / `Lock compromised`. Отдельно тест зелёный.

## Корень
npm 11.6.2, `libnpmexec/lib/with-lock.js`: блокировка `_npx/<hash>/concurrency.lock` держится на весь
`reify`; `touchLock` раз в 1000 мс сверяет inode и mtime: `if (currentStats.ino !== stats.ino || currentMtime !== mtime) { throw new Error('Lock compromised') }`,
а любая ошибка fs в `catch` даёт `controller.abort()`, после чего `withLock` отвечает
`Object.assign(new Error('Lock compromised'), { code: 'ECOMPROMISED' })`.
Других держателей в тесте нет (`spawnSync` по очереди, кэш свой у файла): npm роняет себя сам. Механизм гонки (перекрытие тиков `touchLock`, голодание
event loop дольше `staleThreshold = 5000`, вмешательство антивируса) **не доказан**.

## Как воспроизвести
Синтетическая нагрузка (12 и 24 потока на 12 ядрах) не воспроизвела: зелёно или таймауты и
`ECONNRESET`. Сбой настоящий только под полным `pytest -n 12` на ветке с браузерными тестами. Правку держит `installer/test/retry-compromised.test.js` (решение о повторе без сети).

## Чем закрыто
`installer/test-support/lock-retry.js`: вызов `npx` в `npx.test.js` повторяется один раз и только при
`ECOMPROMISED` в выводе; другая ошибка и второй `ECOMPROMISED` падают сразу. Код продукта не менялся.
Отвергнуто: свой кэш на вызов (тесты делят установку), последовательность (уже есть), заготовленный кэш.
