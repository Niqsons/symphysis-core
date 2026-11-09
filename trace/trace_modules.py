"""Portable structural declarations for the requirements graph (trace-modules).

No writes, Git calls or model decisions. YAML is optional until declarations are
present; failures carry a category, never raw input or local absolute paths.
"""
from __future__ import annotations

import hashlib
import fnmatch
import json
import re
from pathlib import Path
from urllib.parse import quote

from roots import OUTSIDE_ROOT, UNUSABLE_ROOTS, _resolve, default_roots, repo_root


class DeclarationError(ValueError):
    """An invalid/unreadable declaration; message is safe to include in diagnostics."""


STATES = ('found', 'none', 'unavailable', 'unexamined')
IMPLEMENTATION = re.compile(r'<!--\s*symphysis:implements\s+(.+?)\s*-->', re.S)


def content_hash(data: bytes) -> str:
    return hashlib.sha256(re.sub(rb'\r\n?', b'\n', data)).hexdigest()


def yaml_data(data: bytes):
    if b'\x00' in data:
        raise DeclarationError('бинарный источник')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise DeclarationError('источник не в UTF-8') from None
    try:
        import yaml
    except ImportError:
        raise DeclarationError('нет пакета PyYAML: python -m pip install pyyaml') from None
    try:
        class UniqueLoader(yaml.SafeLoader):
            pass
        def mapping(loader, node, deep=False):
            seen = set()
            for key, _ in node.value:
                if key.tag == 'tag:yaml.org,2002:merge':
                    continue
                value = loader.construct_object(key, deep=deep)
                if value in seen:
                    raise ValueError('duplicate key')
                seen.add(value)
            return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)
        UniqueLoader.add_constructor('tag:yaml.org,2002:map', mapping)
        return yaml.load(text, Loader=UniqueLoader)
    except (yaml.YAMLError, RecursionError, ValueError, TypeError):
        raise DeclarationError('негодный YAML') from None


def _name(value) -> bool:
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n\x00'):
        return False
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return not value.startswith(('/', '\\')) and not Path(value).is_absolute() and not re.match(r'^[A-Za-z]:', value)


def _relative(value) -> bool:
    return isinstance(value, str) and not value.startswith(('/', '\\')) and not Path(value).is_absolute() and not re.match(r'^[A-Za-z]:', value) and '..' not in value.replace('\\', '/').split('/')


def _ref(value, field='module') -> bool:
    return isinstance(value, dict) and _name(value.get('repo')) and _name(value.get(field))


def read_declaration(data: bytes) -> dict | None:
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise DeclarationError('источник не в UTF-8') from None
    if '\x00' in text:
        raise DeclarationError('бинарный источник')
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return None
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == '---'), None)
    if end is None:
        raise DeclarationError('frontmatter не закрыт')
    value = yaml_data('\n'.join(lines[1:end]).encode('utf-8'))
    if value is None or (isinstance(value, dict) and not {'name', 'kind'} & value.keys()):
        return None
    if not isinstance(value, dict) or not _name(value.get('name')) or value.get('kind') not in ('доменный', 'технический'):
        kind = value.get('kind') if isinstance(value, dict) else None
        detail = ': kind=' + kind[:80] if _name(kind) else ''
        raise DeclarationError('негодные name/kind модуля' + detail)
    dependencies = value.get('dependencies', [])
    if not isinstance(dependencies, list) or not all(_ref(ref) for ref in dependencies):
        raise DeclarationError('негодный список dependencies')
    return {'name': value['name'], 'kind': value['kind'],
            'dependencies': [{'repo': ref['repo'], 'module': ref['module']} for ref in dependencies]}


