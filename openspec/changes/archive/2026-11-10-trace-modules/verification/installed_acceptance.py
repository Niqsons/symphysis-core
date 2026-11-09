"""Exercise the actual installed product in disposable non-Git repositories."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'installer/scripts/sync-payload.js').is_file())
OUT = Path(__file__).resolve().parent


def main():
    import yaml
    subprocess.run(['node', str(ROOT / 'installer/scripts/sync-payload.js')], cwd=ROOT, check=True, capture_output=True)
    with tempfile.TemporaryDirectory(prefix='trace-acceptance-') as temporary:
        case = Path(temporary)
        project, external = case / 'project', case / 'external'
        project.mkdir()
        external.mkdir()
        env = {**os.environ, 'XDG_CONFIG_HOME': str(case / 'config'), 'XDG_DATA_HOME': str(case / 'data'),
               'OPENSPEC_TELEMETRY': '0', 'OPENSPEC_NO_UPDATE_CHECK': '1', 'OPENSPEC_NO_COMPLETIONS': '1'}
        logs = []

        def run(arguments, cwd):
            result = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8')
            def portable(value):
                return value.replace(str(case), '<case>').replace(str(ROOT), '<source>').replace(chr(92), '/')
            logs.append({'command': [portable(str(a)) if a != sys.executable else 'python' for a in arguments],
                         'cwd': portable(str(cwd)), 'code': result.returncode,
                         'stdout': portable(result.stdout), 'stderr': portable(result.stderr)})
            assert result.returncode == 0, logs[-1]
            return result.stdout

        run(['node', str(ROOT / 'installer/bin/symphysis.js'), 'install', '--project', str(project),
             '--skills-dir', '.agents/skills', '--force'], ROOT)
        tool = project / '.symphysis/tools/trace_graph.py'
        helper = project / '.symphysis/tools/trace_modules.py'
        assert helper.read_bytes() == (ROOT / 'trace/trace_modules.py').read_bytes()
        definitions = {
            project / 'README.md': '---\nname: viewer\nkind: технический\ndependencies:\n  - repo: plugin\n    module: viewer\n---\nPRIVATE_SYNTHETIC_BODY\n',
            project / 'src/deep/README.md': '---\nname: nested\nkind: доменный\n---\nNested module.\n',
            external / 'README.md': '---\nname: viewer\nkind: технический\n---\nExternal module.\n',
        }
        for path, body in definitions.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in definitions}
        (project / 'src/deep/used.py').write_text('value = 1\n', encoding='utf-8')
        (project / 'unused.py').write_text('value = 2\n', encoding='utf-8')
        change = project / 'openspec/changes/installed-probe'
        spec = change / 'specs/example/spec.md'
        spec.parent.mkdir(parents=True)
        metadata = {'schema': 'symphysis', 'created': '2026-11-09', 'x-symphysis-components': {
            'product': [{'repo': 'core', 'root': '', 'survey': 'found'},
                        {'repo': 'plugin', 'root': 'plugin/', 'survey': 'found'}]}}
        (change / '.openspec.yaml').write_text(yaml.safe_dump(metadata, allow_unicode=True), encoding='utf-8')
        (change / 'proposal.md').write_text('## Why\nExercise installed structure.\n\n## What Changes\nAdd a fixture.\n\n## Capabilities\n### New Capabilities\n- `example`: fixture.\n\n## Impact\nDisposable repos.\n', encoding='utf-8')
        spec.write_text('## ADDED Requirements\n\n### Requirement: Shared behavior\nThe graph SHALL retain both implementations.\n'
                        '<!-- symphysis:implements {"modules":[{"repo":"core","module":"viewer"},{"repo":"plugin","module":"viewer"}],"files":[{"repo":"core","path":"src/deep/used.py","module":"nested"}]} -->\n'
                        '\n#### Scenario: Retained\n- **WHEN** a graph is built\n- **THEN** both modules remain\n', encoding='utf-8')
        roots = case / 'roots.json'
        roots.write_text(json.dumps({'': str(project), 'plugin/': str(external)}), encoding='utf-8')
        cwd = project / 'nested/working'
        cwd.mkdir(parents=True)
        assert not any((p / '.git').exists() for p in [project, *project.parents])
        graph = json.loads(run([sys.executable, '-X', 'utf8', str(tool), 'build', 'installed-probe', '--roots', str(roots)], cwd))
        modules = [n for n in graph['nodes'] if n['kind'] == 'module']
        assert len(modules) == 3 and len({n['id'] for n in modules}) == 3
        assert {n['repo'] for n in modules if n['name'] == 'viewer'} == {'core', 'plugin'}
        implementations = [e for e in graph['edges'] if e['type'] == 'implements']
        assert len(implementations) == 4  # two named modules, the used file and its nearest module
        assert any(e['type'] == 'depends' and e['from'] == 'module:core/viewer' and e['to'] == 'module:plugin/viewer' for e in graph['edges'])
        assert not any(n.get('path') == 'unused.py' for n in graph['nodes'])
        report = run([sys.executable, '-X', 'utf8', str(tool), 'report', 'installed-probe', '--roots', str(roots)], cwd)
        run([sys.executable, '-X', 'utf8', str(tool), 'freeze', 'installed-probe', '--roots', str(roots)], cwd)
        snapshot = change / 'graph/req-graph.json'
        assert json.loads(snapshot.read_text(encoding='utf-8'))['format'] == 3
        checked = run([sys.executable, '-X', 'utf8', str(tool), 'check', 'installed-probe', str(snapshot), '--roots', str(roots)], cwd)
        assert '[!!]' not in checked
        mermaid = run([sys.executable, '-X', 'utf8', str(tool), 'build', 'installed-probe', '--format', 'mermaid',
                       '--requirement', 'example/Shared behavior', '--roots', str(roots)], cwd)
        assert 'requirementDiagram' in mermaid and 'viewer' in mermaid and 'nested' in mermaid
        serialized = json.dumps(graph, ensure_ascii=False) + report + snapshot.read_text(encoding='utf-8')
        assert str(case) not in serialized and case.as_posix() not in serialized
        assert 'PRIVATE_SYNTHETIC_BODY' not in serialized
        assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in definitions}
        evidence = {'python': sys.version.split()[0], 'git': False, 'modules': len(modules),
                    'implements': len(implementations), 'readmes_unchanged': True,
                    'helper_matches_source': True, 'private_inputs_absent': True, 'commands': logs}
        (OUT / 'installed-results.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Installed acceptance: 3 modules, 4 implements; build/report/freeze/check/mermaid passed.')


if __name__ == '__main__':
    main()
