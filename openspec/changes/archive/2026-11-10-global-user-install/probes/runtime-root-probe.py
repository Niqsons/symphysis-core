import importlib.util
import json
import shutil
from pathlib import Path

base = Path('X:/codex-tmp/global-runtime-root-probe')
tools = base / 'user-runtime/tools'
tools.mkdir(parents=True, exist_ok=True)
shutil.copyfile('X:/symphysis/roots/roots.py', tools / 'roots.py')
(tools / 'journal-roots.json').write_text('{"": "<root>/.."}', encoding='utf-8')
project = base / 'project-a'
journal = project / 'openspec/changes/demo/decisions.json'
journal.parent.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('root_probe', tools / 'roots.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print('runtime ROOT:', module.ROOT)
print('project root:', project)
print('default_roots(journal_path=journal):', module.default_roots(journal_path=journal))
project_map = project / 'roots.json'
project_map.write_text('{"": "<root>/.."}', encoding='utf-8')
print('explicit project roots file:', module.default_roots(project_map, journal))
print('project_roots(project):', module.project_roots(project))