def read_components(change_dir: Path) -> dict:
    result = {'components': [], 'repos': [], 'signals': [], 'sources': []}
    path = change_dir / '.openspec.yaml'
    if not path.exists():
        return result
    try:
        data = path.read_bytes()
        # Legacy metadata without the extension does not require a YAML package.
        if b'x-symphysis-components' not in data:
            return result
        result['sources'].append({'path': '.openspec.yaml', 'sha256': content_hash(data)})
        raw = yaml_data(data)
        if isinstance(raw, dict) and 'x-symphysis-components' not in raw:
            return result
        components = raw.get('x-symphysis-components') if isinstance(raw, dict) else None
        if not isinstance(components, dict):
            raise DeclarationError('x-symphysis-components не объект')
        seen = set()
        for component, repos in components.items():
            if not _name(component) or not isinstance(repos, list):
                result['signals'].append({'source': '.openspec.yaml', 'reason': 'негодное объявление компонента'})
                continue
            names = []
            for item in repos:
                try:
                    if not isinstance(item, dict) or not _name(item.get('repo')) or not _relative(item.get('root')):
                        raise DeclarationError('repo требует логическое имя и переносимый псевдоним root')
                    if item['repo'] in seen:
                        duplicate = item['repo']
                        result['repos'] = [r for r in result['repos'] if r['repo'] != duplicate]
                        names[:] = [n for n in names if n != duplicate]
                        for c in result['components']:
                            c['repos'] = [n for n in c['repos'] if n != duplicate]
                        raise DeclarationError('повтор логического repo')
                    if item.get('survey', 'unexamined') not in STATES:
                        raise DeclarationError('неизвестное состояние survey')
                    exclusions = item.get('exclude', [])
                    if not isinstance(exclusions, list) or not all(_name(p) and _relative(p) for p in exclusions):
                        raise DeclarationError('негодные исключения repo')
                    if 'commit' in item and not isinstance(item['commit'], str):
                        raise DeclarationError('commit должен быть строкой')
                    seen.add(item['repo'])
                    names.append(item['repo'])
                    result['repos'].append({'repo': item['repo'], 'root': item['root'],
                                            'survey': item.get('survey', 'unexamined'), 'exclude': list(exclusions),
                                            **({'commit': item['commit']} if 'commit' in item else {})})
                except DeclarationError as error:
                    result['signals'].append({'source': '.openspec.yaml', 'reason': str(error)})
            result['components'].append({'name': component, 'repos': names})
    except (OSError, DeclarationError) as error:
        reason = str(error) if isinstance(error, DeclarationError) else 'metadata не читается'
        result['signals'].append({'source': '.openspec.yaml', 'reason': reason})
    return result


