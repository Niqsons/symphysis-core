#!/usr/bin/env bash
# Проба к журналу step-help: что `openspec status` и `instructions apply` говорят о пустых файлах.
# Запуск: bash status-empty-files.sh <форк: путь к bin/openspec.js> <каталог схемы symphysis> > status-empty-files.txt
# Пишет только во временный каталог; глобальный конфиг не задет: XDG_CONFIG_HOME временный, телеметрия выключена.
set -u
FORK="$1"; SCHEMA="$2"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
mkdir -p "$W/proj/openspec/schemas" "$W/xdg"; cp -r "$SCHEMA" "$W/proj/openspec/schemas/symphysis"
printf 'schema: symphysis\n' > "$W/proj/openspec/config.yaml"; cd "$W/proj"
export XDG_CONFIG_HOME="$W/xdg" OPENSPEC_TELEMETRY=0
O() { node "$FORK" "$@" 2>/dev/null; }
show() { echo "=== $1"; O status --change x --json | node -e "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{const s=JSON.parse(d);const by=k=>s.artifacts.filter(a=>a.status===k).map(a=>a.id).join(' ');console.log('готово: '+by('done'));console.log('готовы к работе: '+by('ready'));console.log('isPlanningComplete='+s.isPlanningComplete+' applyRequires='+s.applyRequires.join(','))})"; }
C=openspec/changes/x
O new change x >/dev/null; printf '# намерение\n' > "$C/intent.md"; show "только intent.md"
printf '{}' > "$C/decisions.json"; show "decisions.json = {}: ни одной записи, ничего не решено"
mkdir -p "$C/research" "$C/specs/a"; : > "$C/research/none.md"; : > "$C/proposal.md"; : > "$C/specs/a/spec.md"; show "пустые research/none.md, proposal.md, specs/a/spec.md"
: > "$C/consequences.md"; : > "$C/design.md"; printf -- '- [ ] 1.1 задача\n' > "$C/tasks.md"; show "пустые consequences.md, design.md; tasks.md с одной задачей; security.md нет"
echo "=== instructions apply без security.md"; O instructions apply --change x --json | node -e "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{const s=JSON.parse(d);console.log('state='+s.state+' progress='+JSON.stringify(s.progress))})"
