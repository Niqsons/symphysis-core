import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import yaml

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'installer/bin/symphysis.js').is_file())
BIN = ROOT / 'installer/bin/symphysis.js'
OUTPUT = Path(__file__).with_name('runtime-integration-results.json')


def main():
    results = []
    subprocess.run(['node', str(ROOT / 'installer/scripts/sync-payload.js')], check=True, capture_output=True)
    with tempfile.TemporaryDirectory(prefix='trace-runtime-merge-') as temporary:
        for scope in ('local', 'global'):
            case = Path(temporary) / scope
            project = case / 'project'
            base = project / 'openspec/changes/runtime-probe'
            base.mkdir(parents=True)
            (project / 'openspec/config.yaml').write_text('schema: symphysis\n', encoding='utf-8')
            env = {**os.environ, 'SYMPHYSIS_OPENSPEC': str(ROOT / 'upstream/openspec/bin/openspec.js'),
                   'OPENSPEC_TELEMETRY': '0', 'OPENSPEC_NO_UPDATE_CHECK': '1', 'OPENSPEC_NO_COMPLETIONS': '1'}
            for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
                        'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR',
                        'OPENCODE_CONFIG_DIR', 'SYMPHYSIS_HOME'):
                directory = case / 'profile' / key.lower()
                directory.mkdir(parents=True, exist_ok=True)
                env[key] = str(directory)
            # The isolated profile has no user site packages; use the already installed test dependency.
            env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']
            env['PYTHONPATH'] = str(Path(yaml.__file__).parent.parent)
            commands = []

            def run(args, selected=True):
                command = ['node', str(BIN), *( ['--project', str(project)] if selected else []), *args]
                done = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, encoding='utf-8', timeout=90)
                commands.append({'arguments': [str(a).replace(str(case), '<case>').replace(chr(92), '/') for a in args],
                                 'selected_project': selected, 'code': done.returncode})
                assert done.returncode == 0, {'scope': scope, 'arguments': args, 'stderr': done.stderr}
                return done.stdout

            install = ['install', '--scope', scope, '--client', 'codex', '--force']
            if scope == 'local':
                install += ['--project', str(project)]
            run(install, selected=False)
            if scope == 'global':
                run(['init', '--project', str(project)], selected=False)
            (base / '.openspec.yaml').write_text('schema: symphysis\ncreated: 2026-11-10\nx-symphysis-components:\n  product:\n    - repo: core\n      root: ""\n      survey: found\n', encoding='utf-8')
            readme = project / 'src/deep/README.md'
            readme.parent.mkdir(parents=True)
            readme.write_text('---\nname: viewer\nkind: технический\n---\nReadonly module.\n', encoding='utf-8')
            before = hashlib.sha256(readme.read_bytes()).hexdigest()
            target = base / 'specs/example/spec.md'
            target.parent.mkdir(parents=True)
            target.write_text('## ADDED Requirements\n\n### Requirement: Runtime behavior\nThe graph SHALL retain declared implementation.\n<!-- symphysis:implements {"modules":[{"repo":"core","module":"viewer"}]} -->\n\n#### Scenario: Present\n- **WHEN** the graph is built\n- **THEN** the module remains\n', encoding='utf-8')
            roots = case / 'roots.json'
            roots.write_text(json.dumps({'': str(project)}), encoding='utf-8')
            run(['preflight', '--change', 'runtime-probe', '--json'])
            document = run(['resource', 'doc', 'module-declarations.md'])
            assert 'symphysis trace build <имя>' in document
            assert 'python .symphysis/tools/trace_graph.py' not in document
            graph = json.loads(run(['trace', 'build', 'runtime-probe', '--roots', str(roots)]))
            assert graph['format'] == 3
            assert any(n['id'] == 'module:core/viewer' for n in graph['nodes'])
            assert any(e['type'] == 'implements' and e['from'] == 'module:core/viewer' for e in graph['edges'])
            run(['trace', 'freeze', 'runtime-probe', '--roots', str(roots)])
            checked = run(['trace', 'check', 'runtime-probe', str(base / 'graph/req-graph.json'), '--roots', str(roots)])
            assert '[!!]' not in checked
            assert before == hashlib.sha256(readme.read_bytes()).hexdigest()
            if scope == 'global':
                assert not (project / '.symphysis/tools/trace_graph.py').exists()
                assert (Path(env['SYMPHYSIS_HOME']) / 'runtime/tools/trace_modules.py').is_file()
            results.append({'scope': scope, 'module_present': True, 'implements_present': True,
                            'python': sys.version.split()[0], 'test_dependency_provided': 'installed PyYAML via PYTHONPATH',
                            'readonly_readme': True, 'resource_sha256': hashlib.sha256(document.encode()).hexdigest(),
                            'commands': commands})
            print(scope, 'resource/preflight/build/freeze/check passed', flush=True)
    assert len({r['resource_sha256'] for r in results}) == 1
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
