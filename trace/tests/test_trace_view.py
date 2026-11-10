"""Просмотр графа и соответствие Mermaid-элементов исходным узлам."""
import copy
import json

import pytest

from conftest import ROOT
import trace_graph
from test_trace_diagram import graph_of, node
from test_trace_graph import CHANGE, make_change, run


def test_render_view_keeps_canonical_identity_after_label_cleanup():
    """Сокращённые и совпадающие подписи ведут к разным исходным узлам."""
    common = 'Общее "имя" <b>с разметкой</b> ' * 12
    nodes = [node('req', common, 'req:a/first', capability='a', section='ADDED', at='specs/a/spec.md:4'),
             node('req', common, 'req:b/second', capability='b', section='ADDED', at='specs/b/spec.md:9'),
             node('rec', common, 'rec:F-22', number=22, at='decisions.json:12')]
    original = copy.deepcopy(nodes)
    assert callable(getattr(trace_graph, 'render_view', None)), 'render_view должен возвращать текст и карту'
    result = trace_graph.render_view(nodes, [])
    assert result['text'].startswith('requirementDiagram\n')
    assert [value['id'] for value in result['elements'].values()] == ['req:a/first', 'req:b/second', 'rec:F-22']
    assert [value['at'] for value in result['elements'].values()] == ['specs/a/spec.md:4', 'specs/b/spec.md:9', 'decisions.json:12']
    assert len(result['elements']) == 3
    for label in result['elements']:
        assert len(label) <= 90
        assert '"' not in label and '<' not in label
        assert f'"{label}" {{' in result['text']
    assert nodes == original


def test_view_cli_reads_live_source_without_writing_graph(tmp_path):
    root, base = make_change(tmp_path, journal=['F-01'], specs={'a': '## ADDED Requirements\n### Requirement: R\nSHALL. (F-01)\n#### Scenario: S\n- **WHEN** a\n- **THEN** b\n'})
    (base / 'proposal.md').write_text('### New Capabilities\n- `a`: demo\n', encoding='utf-8')
    before = {p.relative_to(base): p.read_bytes() for p in base.rglob('*') if p.is_file()}
    result = run('view', CHANGE, '--requirement', 'req:a/R', cwd=root)
    assert result.returncode == 0, result.stderr
    view = json.loads(result.stdout)
    assert view['view_format'] == 1
    assert view['source']['kind'] == 'live' and view['source']['preliminary']
    assert {n['id'] for n in view['elements'].values()} >= {'req:a/R', 'scn:a/R/S', 'rec:F-01'}
    assert {p.relative_to(base): p.read_bytes() for p in base.rglob('*') if p.is_file()} == before


def test_view_without_selection_returns_choices_without_diagram():
    graph = graph_of([node('cap', 'a', 'cap:a'), node('req', 'R', 'req:a/R', capability='a', section='ADDED')])
    assert callable(getattr(trace_graph, 'graph_view', None)), 'нужен выбор части для просмотра'
    view = trace_graph.graph_view(graph)
    assert view['text'] is None and view['elements'] == {}
    assert view['choices']['requirements'] == [{'id': 'req:a/R', 'name': 'R', 'capability': 'a'}]


def module_graph():
    nodes = [node('cap', 'a', 'cap:a'), node('cap', 'b', 'cap:b'),
             node('req', 'R', 'req:a/R', capability='a', section='ADDED'),
             node('req', 'Q', 'req:b/Q', capability='b', section='ADDED'),
             node('scn', 'S', 'scn:a/R/S', capability='a', requirement='req:a/R'),
             node('module', 'trace', 'module:one/trace', repo='one'),
             node('module', 'trace', 'module:two/trace', repo='two'),
             node('module', 'empty', 'module:one/empty', repo='one'),
             node('file', 'a.py', 'file:one/a.py', repo='one'), node('rec', 'D', 'rec:F-01', number=1)]
    edges = [{'from': a, 'to': b, 'type': kind} for a, b, kind in [
        ('cap:a', 'req:a/R', 'contains'), ('cap:b', 'req:b/Q', 'contains'),
        ('scn:a/R/S', 'req:a/R', 'verifies'), ('req:a/R', 'rec:F-01', 'traces'),
        ('module:one/trace', 'req:a/R', 'implements'), ('module:two/trace', 'req:a/R', 'implements'),
        ('module:one/trace', 'file:one/a.py', 'contains'), ('file:one/a.py', 'req:b/Q', 'implements')]]
    return graph_of(nodes, edges)


