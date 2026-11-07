#!/usr/bin/env bash
# Проба F-21, шаг 2: патч правила A на копии, сборка «после» для обоих изменений, сравнение связей и сигналов.
# Требует выполненного setup.sh ($TEMP/f21-probe). В проект пишет только файлы следа в этом каталоге.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
P="X:/symphysis-trace-numbers-signals"
T="$TEMP/f21-probe"
python -X utf8 -B "$HERE/patch-rule-A.py" "$T/tools" "$T/tools-A" | tee "$HERE/patch-rule-A.txt"
diff -u "$T/tools/trace_graph.py" "$T/tools-A/trace_graph.py" > "$HERE/patch-rule-A.diff" || true
for pair in "module-structure:2026-11-07-module-structure" "trace-graph:2026-11-06-trace-graph"; do
  name=${pair%%:*}; arch=${pair#*:}
  R="$T/$name"
  (cd "$R" && python -X utf8 -B "$T/tools-A/trace_graph.py" build "$name" --out "$R/after-build.json"; echo "build (после патча) $name код $?") | tee -a "$HERE/patch-rule-A.txt"
  python -X utf8 -B "$HERE/signals.py" "$T/tools-A" "$R" "$name" > "$HERE/after-signals-$name.txt"; echo "signals (после) $name код $?" | tee -a "$HERE/patch-rule-A.txt"
  python -X utf8 -B "$HERE/compare.py" "$R/before-build.json" "$R/after-build.json" "до патча" "после патча (правило A)" \
      --journal "$R/openspec/changes/$name/decisions.json" > "$HERE/after-vs-before-$name.txt"
  diff -u "$HERE/before-signals-$name.txt" "$HERE/after-signals-$name.txt" > "$HERE/signals-diff-$name.txt" || true
done
