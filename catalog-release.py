#!/usr/bin/env python3
"""Immutable catalog inventory, packaging and verified cache preparation (stdlib only)."""
import argparse, hashlib, json, os, re, shutil, subprocess, tarfile, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 8 * 1024**3
SCHEMA = 'metadata.catalog/1'
def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
def sources(root):
    data = root/'packages/api/data'
    registry = json.loads((data/'vertical-registry.json').read_text())
    found = {v['id']: set() for v in registry['verticals']}
    for source in (root/'packages/api/src').glob('*.ts'):
        for vertical, name in re.findall(r"\.\./data/([a-z]+)/([a-z0-9-]+\.json)", source.read_text()):
            if vertical in found: found[vertical].add(name)
    tcg = json.loads((data/'tcg/card-shards.json').read_text())
    found['tcg'].update(['cards.json','card-shards.json', *tcg['files']])
    for vertical, files in found.items():
        for name in files:
            if Path(name).name != name or not (data/vertical/name).is_file(): raise ValueError('invalid source '+name)
    return found

def inventory(root, output=None):
    result = {'schema': SCHEMA, 'verticals': []}
    for vertical, names in sources(root).items():
        files = []
        for name in sorted(names):
            p = root/'packages/api/data'/vertical/name
            files.append({'path':name,'bytes':p.stat().st_size,'sha256':digest(p)})
        result['verticals'].append({'id':vertical,'repository':'metadata-fyi/data-'+vertical,
          'files':files,'bytes':sum(f['bytes'] for f in files),
          'publicExport':{'status':'blocked','reason':'Per-record metadata and media permission evidence not yet recorded'},
          'excluded':'Raw snapshots, evidence, reports, runtime state and local image binaries'})
    if output is not None: write(output,result)
    return result

def pack(root, vertical, output):
    names = sources(root)[vertical]
    manifest={'schema':SCHEMA,'vertical':vertical,'files':[]}
    for name in sorted(names):
        p=root/'packages/api/data'/vertical/name
        manifest['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':digest(p)})
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        mp=Path(td)/'source-manifest.json'; write(mp,manifest)
        with tarfile.open(output,'w:gz') as archive:
            archive.add(mp,arcname='source-manifest.json')
            for name in sorted(names): archive.add(root/'packages/api/data'/vertical/name,arcname='data/'+name)
        return {'schema':SCHEMA,'vertical':vertical,'sha256':digest(output),'bytes':output.stat().st_size,
                'sourceManifestSha256':digest(mp),'files':len(names)}

def validate_entry(entry):
    vertical=entry['vertical']
    if not re.fullmatch(r'[a-z]+',vertical): raise ValueError('invalid vertical')
    if entry['repository']!='metadata-fyi/data-'+vertical: raise ValueError('repository mismatch')
    if not re.fullmatch(r'[0-9a-f]{40}',entry['commit']): raise ValueError('full commit required')
    if entry['schema']!=SCHEMA or entry['policyVersion']!=1: raise ValueError('schema/policy mismatch')
    for key in ('sha256','sourceManifestSha256'):
        if not re.fullmatch(r'[0-9a-f]{64}',entry[key]): raise ValueError('invalid digest')
    if not isinstance(entry['bytes'],int) or not 0<entry['bytes']<=MAX_BYTES: raise ValueError('invalid size')
    url=entry['artifactUrl']
    if not url.startswith('https://github.com/'+entry['repository']+'/releases/download/'): raise ValueError('untrusted artifact URL')

def verify_directory(directory, entry):
    if directory.is_symlink() or any(p.is_symlink() for p in directory.rglob('*')): raise ValueError('cache symlinks are forbidden')
    mp=directory/'source-manifest.json'
    if digest(mp)!=entry['sourceManifestSha256']: raise ValueError('source manifest mismatch')
    manifest=json.loads(mp.read_text())
    if manifest['schema']!=entry['schema'] or manifest['vertical']!=entry['vertical']: raise ValueError('source schema mismatch')
    paths=set()
    total=0
    for item in manifest['files']:
        name=item['path']
        if Path(name).name!=name or name in paths: raise ValueError('invalid/duplicate source path')
        paths.add(name); p=directory/'data'/name
        if p.is_symlink() or not p.is_file() or p.stat().st_size!=item['bytes'] or digest(p)!=item['sha256']: raise ValueError('source integrity mismatch')
        total+=item['bytes']
        if total>MAX_BYTES: raise ValueError('source limit exceeded')
    actual={str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}
    if actual!={'source-manifest.json',*('data/'+p for p in paths)}: raise ValueError('unlisted content')
    return manifest

