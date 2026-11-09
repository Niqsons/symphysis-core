"""Verify real module dogfood, task/scenario links and all accepted Specify outcomes."""
import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'trace/trace_graph.py').is_file())
OUT = Path(__file__).resolve().parent
CHANGE = OUT.parent
sys.path[:0] = [str(ROOT / p) for p in ('trace', 'roots', 'decisions', 'openspec-run')]
import trace_graph


def main():
    roots = CHANGE / 'probes/journal-roots.json'
    graph, duplicates, unresolved = trace_graph.build_graph_with_signals(ROOT, 'trace-modules', roots_file=roots)
    context = trace_graph.signal_context(ROOT, 'trace-modules', roots_file=roots, structure=graph['structure'])
    signals = trace_graph.graph_signals(graph, duplicates, unresolved, context)
    assert not duplicates and not unresolved
    assert len(signals) == 3
    assert sum('критерий без требования: F-03 ' in s for s in signals) == 1
    assert sum('критерий без требования: F-06 ' in s for s in signals) == 1
    assert sum('требование без записи: repository-survey/Структурные источники остаются внутри разрешённого корня' in s for s in signals) == 1
    specified = [r['id'] for r in context['records'] if (r.get('outcome') or {}).get('value') == 'Specify']
    assert len(specified) == 13
    assert all(int(re.search(r'\d+', n).group()) in context['marks'] for n in specified)
    scenarios = [n for n in graph['nodes'] if n['kind'] == 'scn']
    covered = {e['to'] for e in graph['edges'] if e['type'] == 'satisfies' and e['from'].startswith('task:')}
    needed = [n for n in scenarios if n['requirement'] not in context['modified'] or
              context['modified'][n['requirement']]['scenarios'].get(n['id']) in ('new', 'changed')]
    assert all(n['id'] in covered for n in needed)
    modules = [n for n in graph['nodes'] if n['kind'] == 'module']
    assert len(modules) == 16
    implementations = [e for e in graph['edges'] if e['type'] == 'implements']
    assert {e['from'] for e in implementations} == {'module:symphysis-core/trace', 'module:symphysis-core/roots'}
    assert {e['to'] for e in implementations} == {'req:trace-graph/Граф собирается из файлов изменения'}
    assert any(e['type'] == 'depends' and e['from'] == 'module:symphysis-core/trace' and
               e['to'] == 'module:symphysis-core/roots' and e['at'].startswith('symphysis-core/trace/README.md:') for e in graph['edges'])
    counts = {kind: sum(n['kind'] == kind for n in graph['nodes']) for kind in ('req', 'scn', 'task', 'module')}
    results = {'counts': counts, 'scenarios_requiring_tasks': len(needed), 'all_required_scenarios_covered': True,
               'Specify': specified, 'real_implementations': implementations, 'signals': signals,
               'dispositions': {
                   'F-03': 'Обобщённый критерий реализован требованиями trace-conventions/module-discovery и задачами 3.4/4.x; нет прямой ссылки F-03 в тексте требования. Семантическое покрытие проверено build/installed-results.',
                   'F-06': 'Критерий приёмки на самом Symphysis, закрывается 9.1 и этой проверкой 16 реальных модулей/2 implements, не отдельное поведение продукта.',
                   'repository-survey/Структурные источники остаются внутри разрешённого корня': 'Канон ИБ F-46; отдельное решение владельца не создавалось. Security и реальные junction/отрицательные тесты подтверждают требование.'}}
    (OUT / 'plan-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Plan/dogfood verified:', counts, '; Specify 13/13; known graph signals 3, all explained.')


if __name__ == '__main__':
    main()
