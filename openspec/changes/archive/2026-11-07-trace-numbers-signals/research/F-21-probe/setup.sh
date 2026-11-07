#!/usr/bin/env bash
# Проба F-21, шаг 1: временный корень вне проекта для сборки графа архивных изменений.
# Корень пробы: $TEMP/f21-probe/<имя изменения>/ — openspec/specs на коммите снимка (roots[0].commit),
# openspec/changes/<имя>/ — копия архивного каталога (с graph/req-graph.json: из него build берёт базу).
# Инструменты: $TEMP/f21-probe/tools/ — trace_graph.py из trace/ (равен .symphysis/tools/trace_graph.py, diff -q),
# соседи roots.py, journal_model.py (+ journal.schema.json), openspec_run.py — из .symphysis/tools/ (только stdlib).
# В проект скрипт не пишет ничего.
set -e
P="X:/symphysis-trace-numbers-signals"
T="$TEMP/f21-probe"
rm -rf "$T"; mkdir -p "$T/tools"
cp "$P/trace/trace_graph.py" "$T/tools/"
cp "$P/.symphysis/tools/roots.py" "$P/.symphysis/tools/journal_model.py" "$P/.symphysis/tools/journal.schema.json" "$P/.symphysis/tools/openspec_run.py" "$T/tools/"
for pair in "module-structure:2026-11-07-module-structure:9b012131bfffcbf84aefb596f6c71e32ad2f99c2" \
            "trace-graph:2026-11-06-trace-graph:e1e3c551f6fb035fcc03622bc2b091adc9679146"; do
  name=${pair%%:*}; rest=${pair#*:}; arch=${rest%%:*}; commit=${rest#*:}
  R="$T/$name"; mkdir -p "$R/openspec/changes"
  git -C "$P" archive "$commit" openspec/specs | tar -x -C "$R"
  cp -r "$P/openspec/changes/archive/$arch" "$R/openspec/changes/$name"
  echo "== $name: корень $R, мастер на $commit, specs: $(ls "$R/openspec/specs" | wc -l) каталогов"
  (cd "$R" && python -X utf8 -B "$T/tools/trace_graph.py" build "$name" --out "$R/before-build.json"; echo "build (до патча) код $?")
done
