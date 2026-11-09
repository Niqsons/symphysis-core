"""Audited I/O for isolated model probes; emitted input pages are the evidence."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True, type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    read = sub.add_parser('read')
    read.add_argument('path')
    read.add_argument('--offset', type=int, default=0)
    run = sub.add_parser('run')
    run.add_argument('command', choices=['build', 'anchor'])
    args = parser.parse_args()
    case = args.case.resolve()
    assert case.name in ('trial-1', 'trial-2') and case.parent.name == 'model-probes'
    project = case / 'project'
    if args.action == 'read':
        path = (case / args.path).resolve()
        allowed = [project, case / 'core', case / 'plugin', case / 'empty', case / 'new', case / 'concurrent']
        if not any(path.is_relative_to(folder) for folder in allowed) or path.name == 'roots.json':
            event = {'action':'denied','path':'outside allowed inputs'}
        else:
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            event = {'action':'read','path':path.relative_to(case).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),
                     'offset':args.offset,'total_chars':len(text),'emitted_text':text[args.offset:args.offset+4000]}
    else:
        tools = project / '.symphysis/tools'
        command = ([sys.executable,'-X','utf8',str(tools/'trace_graph.py'),'build','model-probe','--roots',str(case/'roots.json')]
                   if args.command=='build' else [sys.executable,'-X','utf8',str(tools/'anchor_refs.py'),'model-probe'])
        completed = subprocess.run(command,cwd=project,capture_output=True,text=True,encoding='utf-8',timeout=60)
        emitted = completed.stdout
        if args.command=='build' and completed.returncode==0:
            graph=json.loads(emitted)
            emitted=json.dumps({'format':graph['format'],'structure':graph.get('structure'),
                                'implements':[e for e in graph['edges'] if e['type']=='implements']},ensure_ascii=False)
        event={'action':'run','command':args.command,'code':completed.returncode,'emitted_text':emitted,
               'stderr':completed.stderr}
    # Normalize only the case directory; source text and observed values remain intact.
    event=json.loads(json.dumps(event,ensure_ascii=False).replace(str(case).replace(chr(92),chr(92)*2),'<case>').replace(case.as_posix(),'<case>'))
    with (case/'io-events.jsonl').open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(event,ensure_ascii=False)+'\n')
    print(json.dumps(event,ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