def resolve(lock_path, cache, artifact_directory=None):
    lock=json.loads(lock_path.read_text())
    if lock['version']!=1: raise ValueError('lock version mismatch')
    seen=set(); prepared=[]
    for entry in lock['datasets']:
        validate_entry(entry)
        if entry['vertical'] in seen: raise ValueError('duplicate vertical')
        seen.add(entry['vertical'])
        cache.mkdir(parents=True,exist_ok=True)
        destination=cache/entry['sha256']
        if destination.exists(): verify_directory(destination,entry)
        else:
            with tempfile.TemporaryDirectory(dir=cache,prefix='.prepare-') as td:
                stage=Path(td); blob=stage/'artifact.tar.gz'
                if artifact_directory:
                    with open(artifact_directory/(entry['sha256']+'.tar.gz'),'rb') as src, open(blob,'wb') as dst:
                        shutil.copyfileobj(src,dst,1024*1024)
                else:
                    match=re.fullmatch(r'https://github.com/(metadata-fyi/data-[a-z]+)/releases/download/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)',entry['artifactUrl'])
                    if not match: raise ValueError('invalid release URL')
                    repository,tag,filename=match.groups()
                    subprocess.run(['gh','release','download',tag,'--repo',repository,'--pattern',filename,'--dir',str(stage)],check=True,capture_output=True)
                    downloaded=stage/filename
                    if downloaded!=blob: downloaded.rename(blob)
                if blob.stat().st_size!=entry['bytes'] or digest(blob)!=entry['sha256']: raise ValueError('artifact integrity mismatch')
                unpack=stage/'unpack';unpack.mkdir(); total=0; paths=set()
                with tarfile.open(blob,'r:gz') as archive:
                    for member in archive:
                        if not member.isfile() or member.name in paths or Path(member.name).name in ('.','..') or not re.fullmatch(r'(source-manifest\.json|data/[a-zA-Z0-9_.-]+)',member.name): raise ValueError('unsafe archive member')
                        paths.add(member.name);total+=member.size
                        if total>MAX_BYTES: raise ValueError('extraction limit exceeded')
                        target=unpack/member.name;target.parent.mkdir(exist_ok=True)
                        with archive.extractfile(member) as src,open(target,'wb') as dst: shutil.copyfileobj(src,dst,1024*1024)
                verify_directory(unpack,entry)
                os.rename(unpack,destination)
        prepared.append({'vertical':entry['vertical'],'path':str(destination.resolve()),'sha256':entry['sha256']})
    return {'version':1,'datasets':prepared,'activation':'prepared-only'}

def verify_workspace(root, lock_path):
    lock=json.loads(lock_path.read_text())
    if lock['version']!=1: raise ValueError('lock version mismatch')
    inventory_data=inventory(root)
    expected={v['id']:v for v in inventory_data['verticals']}
    seen=set()
    for entry in lock['datasets']:
        validate_entry(entry)
        name=entry['vertical']
        if name in seen or name not in expected: raise ValueError('duplicate/unknown vertical')
        seen.add(name)
        manifest={'schema':SCHEMA,'vertical':name,'files':expected[name]['files']}
        raw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
        if hashlib.sha256(raw).hexdigest()!=entry['sourceManifestSha256']: raise ValueError('workspace differs from pinned release: '+name)
    if seen!=set(expected): raise ValueError('lock must cover every registered vertical')
    if (root/'.git').exists():
        paths=['packages/api/data/'+v['id']+'/'+f['path'] for v in inventory_data['verticals'] for f in v['files']]
        tracked=subprocess.run(['git','ls-files','--',*paths],cwd=root,capture_output=True,text=True,check=True).stdout.splitlines()
        if tracked: raise ValueError('catalog inputs must be generated, not tracked in the application: '+tracked[0])
    return {'status':'passed','verticals':len(seen),'source':'pinned-release-manifests'}