def test_module_view_includes_file_implementation_and_coimplementation():
    view = trace_graph.graph_view(module_graph(), module='one/trace')
    assert {n['id'] for n in view['elements'].values()} >= {'req:a/R', 'req:b/Q', 'module:two/trace', 'scn:a/R/S', 'rec:F-01'}
    narrow = trace_graph.graph_view(module_graph(), module='two/trace', capability='a')
    assert 'req:b/Q' not in {n['id'] for n in narrow['elements'].values()}


def test_module_filter_keeps_requirement_candidates_outside_implements_out():
    graph = module_graph()
    graph['candidates'] = [{'a': 'req:a/R', 'b': 'req:b/Q', 'source': 'records', 'shared': ['F-01']}]
    view = trace_graph.graph_view(graph, module='two/trace', capability='a')
    shown = {n['id'] for n in view['elements'].values()}
    assert 'req:a/R' in shown and 'module:one/trace' in shown
    assert 'req:b/Q' not in shown


@pytest.mark.parametrize('module,capability', [('one/empty', None), ('two/trace', 'b')])
def test_existing_module_with_no_requirements_is_explicitly_empty(module, capability):
    view = trace_graph.graph_view(module_graph(), module=module, capability=capability)
    assert view['text'] is None and view['elements'] == {} and view['empty']
    assert view['selection']['module'] == module


@pytest.mark.parametrize('selection', [{'module': 'missing/trace'}, {'requirement': 'req:a/gone'}, {'capability': 'gone'}])
def test_missing_selection_is_refused(selection):
    with pytest.raises(trace_graph.Refusal):
        trace_graph.graph_view(module_graph(), **selection)


def test_linked_only_counts_structural_edges_and_keeps_diagnostics_and_scope():
    graph = module_graph()
    graph['nodes'].append(node('req', 'Isolated', 'req:a/I', capability='a', section='ADDED'))
    diagnostics = [{'kind': 'unresolved', 'at': 'specs/a/spec.md:3', 'reason': 'missing'}]
    full = trace_graph.graph_view(graph, capability='a', diagnostics=diagnostics)
    filtered = trace_graph.graph_view(graph, capability='a', linked_only=True, diagnostics=diagnostics)
    assert 'req:a/I' in {n['id'] for n in full['elements'].values()}
    assert 'req:a/I' not in {n['id'] for n in filtered['elements'].values()}
    assert 'cap:a' in {n['id'] for n in filtered['elements'].values()}
    assert full['diagnostics'] == filtered['diagnostics']
    assert full['diagnostics'] == diagnostics + [{'kind': 'structure', 'at': '', 'reason': 'структурные данные отсутствуют'}]
    assert full['unlinked'] == filtered['unlinked']
    assert 'req:b/Q' in {n['id'] for n in full['unlinked']['items']}
    assert full['unlinked']['scope'] == 'change'


def test_all_isolated_nodes_become_empty_and_can_be_restored():
    graph = graph_of([node('req', 'R', 'req:a/R', capability='a', section='ADDED')])
    assert trace_graph.graph_view(graph, requirement='req:a/R', linked_only=True)['empty']
    assert not trace_graph.graph_view(graph, requirement='req:a/R')['empty']


@pytest.mark.parametrize('raw', [b'', b'{"format":', b'\xff', b'\x00\x01', b'{}', b'[]'])
def test_invalid_snapshot_refuses_without_live_fallback(tmp_path, raw):
    root, base = make_change(tmp_path)
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_bytes(raw)
    result = run('view', CHANGE, '--snapshot', str(snapshot), cwd=root)
    assert result.returncode == 1 and result.stdout == '' and 'Traceback' not in result.stderr


