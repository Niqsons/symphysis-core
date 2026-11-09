import hashlib, json, os, shutil, subprocess
from pathlib import Path
from tempfile import mkdtemp

repo=Path('X:/symphysis')
probe=Path(mkdtemp(prefix='global-store-', dir='X:/codex-tmp'))
cli=repo/'upstream/openspec/bin/openspec.js'
env=dict(os.environ)
for key, name in [('TEMP','tmp'),('TMP','tmp'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('HOME','home'),('USERPROFILE','home'),('APPDATA','appdata'),('LOCALAPPDATA','localappdata'),('CODEX_HOME','home/.codex'),('CLAUDE_CONFIG_DIR','home/.claude')]:
    env[key]=str(probe/name); Path(env[key]).mkdir(parents=True, exist_ok=True)
env.update(OPENSPEC_TELEMETRY='0',OPENSPEC_NO_UPDATE_CHECK='1',OPENSPEC_NO_COMPLETIONS='1',NO_COLOR='1',CI='1')
rows=[]
def run(args,cwd=None):
    p=subprocess.run(['node',str(cli),*args],cwd=cwd or probe,env=env,capture_output=True,text=True,encoding='utf-8',timeout=50)
    row={'cmd':'openspec '+' '.join(args),'cwd':str(cwd or probe),'code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    rows.append(row)
    print(row['cmd'],'code='+str(p.returncode),flush=True)
    return p

store=probe/'team-store'; source=probe/'source-repo'; source.mkdir()
run(['store','setup','probe-store','--path',str(store),'--no-init-git','--json'])
run(['context','--json'],store)
run(['init',str(source),'--tools','claude,opencode,codex','--no-animation','--force'])
run(['update',str(source),'--dry-run','--json'])
run(['init',str(source),'--tools','claude','--global'])
run(['update',str(source),'--global','--dry-run','--json'])
run(['list','--store','probe-store','--json'],source)
(source/'openspec/config.yaml').write_text('store: probe-store\nschema: cwd-only\n',encoding='utf-8')
run(['context','--json'],source)
run(['new','change','pointer-demo','--schema','spec-driven','--json'],source)
run(['schema','which','symphysis','--json'],store)
user_schema=probe/'data/openspec/schemas/symphysis'
shutil.copytree(repo/'openspec/schemas/symphysis',user_schema)
run(['schema','which','symphysis','--json'],store)
run(['new','change','global-demo','--schema','symphysis','--json'],source)
run(['instructions','intent','--change','global-demo','--json'],source)
shutil.copytree(repo/'openspec/schemas/symphysis',store/'openspec/schemas/symphysis')
run(['schema','which','symphysis','--json'],store)
clone=probe/'cloned-store'; shutil.copytree(store,clone)
run(['store','register',str(clone),'--id','probe-clone','--json'])
run(['config','set','defaultStore','probe-store'])
outside=probe/'outside'; outside.mkdir()
run(['context','--json'],outside)
files=[str(p.relative_to(probe)) for p in probe.rglob('*') if p.is_file() and not any(x in p.parts for x in ('schemas','changes'))]
record={'probe':str(probe),'cli_sha256':hashlib.sha256(cli.read_bytes()).hexdigest(),'runs':rows,'files':files}
(probe/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
Path('X:/codex-tmp/global-store-probe-location.txt').write_text(str(probe),encoding='utf-8')
print('RESULTS '+str(probe/'results.json'))