def materialize_runtime(root, destination):
    release_root=root/'.release'
    destination=destination.absolute()
    if release_root.is_symlink() or destination.is_symlink() or destination.resolve()==release_root.resolve() or not destination.resolve().is_relative_to(release_root.resolve()): raise ValueError('runtime sources must be prepared inside a release artifact')
    verify_workspace(root,root/'catalog.lock.json')
    inventory_data=inventory(root)
    lock=json.loads((root/'catalog.lock.json').read_text())
    entries={e['vertical']:e for e in lock['datasets']}
    data=destination/'packages/api/data'
    for directory in (destination,destination/'packages',destination/'packages/api',data):
        if directory.is_symlink(): raise ValueError('artifact directory links are forbidden')
    data.mkdir(parents=True,exist_ok=True)
    total=0
    for vertical in inventory_data['verticals']:
        name=vertical['id']
        manifest={'schema':SCHEMA,'vertical':name,'files':vertical['files']}
        raw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
        if hashlib.sha256(raw).hexdigest()!=entries[name]['sourceManifestSha256']: raise ValueError('source changed before runtime preparation')
        target=data/name
        if target.is_symlink(): raise ValueError('artifact source directory must not be a symlink')
        if target.exists(): shutil.rmtree(target)
        target.mkdir()
        source=root/'packages/api/data'/name
        if source.is_symlink(): raise ValueError('source directory must not be a symlink')
        for item in vertical['files']:
            src=source/item['path'];dst=target/item['path']
            if src.is_symlink(): raise ValueError('source links are forbidden')
            shutil.copy2(src,dst)
            if dst.stat().st_size!=item['bytes'] or digest(dst)!=item['sha256']: raise ValueError('source changed while preparing artifact')
            total+=1
    receipt={'version':1,'catalogLockSha256':digest(root/'catalog.lock.json'),'verticals':len(entries),'sourceFiles':total,'rawEvidenceIncluded':False}
    write(destination/'catalog-runtime-manifest.json',receipt)
    return receipt

def hydrate(root, lock_path, cache, artifact_directory=None):
    lock=json.loads(lock_path.read_text())
    registry=json.loads((root/'packages/api/data/vertical-registry.json').read_text())
    known={v['id'] for v in registry['verticals']}
    names=[e['vertical'] for e in lock['datasets']]
    if set(names)!=known or len(names)!=len(known): raise ValueError('lock must cover every registered vertical exactly once')
    prepared=resolve(lock_path,cache,artifact_directory)
    data=root/'packages/api/data'
    if data.is_symlink(): raise ValueError('data directory must not be a symlink')
    receipt=[]
    for dataset in prepared['datasets']:
        source=Path(dataset['path'])
        manifest=json.loads((source/'source-manifest.json').read_text())
        target=data/dataset['vertical']
        if target.is_symlink(): raise ValueError('vertical directory must not be a symlink')
        target.mkdir(parents=True,exist_ok=True)
        for item in manifest['files']:
            destination=target/item['path']
            if destination.is_symlink(): raise ValueError('source destination must not be a symlink')
            if destination.is_file() and destination.stat().st_size==item['bytes'] and digest(destination)==item['sha256']: continue
            with tempfile.NamedTemporaryFile(dir=target,prefix='.catalog-',delete=False) as output:
                temporary=Path(output.name)
                try:
                    with (source/'data'/item['path']).open('rb') as input_file: shutil.copyfileobj(input_file,output,1024*1024)
                    output.flush()
                    if temporary.stat().st_size!=item['bytes'] or digest(temporary)!=item['sha256']: raise ValueError('source changed during hydration')
                    os.chmod(temporary,0o644);os.replace(temporary,destination)
                finally:
                    if temporary.exists(): temporary.unlink()
        receipt.append({'vertical':dataset['vertical'],'files':len(manifest['files']),'sha256':dataset['sha256']})
    return {'status':'hydrated','activation':'build-workspace-only','datasets':receipt}

