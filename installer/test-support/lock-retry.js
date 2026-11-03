/**
 * Повтор вызова `npx` один раз, и только на точном коде ECOMPROMISED в выводе.
 * Код приходит из блокировки кэша самого npm: она держится на всю установку и сама себя
 * объявляет нарушенной под нагрузкой на машину. Любая другая ошибка, как и второй
 * ECOMPROMISED, возвращается как есть — настоящие отказы повтор не прячет.
 * `run` — вызов, возвращающий результат spawnSync.
 */
export function runWithLockRetry(run) {
  const first = run();
  if (first.status === 0 || !/ECOMPROMISED/.test(`${first.stdout}${first.stderr}`)) return first;
  return run();
}
