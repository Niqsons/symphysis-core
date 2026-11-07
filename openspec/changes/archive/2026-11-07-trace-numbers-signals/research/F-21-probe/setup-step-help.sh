#!/usr/bin/env bash
# Проба F-21, пункт 4: step-help (архив 2026-11-03) снимка graph/ не имеет. Замена базы — живой мастер на коммите
# до синхронизации: дельты step-help влиты в openspec/specs коммитом архива 37841d0 (git show --stat 37841d0 -- openspec/specs),
# поэтому мастер берётся с его родителя 37841d0^ = 5508872109b4c4bf18c1543607fd320040b6370f; без снимка build читает живой
# мастер (saved_base пуста, F-123). Требует setup.sh и run-after.sh ($TEMP/f21-probe/tools и tools-A).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
P="X:/symphysis-trace-numbers-signals"
T="$TEMP/f21-probe"
name=step-help; arch=2026-11-03-step-help; commit=5508872109b4c4bf18c1543607fd320040b6370f
R="$T/$name"; rm -rf "$R"; mkdir -p "$R/openspec/changes"
git -C "$P" archive "$commit" openspec/specs | tar -x -C "$R"
cp -r "$P/openspec/changes/archive/$arch" "$R/openspec/changes/$name"
echo "== $name: корень $R, мастер на $commit (37841d0^), specs: $(ls "$R/openspec/specs" | wc -l) каталогов; graph/ в изменении: $([ -d "$R/openspec/changes/$name/graph" ] && echo есть || echo нет)"
(cd "$R" && python -X utf8 -B "$T/tools/trace_graph.py" build "$name" --out "$R/before-build.json"; echo "build (до патча) код $?")
(cd "$R" && python -X utf8 -B "$T/tools-A/trace_graph.py" build "$name" --out "$R/after-build.json"; echo "build (после патча) код $?")
python -X utf8 -B "$HERE/signals.py" "$T/tools" "$R" "$name" > "$HERE/before-signals-$name.txt"; echo "signals (до) код $?"
python -X utf8 -B "$HERE/signals.py" "$T/tools-A" "$R" "$name" > "$HERE/after-signals-$name.txt"; echo "signals (после) код $?"
python -X utf8 -B "$HERE/compare.py" "$R/before-build.json" "$R/after-build.json" "до патча" "после патча (правило A)" \
    --journal "$R/openspec/changes/$name/decisions.json" > "$HERE/after-vs-before-$name.txt"
diff -u "$HERE/before-signals-$name.txt" "$HERE/after-signals-$name.txt" > "$HERE/signals-diff-$name.txt" || true
