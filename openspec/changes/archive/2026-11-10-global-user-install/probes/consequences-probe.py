"""Isolated probes of existing branches; no personal configs or installed clients."""
from pathlib import Path
import importlib.util
import json
import ntpath
import os
import subprocess
import tempfile
from unittest.mock import patch

REPO = Path('X:/symphysis-global-user-install')
FIXTURE = Path('X:/codex-tmp/global-consequences-probe')
STORE = FIXTURE / 'store'
RUNTIME = FIXTURE / 'runtime'
SOURCE = FIXTURE / 'source'


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def load_roots():
    module_file = RUNTIME / 'tools/roots.py'
    put(module_file, (REPO / 'roots/roots.py').read_text(encoding='utf-8'))
    spec = importlib.util.spec_from_file_location('isolated_consequences_roots', module_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


put(SOURCE / 'sample.txt', 'isolated evidence\n')
journal = STORE / 'openspec/changes/demo/decisions.json'
put(journal, '{}\n')
store_map = STORE / '.symphysis/tools/journal-roots.json'
put(store_map, json.dumps({'': '<root>/..', 'src/': SOURCE.as_posix()}))
roots = load_roots()
# A deliberately nonexistent fixture path: never read the real user roots map.
roots.ROOTS_PATH = RUNTIME / 'absent-roots.json'
implicit = roots.default_roots(journal_path=journal)
explicit = roots.default_roots(roots_file=store_map, journal_path=journal)
assert 'src/' not in implicit
assert explicit[''].resolve() == FIXTURE.resolve()
assert explicit[''].resolve() != STORE.resolve()

put(STORE / '.claude/skills/openspec-continue-change/SKILL.md', '# fixture\n')
put(STORE / '.agents/skills/openspec-propose/SKILL.md', '# fixture\n')
node_code = r"""
import path from 'node:path';
import { selectedClients, continueLines, ensureContinue } from './installer/lib/clients.js';
import { mergeConfig } from './installer/lib/install.js';
const root = process.argv[1];
const dirs = ['.claude/skills', '.agents/skills'].map(d => path.join(root, d));
const clients = selectedClients(root, dirs);
const config = mergeConfig('schema: spec-driven\nrules: keep-user-value\noperations: keep-operations\n',
  'schema: symphysis\nrules:\n  intent:\n    - product-rule\noperations:\n  archive:\n    guidance:\n      - product-guidance\n');
console.log(JSON.stringify({ clients, lines: continueLines(clients), install: ensureContinue(root, dirs), config }));
"""
reply = subprocess.run(['node', '--input-type=module', '-e', node_code, str(STORE)],
                       cwd=REPO, capture_output=True, text=True, encoding='utf-8', check=True)
clients = json.loads(reply.stdout)
assert [c['hasContinue'] for c in clients['clients']] == [True, False]
assert clients['lines']['findings'] == []
assert clients['install'] == []
assert 'keep-user-value' not in clients['config']['text']
assert 'keep-operations' in clients['config']['text']
assert clients['config']['warnings'] == ['operations не словарь — подсказки symphysis не добавлены']

try:
    ntpath.relpath('C:/runtime/skill/SKILL.md', 'X:/store/change')
except ValueError:
    different_drive_error = True
else:
    different_drive_error = False
assert different_drive_error
with patch.object(roots.os.path, 'relpath', side_effect=ValueError('different drives: fixture')):
    dropped_link = roots._relative_link('src/sample.txt', [{'src/': SOURCE}], journal.parent)
assert dropped_link is None

openspec_fixture = Path(tempfile.mkdtemp(prefix='global-consequences-openspec-', dir=FIXTURE))
user_data = openspec_fixture / 'data'
project_local = openspec_fixture / 'project-local'
project_global = openspec_fixture / 'project-global'
schema = (REPO / 'openspec/schemas/symphysis/schema.yaml').read_text(encoding='utf-8')
put(user_data / 'openspec/schemas/symphysis/schema.yaml', schema)
put(project_local / 'openspec/schemas/symphysis/schema.yaml', schema)
for project in (project_local, project_global):
    put(project / 'openspec/config.yaml', 'schema: symphysis\n')
env = {**os.environ, 'XDG_DATA_HOME': str(user_data),
       'XDG_CONFIG_HOME': str(openspec_fixture / 'config'),
       'OPENSPEC_TELEMETRY': '0', 'OPENSPEC_NO_UPDATE_CHECK': '1',
       'OPENSPEC_NO_COMPLETIONS': '1', 'TEMP': str(FIXTURE), 'TMP': str(FIXTURE)}
cli = REPO / 'upstream/openspec/bin/openspec.js'


def openspec(project, *args):
    reply = subprocess.run(['node', str(cli), *args], cwd=project, env=env,
                           capture_output=True, text=True, encoding='utf-8')
    assert reply.returncode == 0, (args, reply.returncode, reply.stderr)
    return {'args': list(args), 'code': reply.returncode, 'out': reply.stdout, 'err': reply.stderr}


native = {
    'project_schema': openspec(project_local, 'schema', 'which', 'symphysis', '--json'),
    'user_schema': openspec(project_global, 'schema', 'which', 'symphysis', '--json'),
    'new_without_compatibility': openspec(project_global, 'new', 'change', 'native-no-declaration'),
}
native['created_without_compatibility'] = (project_global / 'openspec/changes/native-no-declaration').is_dir()
assert native['created_without_compatibility']

result = {
    'fixture': 'X:/codex-tmp/global-consequences-probe',
    'roots': {
        'implicit_store_prefixes': sorted(implicit),
        'explicit_root_is_runtime_parent': explicit[''].resolve() == FIXTURE.resolve(),
        'explicit_root_is_store': explicit[''].resolve() == STORE.resolve(),
    },
    'continue': clients,
    'cross_drive': {
        'ntpath_raises': different_drive_error,
        'relative_link_with_injected_drive_error': dropped_link,
        'physical_second_drive_tested': False,
    },
    'openspec': native,
}
out = REPO / 'openspec/changes/global-user-install/probes/consequences-results.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Isolated probes passed: roots, continue, cross-drive branch, native schema lookup and new change')
