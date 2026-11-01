#!/usr/bin/env python3
"""Fresh-workspace ownership and runtime artifact acceptance using original fixtures."""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CLI=ROOT/'scripts/catalog-release.py';cases=[]
if not CLI.exists():CLI=ROOT/'catalog-release.py'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def run(args,ok=True):
 p=subprocess.run([sys.executable,str(CLI),*map(str,args)],capture_output=True,text=True)
 assert (p.returncode==0)==ok,p.stderr
 return p
with tempfile.TemporaryDirectory(prefix='metadata-ownership-') as td:
 root=Path(td);data=root/'packages/api/data';src=root/'packages/api/src';src.mkdir(parents=True);data.mkdir()
 registry=ROOT/'packages/api/data/vertical-registry.json'
 if not registry.exists():registry=ROOT/'fixtures/vertical-registry.json'
 ids=[v['id'] for v in json.loads(registry.read_text())['verticals']]
 (data/'vertical-registry.json').write_text(json.dumps({'verticals':[{'id':v} for v in ids]}))
 imports=[];entries=[]
 for name in ids:
  folder=data/name;folder.mkdir();(folder/'items.json').write_text('[]\n')
  imports.append('import '+name+' from "../data/'+name+'/items.json" with { type: "json" }')
  if name=='tcg':
   (folder/'cards.json').write_text('[]\n');(folder/'card-shards.json').write_text('{"files":[],"totalCards":0}\n')
  files=[{'path':f.name,'bytes':f.stat().st_size,'sha256':sha(f.read_bytes())} for f in sorted(folder.iterdir())]
  manifest={'schema':'metadata.catalog/1','vertical':name,'files':files}
  raw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
  entries.append({'schema':'metadata.catalog/1','vertical':name,'repository':'metadata-fyi/data-'+name,'commit':'a'*40,'artifactUrl':'https://github.com/metadata-fyi/data-'+name+'/releases/download/fixture/catalog.tar.gz','sha256':'b'*64,'bytes':1,'sourceManifestSha256':sha(raw),'policyVersion':1})
 (src/'catalog.ts').write_text('\n'.join(imports)+'\n')
 lock=root/'catalog.lock.json';lock.write_text(json.dumps({'version':1,'datasets':entries}))
 args=['verify-workspace','--workspace',root,'--lock',lock]
 run(args);cases.append('fresh original fixture matches all sixteen locked manifests')
 subprocess.run(['git','init','-q',str(root)],check=True,capture_output=True)
 subprocess.run(['git','-C',str(root),'add','packages/api/data/anime/items.json'],check=True,capture_output=True)
 result=run(args,False);assert 'generated, not tracked' in result.stderr
 cases.append('tracked application source copy rejected')
 subprocess.run(['git','-C',str(root),'rm','--cached','packages/api/data/anime/items.json'],check=True,capture_output=True)
 run(args);assert (data/'anime/items.json').read_text()=='[]\n'
 cases.append('untracking preserves generated files and passes ownership gate')
 artifact=root/'.release/runtime-probe';private=artifact/'packages/api/data/figures/private-review.txt';private.parent.mkdir(parents=True);private.write_text('original private fixture')
 shared=artifact/'packages/api/data/_maintained/keep.json';shared.parent.mkdir();shared.write_text('[]\n')
 run(['materialize-runtime','--workspace',root,'--destination',artifact])
 assert not private.exists() and shared.exists()
 for name in ids:
  assert {f.name for f in (artifact/'packages/api/data'/name).iterdir()}=={f.name for f in (data/name).iterdir()}
  for file in (data/name).iterdir():assert (artifact/'packages/api/data'/name/file.name).read_bytes()==file.read_bytes()
 cases.append('runtime artifact contains exact source bytes and no raw vertical evidence')
 manifest=json.loads((artifact/'catalog-runtime-manifest.json').read_text());assert manifest['sourceFiles']==len(ids)+2 and manifest['verticals']==len(ids)
 cases.append('runtime source manifest records complete coverage')
 run(['materialize-runtime','--workspace',root,'--destination',root],False)
 assert (data/'anime/items.json').exists()
 cases.append('runtime preparation refuses live workspace destination')
report={'status':'passed','cases':cases,'command':'python3 '+str(Path(__file__).resolve().relative_to(ROOT)),'thirdPartyFixtures':False}
out=ROOT/'outputs/catalog-architecture/ownership-e2e.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(out.read_text())