def pin_release(root, lock_path, repository, tag, sync=False):
    if not re.fullmatch(r'metadata-fyi/data-[a-z]+',repository) or not re.fullmatch(r'[a-zA-Z0-9_.-]+',tag): raise ValueError('invalid repository/tag')
    response=subprocess.run(['gh','api','repos/'+repository+'/releases/tags/'+tag],capture_output=True,text=True,check=True)
    remote=json.loads(response.stdout)
    artifacts=[a for a in remote['assets'] if a['name'].endswith('.tar.gz')]
    if len(artifacts)!=1: raise ValueError('release must have exactly one source archive')
    asset=artifacts[0]
    if not 0<asset['size']<=MAX_BYTES: raise ValueError('artifact size limit')
    with tempfile.TemporaryDirectory(prefix='metadata-pin-') as td:
        stage=Path(td)
        subprocess.run(['gh','release','download',tag,'--repo',repository,'--pattern',asset['name'],'--dir',str(stage)],check=True,capture_output=True)
        archive=stage/asset['name']
        with tarfile.open(archive,'r:gz') as tar:
            member=tar.getmember('source-manifest.json')
            if not member.isfile() or member.size>16*1024*1024: raise ValueError('invalid source manifest')
            raw=tar.extractfile(member).read()
        manifest=json.loads(raw)
        entry={'vertical':repository.removeprefix('metadata-fyi/data-'),'repository':repository,
          'commit':remote['target_commitish'],'schema':manifest['schema'],'artifactUrl':asset['browser_download_url'],
          'sha256':digest(archive),'bytes':archive.stat().st_size,'sourceManifestSha256':hashlib.sha256(raw).hexdigest(),'policyVersion':1}
        validate_entry(entry)
        if manifest['vertical']!=entry['vertical']: raise ValueError('vertical mismatch')
        archive.rename(stage/(entry['sha256']+'.tar.gz'))
        fixture=stage/'lock.json';write(fixture,{'version':1,'datasets':[entry]})
        prepared=resolve(fixture,stage/'cache',stage)
        if sync:
            source=Path(prepared['datasets'][0]['path'])/'data'
            target=root/'packages/api/data'/entry['vertical']
            for file in source.iterdir():
                temporary=target/(file.name+'.catalog-update')
                shutil.copyfile(file,temporary);os.replace(temporary,target/file.name)
        lock=json.loads(lock_path.read_text())
        if not any(e['vertical']==entry['vertical'] for e in lock['datasets']): raise ValueError('vertical is not registered in lock')
        lock['datasets']=[entry if e['vertical']==entry['vertical'] else e for e in lock['datasets']]
        write(lock_path,lock)
        return {'status':'pinned','entry':entry,'workspaceSynchronized':sync}

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('inventory');i.add_argument('--output',type=Path,required=True)
    b=sub.add_parser('pack');b.add_argument('vertical');b.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('resolve');r.add_argument('--lock',type=Path,required=True);r.add_argument('--cache',type=Path,required=True);r.add_argument('--artifact-directory',type=Path)
    w=sub.add_parser('verify-workspace');w.add_argument('--lock',type=Path,default=ROOT/'catalog.lock.json');w.add_argument('--workspace',type=Path,default=ROOT)
    u=sub.add_parser('pin');u.add_argument('--lock',type=Path,default=ROOT/'catalog.lock.json');u.add_argument('--repository',required=True);u.add_argument('--tag',required=True);u.add_argument('--sync-workspace',action='store_true')
    h=sub.add_parser('hydrate');h.add_argument('--lock',type=Path,default=ROOT/'catalog.lock.json');h.add_argument('--cache',type=Path,required=True);h.add_argument('--artifact-directory',type=Path);h.add_argument('--workspace',type=Path,default=ROOT)
    m=sub.add_parser('materialize-runtime');m.add_argument('--destination',type=Path,required=True);m.add_argument('--workspace',type=Path,default=ROOT)
    a=p.parse_args()
    if a.command=='inventory': result=inventory(ROOT,a.output)
    elif a.command=='pack': result=pack(ROOT,a.vertical,a.output)
    elif a.command=='verify-workspace': result=verify_workspace(a.workspace,a.lock)
    elif a.command=='pin': result=pin_release(ROOT,a.lock,a.repository,a.tag,a.sync_workspace)
    elif a.command=='hydrate': result=hydrate(a.workspace,a.lock,a.cache,a.artifact_directory)
    elif a.command=='materialize-runtime': result=materialize_runtime(a.workspace,a.destination)
    else: result=resolve(a.lock,a.cache,a.artifact_directory)
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
