"""Structural declarations and source boundaries (trace-modules)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT


def helper():
    import trace_modules
    return trace_modules


def metadata(base, components):
    import yaml
    base.mkdir(parents=True, exist_ok=True)
    (base / '.openspec.yaml').write_text(yaml.safe_dump({'schema': 'symphysis', 'x-symphysis-components': components}, allow_unicode=True), encoding='utf-8')


def readme(root, rel='README.md', name='viewer', kind='доменный', dependencies=None):
    import yaml
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    declaration = {'name': name, 'kind': kind}
    if dependencies is not None:
        declaration['dependencies'] = dependencies
    path.write_text('---\n' + yaml.safe_dump(declaration, allow_unicode=True) + '---\nDescription\n', encoding='utf-8')
    return path


def test_component_metadata_is_portable_and_commit_is_not_checkout(tmp_path):
    base = tmp_path / 'change'
    metadata(base, {'product': [{'repo': 'core', 'root': '', 'survey': 'found', 'commit': 'old'}, {'repo': 'plugin', 'root': 'external/', 'survey': 'unexamined'}]})
    result = helper().read_components(base)
    assert result['components'] == [{'name': 'product', 'repos': ['core', 'plugin']}]
    assert [r['repo'] for r in result['repos']] == ['core', 'plugin']
    assert result['repos'][0]['commit'] == 'old'
    assert not result['signals']


def test_readme_and_annotation_share_logical_names(tmp_path):
    path = readme(tmp_path, 'src/editor/README.md', dependencies=[{'repo': 'other', 'module': 'api'}])
    declaration = helper().read_declaration(path.read_bytes())
    assert declaration['name'] == 'viewer' and declaration['kind'] == 'доменный'
    assert declaration['dependencies'] == [{'repo': 'other', 'module': 'api'}]
    annotation = '<!-- symphysis:implements ' + json.dumps({'modules': [{'repo': 'core', 'module': 'viewer'}]}) + ' -->'
    assert helper().read_implementations(annotation)[0][1]['modules'][0]['module'] == 'viewer'


@pytest.mark.parametrize('raw', [b'---\nname: x\nkind: invalid\n---\n', b'---\nname: [x]\nkind: domain\n---\n'])
def test_invalid_declaration_is_not_a_module(raw):
    with pytest.raises(helper().DeclarationError):
        helper().read_declaration(raw)


def test_object_yaml_is_rejected_without_side_effect(tmp_path):
    marker = tmp_path / 'marker'
    raw = ('---\nname: !!python/object/apply:builtins.eval ["open(' + repr(str(marker)) + ', chr(119))"]\nkind: доменный\n---\n').encode('utf-8')
    with pytest.raises(helper().DeclarationError):
        helper().read_declaration(raw)
    assert not marker.exists()


def test_shared_protocol_fixtures_are_readable():
    fixture = ROOT / 'tests/fixtures/trace/modules'
    assert len(helper().read_components(fixture)['repos']) == 2
    assert helper().read_declaration((fixture / 'README.fixture').read_bytes())['name'] == 'example'
    assert helper().read_implementations((fixture / 'specs/example/spec.md').read_text(encoding='utf-8'))[0][1]['files'][0]['path'] == 'main.py'


def test_exact_repo_alias_and_unused_roots(tmp_path):
    base, core, external = (tmp_path / name for name in ('change', 'core', 'external'))
    readme(core)
    readme(core / 'missing', name='wrong')
    readme(external, name='api')
    metadata(base, {'p': [{'repo': 'core', 'root': '', 'survey': 'found'}, {'repo': 'plugin', 'root': 'missing/', 'survey': 'found'}]})
    state = helper().discover(base, {'': core, 'unused/': external})
    assert {m['repo'] for m in state['modules']} == {'core'}
    assert next(r for r in state['repos'] if r['repo'] == 'plugin')['actual'] == 'unavailable'
    assert any('псевдоним' in s['reason'] for s in state['signals'])
    assert not any(r['repo'] == 'unused' for r in state['repos'])


def test_discovery_depth_exclusions_ownership_and_duplicates(tmp_path):
    base, repo = tmp_path / 'change', tmp_path / 'repo'
    readme(repo, name='base')
    readme(repo, 'src/deep/part/README.md', name='part')
    readme(repo, 'node_modules/pkg/README.md', name='bad')
    readme(repo, '.git/README.md', name='bad')
    readme(repo, '.symphysis/README.md', name='bad')
    readme(repo, 'generated/README.md', name='bad')
    metadata(base, {'p': [{'repo': 'core', 'root': '', 'survey': 'found', 'exclude': ['generated']}]})
    state = helper().discover(base, {'': repo})
    assert {m['name'] for m in state['modules']} == {'base', 'part'}
    assert helper().owner(state, 'core', 'src/deep/part/main.py')['name'] == 'part'
    readme(repo, 'another/README.md', name='part')
    state = helper().discover(base, {'': repo})
    assert helper().module(state, 'core', 'part') is None
    assert any('another/README.md' in s['reason'] and 'src/deep/part/README.md' in s['reason'] for s in state['signals'])


def test_bad_readme_partial_graph_states_and_no_mutation(tmp_path, monkeypatch):
    base, repo = tmp_path / 'change', tmp_path / 'repo'
    good = readme(repo, name='good')
    blocked = readme(repo, 'blocked/README.md', name='blocked')
    readme(repo, 'bad/README.md', name='bad').write_bytes(b'---\nname: \xff\nkind: x\n---')
    readme(repo, 'binary/README.md').write_bytes(b'---\nname: x\x00\n---')
    metadata(base, {'p': [{'repo': 'core', 'root': '', 'survey': 'none'}]})
    before = (base / '.openspec.yaml').read_bytes()
    raw_read = Path.read_bytes
    def fail(path):
        if path == blocked:
            raise PermissionError('private path must not appear')
        return raw_read(path)
    monkeypatch.setattr(Path, 'read_bytes', fail)
    state = helper().discover(base, {'': repo})
    assert {m['name'] for m in state['modules']} == {'good'}
    assert len(state['signals']) >= 3
    assert 'private path' not in json.dumps(state, ensure_ascii=False)
    assert (base / '.openspec.yaml').read_bytes() == before
    assert state['repos'][0]['actual'] == 'unexamined'


@pytest.mark.parametrize('bom', [False, True])
@pytest.mark.parametrize('eol', ['\n', '\r\n'])
def test_readme_bom_and_eol(bom, eol):
    raw = ('---\nname: a\nkind: технический\n---\n').replace('\n', eol).encode('utf-8')
    assert helper().read_declaration((b'\xef\xbb\xbf' if bom else b'') + raw)['name'] == 'a'


def test_symlink_escape_service_alias_and_cycle(tmp_path, monkeypatch):
    base, repo, external = (tmp_path / n for n in ('change', 'repo', 'external'))
    readme(repo, name='good')
    readme(external, name='outside')
    readme(repo, 'node_modules/a/README.md', name='service')
    original_read = Path.read_bytes
    def guarded_read(path):
        assert not path.is_relative_to(external), 'outside declaration content must never be read'
        return original_read(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded_read)
    created = []
    try:
        for link, target in [(repo / 'escape', external), (repo / 'loop', repo), (repo / 'alias', repo / 'node_modules')]:
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                if os.name != 'nt':
                    raise
                done = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
                assert done.returncode == 0, done.stderr
            created.append(link)
        metadata(base, {'p': [{'repo': 'r', 'root': '', 'survey': 'found'}]})
        state = helper().discover(base, {'': repo})
        assert [m['name'] for m in state['modules']] == ['good']
        assert any('корн' in s['reason'] for s in state['signals'])
    finally:
        for link in reversed(created):
            assert link.absolute().parent == repo.absolute()
            if link.is_symlink():
                link.unlink()
            else:
                link.rmdir()  # junction only; never recurse into its target


def test_readme_file_alias_keeps_its_declared_directory_boundary(tmp_path, monkeypatch):
    mod = helper()
    base, repo = tmp_path / 'change', tmp_path / 'repo'
    metadata(base, {'p': [{'repo': 'r', 'root': '', 'survey': 'found'}]})
    repo.mkdir()
    target = repo / 'docs/module.md'
    target.parent.mkdir()
    target.write_text('---\nname: root-module\nkind: технический\n---\n', encoding='utf-8')
    alias = repo / 'README.md'
    alias.write_text('Alias entry; resolver below models an in-root file symlink.\n', encoding='utf-8')
    resolve = mod._resolve
    monkeypatch.setattr(mod, '_resolve', lambda path, roots: target.resolve() if path == 'README.md' else resolve(path, roots))
    state = mod.discover(base, roots={'': repo})
    assert state['modules'][0]['path'] == '.'
    assert state['modules'][0]['source'] == 'README.md'
    assert mod.owner(state, 'r', 'main.py')['name'] == 'root-module'
    source = next(s for s in state['sources'] if s.get('repo') == 'r')
    assert source['path'] == 'README.md'
    assert source['sha256'] == mod.content_hash(target.read_bytes())


def test_quoted_metadata_extension_is_not_silently_ignored(tmp_path):
    (tmp_path / '.openspec.yaml').write_text('schema: symphysis\n"x-symphysis-components":\n  p:\n    - repo: r\n      root: ""\n', encoding='utf-8')
    assert helper().read_components(tmp_path)['repos'][0]['repo'] == 'r'


def test_duplicate_yaml_keys_are_diagnostic_not_last_wins():
    with pytest.raises(helper().DeclarationError):
        helper().read_declaration('---\nname: a\nname: b\nkind: доменный\n---'.encode('utf-8'))


def test_example_annotation_in_fence_does_not_declare_implementation():
    text = '```markdown\n<!-- symphysis:implements {"modules":[{"repo":"r","module":"fake"}]} -->\n```\n'
    assert helper().read_implementations(text) == []


def test_gitignore_does_not_define_module_exclusions(tmp_path):
    repo, base = tmp_path / 'repo', tmp_path / 'change'
    readme(repo, 'ignored/README.md', name='ignored')
    (repo / '.gitignore').write_text('ignored/\n', encoding='utf-8')
    metadata(base, {'p': [{'repo': 'r', 'root': '', 'survey': 'found'}]})
    state = helper().discover(base, {'': repo})
    assert [m['name'] for m in state['modules']] == ['ignored']


def test_current_external_and_unavailable_repo_are_distinct(tmp_path):
    base, repo, external = (tmp_path / n for n in ('change', 'repo', 'external'))
    readme(repo, name='viewer')
    readme(external, name='viewer')
    metadata(base, {'p': [{'repo': 'core', 'root': '', 'survey': 'found'}, {'repo': 'plugin', 'root': 'external/', 'survey': 'found'}, {'repo': 'lost', 'root': 'lost/', 'survey': 'none'}]})
    state = helper().discover(base, {'': repo, 'external/': external, 'lost/': tmp_path / 'missing'})
    assert [(m['repo'], m['name']) for m in state['modules']] == [('core', 'viewer'), ('plugin', 'viewer')]
    assert [r['actual'] for r in state['repos']] == ['found', 'found', 'unavailable']


def test_file_outside_all_module_boundaries_is_not_assigned(tmp_path):
    base, repo = tmp_path / 'change', tmp_path / 'repo'
    readme(repo, 'src/one/README.md', name='one')
    metadata(base, {'p': [{'repo': 'r', 'root': '', 'survey': 'found'}]})
    state = helper().discover(base, {'': repo})
    assert helper().owner(state, 'r', 'docs/file.md') is None


def graph_project(tmp_path, annotation=None):
    import trace_graph
    base = tmp_path / 'openspec/changes/demo'
    core, plugin = tmp_path / 'core', tmp_path / 'plugin'
    readme(core, name='a', dependencies=[{'repo': 'plugin', 'module': 'b'}])
    readme(core, 'independent/README.md', name='independent')
    readme(plugin, name='b')
    (core / 'main.py').write_text('pass\n', encoding='utf-8')
    metadata(base, {'product': [{'repo': 'core', 'root': '', 'survey': 'found'}, {'repo': 'plugin', 'root': 'plugin/', 'survey': 'found'}]})
    spec = base / 'specs/demo/spec.md'
    spec.parent.mkdir(parents=True)
    annotation = annotation if annotation is not None else {'modules': [{'repo': 'core', 'module': 'a'}, {'repo': 'plugin', 'module': 'b'}], 'files': [{'repo': 'core', 'path': 'main.py'}]}
    spec.write_text('## ADDED Requirements\n\n### Requirement: R\nThe system SHALL work.\n<!-- symphysis:implements ' + json.dumps(annotation) + ' -->\n\n#### Scenario: S\n- **GIVEN** x\n- **WHEN** y\n- **THEN** z\n', encoding='utf-8')
    roots_file = tmp_path / 'roots.json'
    roots_file.write_text(json.dumps({'': str(core), 'plugin/': str(plugin)}), encoding='utf-8')
    return trace_graph, base, core, plugin, roots_file


def test_graph_has_structure_explicit_realization_and_provenance(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path)
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    assert graph['format'] == 3
    assert {n['kind'] for n in graph['nodes']} >= {'component', 'repo', 'module', 'file', 'req', 'scn'}
    modules = {n['name']: n for n in graph['nodes'] if n['kind'] == 'module'}
    assert set(modules) == {'a', 'b', 'independent'}
    implements = [e for e in graph['edges'] if e['type'] == 'implements' and e['to'] == 'req:demo/R']
    assert {modules['a']['id'], modules['b']['id']} <= {e['from'] for e in implements}
    assert all('specs/demo/spec.md:' in e['at'] for e in implements)
    assert any(e['type'] == 'depends' and e['from'] == modules['a']['id'] and e['to'] == modules['b']['id'] for e in graph['edges'])
    assert not any(e['from'] == modules['independent']['id'] and e['type'] == 'implements' for e in graph['edges'])
    assert str(tmp_path) not in json.dumps(graph, ensure_ascii=False)


def test_annotation_without_repo_metadata_is_reported_as_unresolved(tmp_path, monkeypatch):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {'modules': [{'repo': 'missing', 'module': 'typo'}]})
    (base / '.openspec.yaml').write_text('schema: symphysis\n', encoding='utf-8')
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    assert any('missing/typo' in s['reason'] for s in graph.get('structure', {}).get('signals', []))
    assert not any(e['type'] == 'implements' for e in graph['edges'])


def test_annotation_respects_every_accepted_requirement_header(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {})
    spec = base / 'specs/demo/spec.md'
    spec.write_text('## ADDED Requirements\n\n### Requirement: A\nThe system SHALL work.\n'
                    '\n###Requirement: B\nThe system SHALL retain B.\n'
                    '<!-- symphysis:implements {"modules":[{"repo":"core","module":"a"}]} -->\n', encoding='utf-8')
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    implements = [e for e in graph['edges'] if e['type'] == 'implements']
    assert {e['to'] for e in implements} == {'req:demo/B'}


def test_conflicting_module_file_pair_does_not_erase_independent_realization(tmp_path):
    annotation = {'modules': [{'repo': 'plugin', 'module': 'b'}], 'files': [{'repo': 'core', 'path': 'independent/x.py', 'module': 'a'}]}
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, annotation)
    (core / 'independent/x.py').write_text('x', encoding='utf-8')
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    assert len([e for e in graph['edges'] if e['type'] == 'implements']) == 1
    assert any('противореч' in s['reason'] for s in graph['structure']['signals'])


def test_dependency_does_not_imply_realization_and_unknown_target_is_signal(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {'modules': [{'repo': 'core', 'module': 'a'}]})
    readme(plugin, name='b', dependencies=[{'repo': 'core', 'module': 'a'}, {'repo': 'core', 'module': 'absent'}])
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    assert len([e for e in graph['edges'] if e['type'] == 'implements']) == 1
    assert len([e for e in graph['edges'] if e['type'] == 'depends']) == 2
    assert any('absent' in s['reason'] for s in graph['structure']['signals'])


def test_sources_and_id_parts_are_unambiguous(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {})
    metadata(base, {'p': [{'repo': 'api/x', 'root': '', 'survey': 'found'}, {'repo': 'api', 'root': 'plugin/', 'survey': 'found'}]})
    readme(core, name='m')
    (core / 'independent/README.md').unlink()
    readme(plugin, name='x/m')
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    modules = [n for n in graph['nodes'] if n['kind'] == 'module']
    assert len(modules) == len({n['id'] for n in modules}) == 2
    assert any(s['path'] == '.openspec.yaml' for s in graph['sources'])
    assert {s['repo'] for s in graph['structure']['inventory']} == {'api/x', 'api'}


def test_report_keeps_structural_signal_groups_and_has_no_global_coverage_verdict(tmp_path, monkeypatch):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {'modules': [{'repo': 'core', 'module': 'typo'}]})
    readme(plugin, name='b', kind='служебный')
    monkeypatch.setattr(graph_api, 'validate_findings', lambda *_: [])
    report = graph_api.build_report(tmp_path, 'demo', roots_file=roots_file)
    assert 'Связь не разрешена' in report and 'typo' in report
    assert 'Опоры нет' in report
    assert 'нереализован' not in report and 'нет требований во всей системе' not in report


def test_supported_v2_base_survives_new_format(tmp_path):
    import trace_graph
    (tmp_path / 'graph').mkdir()
    saved = {'demo': {'R': {'numbers': ['F-01'], 'scenarios': {}, 'text': 'old', 'traces': ['F-01']}}}
    (tmp_path / 'graph/req-graph.json').write_text(json.dumps({'format': 2, 'base': saved}), encoding='utf-8')
    assert trace_graph.saved_base(tmp_path) == saved


def test_freeze_reads_each_declaration_once_and_keeps_history_without_clone(tmp_path, monkeypatch):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path)
    monkeypatch.setattr(graph_api, 'validate_findings', lambda *_: [])
    raw_read = Path.read_bytes
    counts = {}
    def alternating(path):
        data = raw_read(path)
        if path.name == 'README.md':
            counts[path] = counts.get(path, 0) + 1
            if counts[path] > 1:
                return data.replace(b'name: a', b'name: changed')
        return data
    monkeypatch.setattr(Path, 'read_bytes', alternating)
    graph_api.freeze_change(tmp_path, 'demo', roots_file)
    frozen = json.loads((base / 'graph/req-graph.json').read_text(encoding='utf-8'))
    assert any(n['kind'] == 'module' and n['name'] == 'a' for n in frozen['nodes'])
    assert counts and set(counts.values()) == {1}
    monkeypatch.setattr(Path, 'read_bytes', raw_read)
    assert graph_api.check_graph_file(tmp_path, 'demo', base / 'graph/req-graph.json', roots_file=roots_file) == []
    import shutil
    shutil.rmtree(plugin)
    before = (base / 'graph/req-graph.json').read_bytes()
    problems = graph_api.check_graph_file(tmp_path, 'demo', base / 'graph/req-graph.json', roots_file=roots_file)
    assert problems and any('недоступ' in p for p in problems)
    assert (base / 'graph/req-graph.json').read_bytes() == before


def test_inventory_drift_detects_add_move_and_metadata_change(tmp_path, monkeypatch):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path)
    monkeypatch.setattr(graph_api, 'validate_findings', lambda *_: [])
    graph_api.freeze_change(tmp_path, 'demo', roots_file)
    readme(core, 'new/README.md', name='new')
    problems = graph_api.check_graph_file(tmp_path, 'demo', base / 'graph/req-graph.json', roots_file=roots_file)
    assert any('новый' in p and 'new/README.md' in p for p in problems)
    graph_api.freeze_change(tmp_path, 'demo', roots_file)
    (core / 'new').rename(core / 'moved')
    problems = graph_api.check_graph_file(tmp_path, 'demo', base / 'graph/req-graph.json', roots_file=roots_file)
    assert any('удалён' in p for p in problems) and any('moved' in p for p in problems)


def test_filtered_diagram_includes_realization_ancestors_but_not_unrelated_module(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path)
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    nodes, edges = graph_api.select_diagram(graph, requirement='demo/R')
    assert {n['kind'] for n in nodes} >= {'module', 'repo', 'component', 'file'}
    assert not any(n['kind'] == 'module' and n['name'] == 'independent' for n in nodes)
    text = graph_api.diagram_text(graph, requirement='demo/R')
    assert text.startswith('requirementDiagram') and 'viewer' not in text


def test_structural_diagnostics_do_not_echo_raw_yaml_or_roots(tmp_path, monkeypatch):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path)
    monkeypatch.setattr(graph_api, 'validate_findings', lambda *_: [])
    (plugin / 'README.md').write_text('---\nname: [\nSECRET_SENTINEL\n---', encoding='utf-8')
    graph_api.freeze_change(tmp_path, 'demo', roots_file)
    text = (base / 'graph/req-graph.json').read_text(encoding='utf-8') + (base / 'graph/report.md').read_text(encoding='utf-8')
    assert 'SECRET_SENTINEL' not in text and str(tmp_path) not in text
    assert any(n['kind'] == 'module' and n['name'] == 'a' for n in json.loads((base / 'graph/req-graph.json').read_text(encoding='utf-8'))['nodes'])


def test_absolute_annotation_path_is_not_read_or_echoed(tmp_path):
    secret = tmp_path / 'SECRET_ABSOLUTE.py'  # gate-ok: synthetic disclosure-test marker
    secret.write_text('private', encoding='utf-8')
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {'files': [{'repo': 'core', 'path': str(secret)}]})
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    assert not any(e['type'] == 'implements' for e in graph['edges'])
    assert str(tmp_path) not in json.dumps(graph, ensure_ascii=False)
    assert tmp_path.as_posix() not in json.dumps(graph, ensure_ascii=False)


def test_bad_repo_record_keeps_valid_repo_without_dangling_edges(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {})
    metadata(base, {'p': [{'repo': 'core', 'root': '', 'survey': 'found'}, {'repo': 'invalid'}]})
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    ids = {n['id'] for n in graph['nodes']}
    assert any(n['kind'] == 'module' and n['name'] == 'a' for n in graph['nodes'])
    assert all(e['from'] in ids and e['to'] in ids for e in graph['edges'])


@pytest.mark.parametrize('annotation', [{}, {'modules': [{'repo': 'core', 'module': 'a'}]}])
def test_supported_v2_file_remains_unmodified_and_does_not_gain_live_modules(tmp_path, annotation):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, annotation)
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    graph.pop('structure')
    graph['format'] = 2
    graph['nodes'] = [n for n in graph['nodes'] if n['kind'] not in ('component', 'repo', 'module', 'file')]
    ids = {n['id'] for n in graph['nodes']}
    graph['edges'] = [e for e in graph['edges'] if e['from'] in ids and e['to'] in ids]
    graph['sources'] = [s for s in graph['sources'] if 'repo' not in s and s['path'] != '.openspec.yaml']
    path = base / 'v2.json'
    path.write_text(json.dumps(graph), encoding='utf-8')
    before = path.read_bytes()
    assert graph_api.check_graph_file(tmp_path, 'demo', path, roots_file=roots_file) == []
    assert path.read_bytes() == before


def test_report_distinguishes_none_and_unexamined_even_without_errors(tmp_path, monkeypatch):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {})
    monkeypatch.setattr(graph_api, 'validate_findings', lambda *_: [])
    (core / 'README.md').unlink()
    (core / 'independent/README.md').unlink()
    metadata(base, {'p': [{'repo': 'core', 'root': '', 'survey': 'none'}, {'repo': 'plugin', 'root': 'plugin/', 'survey': 'unexamined'}]})
    report = graph_api.build_report(tmp_path, 'demo', roots_file=roots_file)
    assert 'core: none' in report and 'plugin: unexamined' in report


def test_readonly_and_ordinary_readme_never_synthesizes_module(tmp_path):
    base, repo = tmp_path / 'change', tmp_path / 'repo'
    repo.mkdir()
    (repo / 'README.md').write_text('Ordinary repository description and a link to another module.', encoding='utf-8')
    metadata(base, {'p': [{'repo': 'r', 'root': '', 'survey': 'none'}]})
    before = {p: p.read_bytes() for p in [repo / 'README.md', base / '.openspec.yaml']}
    state = helper().discover(base, {'': repo})
    assert state['modules'] == [] and state['repos'][0]['actual'] == 'none'
    assert all(p.read_bytes() == data for p, data in before.items())


def test_ids_and_graph_do_not_depend_on_checkout_directory(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path)
    before = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    moved = tmp_path / 'different-checkout'
    core.rename(moved)
    roots_file.write_text(json.dumps({'': str(moved), 'plugin/': str(plugin)}), encoding='utf-8')
    assert graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file) == before


def test_filtered_dependencies_are_one_hop_and_cycles_terminate(tmp_path):
    graph_api, base, core, plugin, roots_file = graph_project(tmp_path, {'modules': [{'repo': 'core', 'module': 'a'}]})
    readme(plugin, name='b', dependencies=[{'repo': 'core', 'module': 'independent'}, {'repo': 'core', 'module': 'a'}])
    graph = graph_api.build_graph(tmp_path, 'demo', roots_file=roots_file)
    nodes, edges = graph_api.select_diagram(graph, requirement='demo/R')
    assert {n['name'] for n in nodes if n['kind'] == 'module'} == {'a', 'b'}
    assert len([e for e in edges if e['type'] == 'depends']) == 2


def test_cli_commands_use_same_explicit_roots_from_nested_cwd(tmp_path):
    _, base, core, plugin, roots_file = graph_project(tmp_path)
    cwd = tmp_path / 'elsewhere'
    cwd.mkdir()
    env = {**os.environ, 'OPENSPEC_TELEMETRY': '0', 'OPENSPEC_NO_UPDATE_CHECK': '1', 'XDG_CONFIG_HOME': str(tmp_path / 'xdg-config'), 'XDG_DATA_HOME': str(tmp_path / 'xdg-data')}
    def run(command, *args):
        result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'trace/trace_graph.py'), command, 'demo', *map(str,args), '--roots', str(roots_file)], cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
        assert result.returncode == 0, result.stderr
        return result.stdout
    graph = json.loads(run('build'))
    assert any(n['kind'] == 'module' and n['name'] == 'a' for n in graph['nodes'])
    assert 'core' in run('report')
    run('freeze')
    assert run('check', base / 'graph/req-graph.json').strip() == 'сигналов нет'