def read_implementations(text: str) -> list[tuple[int, dict]]:
    # Keep line positions while ignoring fenced examples, just as spec parsing does.
    visible, fence = [], None
    for line in text.splitlines():
        marker = re.match(r'^[ \t]{0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.fullmatch(r'[ \t]{0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}[ \t]*', line):
                fence = None
            visible.append('')
        elif marker:
            fence = marker[1]
            visible.append('')
        else:
            visible.append(line)
    text = '\n'.join(visible)
    found = []
    for match in IMPLEMENTATION.finditer(text):
        try:
            value = json.loads(match.group(1))
        except (ValueError, RecursionError):
            raise DeclarationError('негодный JSON аннотации реализации') from None
        if not isinstance(value, dict):
            raise DeclarationError('аннотация реализации не объект')
        modules, files = value.get('modules', []), value.get('files', [])
        if not isinstance(modules, list) or not all(_ref(item) for item in modules):
            raise DeclarationError('негодные modules аннотации')
        if not isinstance(files, list) or not all(_ref(item, 'path') for item in files):
            raise DeclarationError('негодные files аннотации')
        if any('module' in item and not _name(item['module']) for item in files):
            raise DeclarationError('негодный module файла аннотации')
        found.append((text[:match.start()].count('\n') + 1, {'modules': modules, 'files': files}))
    return found


SERVICE = frozenset(('.git', 'node_modules', '.symphysis'))


def _excluded(rel: str, patterns: list[str]) -> bool:
    return (bool(set(rel.split('/')) & SERVICE)
            or any(rel == p.rstrip('/') or rel.startswith(p.rstrip('/') + '/') or fnmatch.fnmatchcase(rel, p)
                   for p in patterns))


def discover(change_dir: Path, roots: dict[str, Path] | None = None, roots_file: Path | None = None) -> dict:
    """Read declarations once. The returned value is portable and JSON serializable."""
    state = read_components(change_dir)
    state.update(modules=[], inventory=[])
    if roots is None:
        try:
            roots = default_roots(roots_file, change_dir / 'decisions.json') if state['repos'] else {}
        except UNUSABLE_ROOTS:
            raise DeclarationError('файл корней не прочитан') from None
    for repo in state['repos']:
        name, alias = repo['repo'], repo['root']
        errors = []
        def signal(source, reason):
            errors.append(reason)
            state['signals'].append({'source': f'{name}/{source}', 'reason': reason})
        try:
            folder = repo_root(alias, roots)
        except (OSError, RuntimeError, ValueError):
            folder = None
        if folder is None:
            repo['actual'], repo['availability'] = 'unavailable', 'unavailable'
            signal('.', 'псевдоним корня отсутствует' if alias not in roots else 'репозиторий недоступен')
            continue
        exclusions = [p.replace('\\', '/').strip('/') for p in repo['exclude']]
        stack, visited, found = [folder], set(), []
        while stack:
            directory = stack.pop()
            try:
                canonical = directory.resolve()
                if not canonical.is_relative_to(folder):
                    signal(directory.name, 'источник вне разрешённого корня')
                    continue
                rel_dir = canonical.relative_to(folder).as_posix()
                if canonical in visited or _excluded(rel_dir, exclusions):
                    continue
                visited.add(canonical)
                entries = sorted(canonical.iterdir(), key=lambda p: p.name)
            except (OSError, RuntimeError, ValueError):
                signal(directory.name, 'каталог не читается')
                continue
            for entry in entries:
                logical_rel = entry.relative_to(folder).as_posix()
                if _excluded(logical_rel, exclusions):
                    continue
                try:
                    target = _resolve(logical_rel, {'': folder})
                    if target is OUTSIDE_ROOT or target is None:
                        signal(logical_rel, 'источник вне разрешённого корня')
                        continue
                    rel = target.relative_to(folder).as_posix()
                    if _excluded(rel, exclusions):
                        continue
                    if target.is_dir():
                        stack.append(target)
                        continue
                    if entry.name != 'README.md':
                        continue
                    data = target.read_bytes()
                    item = {'repo': name, 'path': rel, 'sha256': content_hash(data)}
                    if any(r['repo'] == name and r['path'] == rel for r in state['inventory']):
                        continue
                    state['inventory'].append(item)
                    state['sources'].append(dict(item))
                    declaration = read_declaration(data)
                    if declaration is not None:
                        found.append({**declaration, 'repo': name, 'path': target.parent.relative_to(folder).as_posix(),
                                      'source': rel, 'line': 2})
                except DeclarationError as error:
                    signal(logical_rel, str(error))
                except (OSError, RuntimeError, ValueError):
                    signal(logical_rel, 'источник не читается')
        state['modules'].extend(found)
        repo['actual'] = 'unexamined' if errors else ('found' if found else 'none')
        repo['availability'] = 'partial' if errors else 'available'
        if repo['survey'] != repo['actual']:
            state['signals'].append({'source': name, 'reason': f'результат обследования {repo["survey"]}; новое чтение {repo["actual"]}'})
        by_name = {}
        for item in found:
            by_name.setdefault(item['name'], []).append(item['source'])
        for duplicate, places in by_name.items():
            if len(places) > 1:
                state['signals'].append({'source': name, 'reason': 'неоднозначный модуль ' + duplicate + ': ' + ', '.join(sorted(places))})
    state['modules'].sort(key=lambda m: (m['repo'], m['path'], m['name']))
    state['inventory'].sort(key=lambda m: (m['repo'], m['path']))
    return state


def module(state: dict, repo: str, name: str) -> dict | None:
    matches = [m for m in state['modules'] if m['repo'] == repo and m['name'] == name]
    return matches[0] if len(matches) == 1 else None


def owner(state: dict, repo: str, path: str) -> dict | None:
    path = path.replace('\\', '/')
    if '..' in path.split('/') or Path(path).is_absolute():
        return None
    matches = [m for m in state['modules'] if m['repo'] == repo and
               (m['path'] == '.' or path.startswith(m['path'].rstrip('/') + '/'))]
    if not matches:
        return None
    nearest = max(matches, key=lambda m: len(m['path']))
    return nearest if module(state, repo, nearest['name']) is not None else None


def structural_id(kind: str, *parts: str) -> str:
    return kind + ':' + '/'.join(quote(p, safe='') for p in parts)


def attach_structure(graph: dict, state: dict, roots: dict[str, Path], annotations: list) -> None:
    """Join already-read structure and requirement declarations, without re-reading README."""
    nodes = {n['id']: n for n in graph['nodes']}
    repos = {r['repo']: r for r in state['repos']}
    def node(kind, name, at, *parts, **extra):
        ident = structural_id(kind, *parts)
        if ident not in nodes:
            nodes[ident] = {'id': ident, 'kind': kind, 'name': name, 'at': at, **extra}
            graph['nodes'].append(nodes[ident])
        return ident
    def edge(source, target, kind, at):
        item = {'from': source, 'to': target, 'type': kind, 'at': at}
        if item not in graph['edges']:
            graph['edges'].append(item)
    def issue(at, reason):
        state['signals'].append({'kind': 'link', 'source': at, 'reason': reason})
    for component in state['components']:
        c = node('component', component['name'], '.openspec.yaml:1', component['name'])
        for name in component['repos']:
            repo = repos[name]
            r = node('repo', name, '.openspec.yaml:1', name, survey=repo['survey'], actual=repo['actual'], availability=repo['availability'])
            edge(c, r, 'contains', '.openspec.yaml:1')
    for item in state['modules']:
        if module(state, item['repo'], item['name']) is not item:
            continue
        at = item['repo'] + '/' + item['source'] + ':' + str(item['line'])
        m = node('module', item['name'], at, item['repo'], item['name'], repo=item['repo'], path=item['path'], module_kind=item['kind'])
        edge(structural_id('repo', item['repo']), m, 'contains', at)

    def file_node(repo, rel, at):
        ident = node('file', rel, at, repo, rel, repo=repo, path=rel)
        belonging = owner(state, repo, rel)
        parent = structural_id('module', repo, belonging['name']) if belonging else structural_id('repo', repo)
        edge(parent, ident, 'contains', at)
        return ident

    for item in state['modules']:
        source = item['repo'] + '/' + item['source'] + ':' + str(item['line'])
        file_node(item['repo'], item['source'], source)
        m = module(state, item['repo'], item['name'])
        if m is not item:
            continue
        for dep in item['dependencies']:
            target = module(state, dep['repo'], dep['module'])
            if target is None:
                issue(source, 'зависимость не разрешена: ' + dep['repo'] + '/' + dep['module'])
            else:
                edge(structural_id('module', item['repo'], item['name']), structural_id('module', dep['repo'], dep['module']), 'depends', source)

    for requirement, at, declaration in annotations:
        for ref in declaration['modules']:
            m = module(state, ref['repo'], ref['module'])
            if m is None:
                issue(at, 'реализация не разрешена: ' + ref['repo'] + '/' + ref['module'])
            else:
                edge(structural_id('module', m['repo'], m['name']), requirement, 'implements', at)
        for ref in declaration['files']:
            repo, path = ref['repo'], ref['path'].replace('\\', '/')
            config = repos.get(repo)
            try:
                folder = repo_root(config['root'], roots) if config else None
                target = _resolve(path, {'': folder}) if folder else None
                if target is None or target is OUTSIDE_ROOT or not target.is_file():
                    issue(at, 'файл реализации не разрешён внутри repo')
                    continue
                rel = target.relative_to(folder).as_posix()
                belonging = owner(state, repo, rel)
                if 'module' in ref and (not belonging or belonging['name'] != ref['module']):
                    issue(at, 'противоречие модуля и файла реализации: ' + repo + '/' + path)
                    continue
                f = file_node(repo, rel, at)
                edge(f, requirement, 'implements', at)
                if belonging:
                    edge(structural_id('module', repo, belonging['name']), requirement, 'implements', at)
            except (OSError, RuntimeError, ValueError):
                issue(at, 'файл реализации не читается внутри repo')
