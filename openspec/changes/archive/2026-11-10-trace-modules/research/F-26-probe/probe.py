"""Isolated F-26 probes; writes only this directory and a fresh temporary tree."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FORK = ROOT / 'upstream' / 'openspec'
NODE = shutil.which('node')
GIT = shutil.which('git')
events = []

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def sha(data):
    return hashlib.sha256(data).hexdigest()

with tempfile.TemporaryDirectory(prefix='symphysis-f26-') as tmp:
    scratch = Path(tmp)
    env = dict(os.environ)
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME'):
        env[key] = str(scratch / key.lower())
        Path(env[key]).mkdir()
    env.update(OPENSPEC_TELEMETRY='0', DO_NOT_TRACK='1', CI='true', NO_COLOR='1', PYTHONDONTWRITEBYTECODE='1')

    def clean(value):
        value = str(value)
        for path, label in ((str(scratch), '<TEMP>'), (str(FORK.resolve()), '<FORK>'), (str(ROOT), '<PROJECT>')):
            value = value.replace(path, label).replace(path.replace(chr(92), '/'), label)
            value = value.replace(path.replace(chr(92), chr(92) * 2), label)
        return value

    def run(args, cwd, label, expected=0):
        done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        events.append({'step': label, 'command': [clean(a) for a in args], 'exit': done.returncode, 'stdout': clean(done.stdout), 'stderr': clean(done.stderr)})
        if expected is not None:
            assert done.returncode == expected, (label, done.returncode, clean(done.stderr), clean(done.stdout))
        return done

    def cli(cwd, label, *args, expected=0):
        return run([NODE, str(FORK / 'bin' / 'openspec.js'), *args], cwd, label, expected)

    try:
        head = run([GIT, '-C', str(FORK), 'rev-parse', 'HEAD'], scratch, 'fork-head').stdout.strip()
        version = cli(scratch, 'fork-version', '--version').stdout.strip()
        events.append({'step': 'runtime-fingerprints', 'head': head, 'version': version, 'files': {str(p.relative_to(FORK)).replace(chr(92), '/'): sha(p.read_bytes()) for p in (FORK / 'dist/utils/change-metadata.js', FORK / 'dist/core/change-metadata/schema.js', FORK / 'src/utils/change-metadata.ts', FORK / 'src/core/change-metadata/schema.ts')}})
        project = scratch / 'project'
        project.mkdir()
        cli(project, 'new', 'new', 'change', 'metadata-probe', '--json')
        change = project / 'openspec/changes/metadata-probe'
        metadata = change / '.openspec.yaml'
        original = metadata.read_text(encoding='utf-8')
        assert 'x-symphysis-components' not in original
        extended = original + 'skip_specs: true\nx-symphysis-components:\n  demo-component:\n    - repo: demo-repo\n      commit: abc123\n      modules:\n        - src/deep/demo\n'
        metadata.write_text(extended, encoding='utf-8')
        before = metadata.read_bytes()
        cli(project, 'new-existing', 'new', 'change', 'metadata-probe', '--json', expected=1)
        assert metadata.read_bytes() == before
        cli(project, 'status-json', 'status', '--change', 'metadata-probe', '--json')
        assert metadata.read_bytes() == before
        cli(project, 'instructions-json', 'instructions', 'proposal', '--change', 'metadata-probe', '--json')
        assert metadata.read_bytes() == before
        cli(project, 'instructions-text', 'instructions', 'proposal', '--change', 'metadata-probe')
        assert metadata.read_bytes() == before
        for name, text in {'proposal.md': '# Metadata probe\n\n## Why\nIsolated metadata test.\n\n## What Changes\n- Probe metadata retention.\n\n## Capabilities\nNo behavior change.\n\n## Impact\nTemporary fixture only.\n', 'design.md': '# Design\nTemporary metadata test.\n', 'tasks.md': '## 1. Probe\n- [x] 1.1 Verify metadata retention\n'}.items():
            (change / name).write_text(text, encoding='utf-8')
        cli(project, 'validate-strict', 'validate', 'metadata-probe', '--strict', '--json')
        assert metadata.read_bytes() == before
        cli(project, 'archive', 'archive', 'metadata-probe', '--yes', '--json')
        archives = list((project / 'openspec/changes/archive').glob('*-metadata-probe'))
        assert len(archives) == 1
        assert (archives[0] / '.openspec.yaml').read_bytes() == before
        events.append({'step': 'metadata-retention', 'result': 'new creates only known metadata; repeated new refuses; status/instructions(json,text)/strict validation/archive preserve exact metadata bytes', 'sha256': sha(before), 'archived': True})

        # Direct public helper probe: parse result and rewrite behavior in scratch only.
        helper = scratch / 'metadata-helper.mjs'
        helper.write_text('import fs from "node:fs";\nimport {readChangeMetadata,writeChangeMetadata,readUnknownChangeMetadataKeys} from ' + json.dumps((FORK / 'dist/utils/change-metadata.js').as_uri()) + ';\nconst [dir,root]=process.argv.slice(2);\nconst parsed=readChangeMetadata(dir,root);\nconsole.log(JSON.stringify({keys:Object.keys(parsed),unknown:readUnknownChangeMetadataKeys(dir)}));\nwriteChangeMetadata(dir,parsed,root);\nconsole.log(JSON.stringify({extensionAfterRewrite:fs.readFileSync(dir+"/.openspec.yaml","utf8").includes("x-symphysis-components")}));\n', encoding='utf-8')
        result = run([NODE, str(helper), str(archives[0]), str(project)], scratch, 'metadata-helper')
        assert '"extensionAfterRewrite":false' in result.stdout

        # Stores are separate from repository/material intake. No Git initialization.
        store = scratch / 'store'
        cli(scratch, 'store-setup-without-git', 'store', 'setup', 'demo-store', '--path', str(store), '--no-init-git', '--json')
        pointer = scratch / 'pointer'
        (pointer / 'openspec').mkdir(parents=True)
        (pointer / 'openspec/config.yaml').write_text('store: demo-store\n', encoding='utf-8')
        cli(pointer, 'store-new-from-pointer', 'new', 'change', 'store-probe', '--json')
        root_status = cli(pointer, 'store-status-from-pointer', 'status', '--change', 'store-probe', '--json')
        assert json.loads(root_status.stdout)['root']['source'] == 'declared'
        assert not (store / '.git').exists()
        events.append({'step': 'store-no-git', 'result': 'setup --no-init-git and declared store pointer new/status succeed; no .git exists'})

        roots = load('f26_roots', ROOT / 'roots/roots.py')
        resolved = roots._resolve('demo/src/deep/demo/README.md', {'demo/': project})
        assert resolved == project / 'src/deep/demo/README.md'
        assert roots._resolve('demo/../outside', {'demo/': project}) == roots.OUTSIDE_ROOT
        events.append({'step': 'roots-explicit-map', 'result': 'long prefix resolves nested path without Git; parent escape rejected; no personal roots file called'})
        # Module detector runs against an indexed synthetic Git repository.
        structure = load('f26_structure', ROOT / 'tests/repository_structure.py')
        repo = scratch / 'modules'
        repo.mkdir()
        run([GIT, 'init', '-q', str(repo)], scratch, 'structure-git-init')
        fixture = {'README.md': '# Demo\n\n- [top/](top/) — модуль\n- [src/](src/) — контур разработки\n- [openspec/](openspec/) — контур разработки\n', '.gitignore': 'ignored/\n', 'top/README.md': '---\nname: top\nkind: технический\n---\n# Top\n', 'src/deep/plain/README.md': '# Plain README\n', 'src/deep/marked/README.md': '---\nname: marked\nkind: доменный\n---\n# Marked\n', 'openspec/schemas/symphysis/schema.yaml': 'name: demo\n', 'ignored/README.md': '---\nname: ignored\nkind: доменный\n---\n'}
        for relative, content in fixture.items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        run([GIT, '-C', str(repo), 'add', '.'], scratch, 'structure-index')
        untracked = repo / 'src/deep/untracked/README.md'
        untracked.parent.mkdir(parents=True)
        untracked.write_text('---\nname: untracked\nkind: технический\n---\n', encoding='utf-8')
        model = structure.Repo(repo)
        found = structure.module_dirs(model)
        places = structure.check_module_places(model)
        assert found == ['openspec/schemas/symphysis', 'src/deep/marked', 'top']
        assert len(places) == 1 and 'src/deep/marked/' in places[0]
        events.append({'step': 'module-detection', 'found': found, 'placeSignals': places, 'notDetected': ['plain README without name/kind', 'ignored README', 'untracked README']})
        no_git = scratch / 'no-git'
        no_git.mkdir()
        try:
            structure.Repo(no_git)
        except subprocess.CalledProcessError as exc:
            events.append({'step': 'module-detection-no-git', 'exit': exc.returncode, 'result': 'CalledProcessError from git ls-files; no fallback'})
        else:
            raise AssertionError('Expected Git dependency')
        # settings only reads synthetic data under scratch.
        sys.path.insert(0, str(ROOT / 'roots'))
        settings_module = load('f26_settings', ROOT / 'settings/symphysis_config.py')
        settings_root = scratch / 'settings'
        settings_root.mkdir()
        (settings_root / 'symphysis.yaml').write_text('repos:\n  demo-repo: ./demo\n', encoding='utf-8')
        settings = settings_module.read_settings(settings_root)
        if settings_module.SIGNAL_NO_PACKAGE in settings.signals:
            events.append({'step': 'settings-reader-limitation', 'signals': settings.signals, 'result': 'isolated Python has no PyYAML; following check calls _apply on an in-memory synthetic mapping'})
            settings = settings_module.Settings()
            settings_module._apply({'repos': {'demo-repo': './demo'}}, settings)
        assert settings.signals == ['symphysis.yaml: неизвестный ключ repos'], settings.signals
        events.append({'step': 'settings-repos', 'signals': settings.signals, 'result': 'repos is not accepted as repository map'})
        events.append({'step': 'final', 'result': 'PASS'})
    except BaseException as exc:
        events.append({'step': 'failure', 'type': type(exc).__name__, 'message': clean(exc)})
        raise
    finally:
        (HERE / 'results.json').write_text(json.dumps(events, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        lines = ['F-26 isolated probe', 'No source/build/install mutation; global config/data/home isolated in a fresh temporary directory; telemetry disabled.']
        for event in events:
            if event['step'] in {'runtime-fingerprints', 'metadata-retention', 'metadata-helper', 'store-no-git', 'roots-explicit-map', 'module-detection', 'module-detection-no-git', 'settings-reader-limitation', 'settings-repos', 'final', 'failure'}:
                lines.append(json.dumps(event, ensure_ascii=False, sort_keys=True))
        (HERE / 'summary.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