@pytest.mark.parametrize('version', [2, 3])
def test_snapshot_view_keeps_historical_structure_and_marks_missing_structure(tmp_path, version):
    root, base = make_change(tmp_path)
    graph = module_graph()
    graph.update(format=version, sources=[])
    if version == 3:
        graph['structure'] = {'repos': [{'repo': 'one', 'survey': 'unexamined', 'availability': 'unavailable'}], 'modules': [], 'signals': []}
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps(graph), encoding='utf-8')
    result = run('view', CHANGE, '--snapshot', str(snapshot), '--module', 'one/trace', cwd=root)
    assert result.returncode == 0, result.stderr
    view = json.loads(result.stdout)
    assert view['source']['kind'] == 'snapshot'
    assert 'module:two/trace' in {n['id'] for n in view['elements'].values()}
    assert view['incomplete'] and view['diagnostics']


@pytest.mark.parametrize('missing', [True, False])
def test_live_view_requires_requirements_for_every_proposed_capability(tmp_path, missing):
    root, base = make_change(tmp_path, specs={'a': '### Requirement: R\nSHALL.\n'})
    (base / 'proposal.md').write_text('### New Capabilities\n- `a`: one\n- `b`: two\n', encoding='utf-8')
    if not missing:
        (base / 'specs' / 'b').mkdir()
        (base / 'specs' / 'b' / 'spec.md').write_text('# Empty\n', encoding='utf-8')
    result = run('view', CHANGE, cwd=root)
    assert result.returncode == 1 and result.stdout == ''


def test_live_view_diagnoses_duplicates_and_unresolved_references(tmp_path):
    root, base = make_change(tmp_path, journal=['F-01'], specs={'a': '## ADDED Requirements\n### Requirement: R\nSHALL. (F-99)\n### Requirement: R\nSHALL.\n'})
    (base / 'proposal.md').write_text('### New Capabilities\n- `a`: demo\n', encoding='utf-8')
    result = run('view', CHANGE, '--capability', 'a', cwd=root)
    assert result.returncode == 0, result.stderr
    view = json.loads(result.stdout)
    assert {'duplicate', 'unresolved'} <= {item['kind'] for item in view['diagnostics']}


def test_view_targets_use_trusted_roots_and_ignore_snapshot_target_fields(tmp_path):
    root, base = make_change(tmp_path)
    (base / 'specs/a').mkdir(parents=True)
    (base / 'specs/a/spec.md').write_text('target\n', encoding='utf-8')
    graph = graph_of([node('req', 'R', 'req:a/R', capability='a', section='ADDED', at='specs/a/spec.md:1',
                           target={'file': str(tmp_path / 'outside'), 'root': str(tmp_path)})])
    graph.update(format=3, sources=[])
    snapshot = base / 'graph/req-graph.json'
    snapshot.parent.mkdir()
    snapshot.write_text(json.dumps(graph), encoding='utf-8')
    result = run('view', CHANGE, '--snapshot', str(snapshot), '--requirement', 'req:a/R', cwd=root)
    assert result.returncode == 0, result.stderr
    target = next(iter(json.loads(result.stdout)['elements'].values()))['target']
    assert target['file'] == str((base / 'specs/a/spec.md').resolve())
    assert target['root'] == str(root.resolve()) and target['line'] == 1


@pytest.mark.parametrize('at', ['../outside.md:1', '..\\outside.md:1', '/outside.md:1', 'Z:/outside.md:1', '//host/share/file:1'])
def test_snapshot_paths_do_not_escape_project(tmp_path, at):
    root, base = make_change(tmp_path)
    graph = graph_of([node('req', 'R', 'req:a/R', capability='a', section='ADDED', at=at)])
    graph.update(format=3, sources=[])
    snapshot = base / 'snapshot.json'
    snapshot.write_text(json.dumps(graph), encoding='utf-8')
    result = run('view', CHANGE, '--snapshot', str(snapshot), '--requirement', 'req:a/R', cwd=root)
    assert result.returncode == 0, result.stderr
    assert 'target' not in next(iter(json.loads(result.stdout)['elements'].values()))


@pytest.mark.parametrize('mutation', [
    {'format': 1}, {'nodes': [None]}, {'nodes': [node('task', 'T', 'broken')]},
    {'nodes': [node('rec', 'D', 'rec:F-01', number='"\n%%{init: {}}%%')]},
    {'edges': [{'from': 'missing', 'to': 'req:a/R', 'type': 'traces'}]},
    {'candidates': [None]}, {'structure': {'repos': [None]}},
])
def test_snapshot_rejects_malformed_render_data_without_traceback(tmp_path, mutation):
    root, base = make_change(tmp_path)
    graph = graph_of([node('req', 'R', 'req:a/R', capability='a', section='ADDED')])
    graph.update(format=3, sources=[])
    graph.update(mutation)
    file = base / 'snapshot.json'
    file.write_text(json.dumps(graph), encoding='utf-8')
    result = run('view', CHANGE, '--snapshot', str(file), cwd=root)
    assert result.returncode == 1 and result.stdout == '' and 'Traceback' not in result.stderr


def test_live_view_refuses_binary_artifact(tmp_path):
    root, base = make_change(tmp_path, specs={'a': '## ADDED Requirements\n### Requirement: R\nSHALL.\n'})
    (base / 'proposal.md').write_text('### New Capabilities\n- `a`: demo\n', encoding='utf-8')
    (base / 'tasks.md').write_bytes(b'\x00not text')
    result = run('view', CHANGE, cwd=root)
    assert result.returncode == 1 and result.stdout == ''


def test_view_keeps_existing_frozen_files_unchanged(tmp_path):
    root, base = make_change(tmp_path, specs={'a': '## ADDED Requirements\n### Requirement: R\nSHALL.\n'})
    (base / 'proposal.md').write_text('### New Capabilities\n- `a`: demo\n', encoding='utf-8')
    (base / 'graph').mkdir()
    (base / 'graph/req-graph.json').write_text('{}', encoding='utf-8')
    (base / 'graph/report.md').write_text('existing', encoding='utf-8')
    result = run('view', CHANGE, '--requirement', 'req:a/R', cwd=root)
    assert result.returncode == 0, result.stderr
    assert (base / 'graph/req-graph.json').read_text(encoding='utf-8') == '{}'
    assert (base / 'graph/report.md').read_text(encoding='utf-8') == 'existing'


def test_snapshot_module_target_opens_only_configured_external_repo(tmp_path):
    root, base = make_change(tmp_path)
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'README.md').write_text('module\n', encoding='utf-8')
    graph = module_graph()
    graph.update(format=3, sources=[], structure={'repos': [{'repo': 'one', 'root': 'one/', 'survey': 'found', 'availability': 'available'}]})
    next(n for n in graph['nodes'] if n['id'] == 'module:one/trace')['at'] = 'one/README.md:1'
    snapshot = base / 'snapshot.json'
    snapshot.write_text(json.dumps(graph), encoding='utf-8')
    roots = tmp_path / 'roots.json'
    roots.write_text(json.dumps({'': str(root), 'one/': str(external)}), encoding='utf-8')
    result = run('view', CHANGE, '--snapshot', str(snapshot), '--module', 'one/trace', '--roots', str(roots), cwd=root)
    assert result.returncode == 0, result.stderr
    target = next(n for n in json.loads(result.stdout)['elements'].values() if n['id'] == 'module:one/trace')['target']
    assert target['file'] == str((external / 'README.md').resolve())
    assert target['root'] == str(external.resolve())


def test_unknown_repo_does_not_fall_back_to_change_relative_file(tmp_path):
    root, base = make_change(tmp_path)
    (base / 'one').mkdir()
    (base / 'one/README.md').write_text('not a repo\n', encoding='utf-8')
    graph = module_graph()
    graph.update(format=3, sources=[])
    next(n for n in graph['nodes'] if n['id'] == 'module:one/trace')['at'] = 'one/README.md:1'
    snapshot = base / 'snapshot.json'
    snapshot.write_text(json.dumps(graph), encoding='utf-8')
    result = run('view', CHANGE, '--snapshot', str(snapshot), '--module', 'one/trace', cwd=root)
    assert result.returncode == 0, result.stderr
    target = next(n for n in json.loads(result.stdout)['elements'].values() if n['id'] == 'module:one/trace')
    assert 'target' not in target
