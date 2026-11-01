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

def inventory(root, output):
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
    write(output,result)
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
                        if not member.isfile() or member.name in paths or not re.fullmatch(r'(source-manifest\.json|data/[a-zA-Z0-9_.-]+)',member.name): raise ValueError('unsafe archive member')
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
    inventory_data=inventory(root,root/'outputs/catalog-architecture/workspace-inventory.json')
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
    return {'status':'passed','verticals':len(seen),'source':'pinned-release-manifests'}

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('inventory');i.add_argument('--output',type=Path,required=True)
    b=sub.add_parser('pack');b.add_argument('vertical');b.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('resolve');r.add_argument('--lock',type=Path,required=True);r.add_argument('--cache',type=Path,required=True);r.add_argument('--artifact-directory',type=Path)
    w=sub.add_parser('verify-workspace');w.add_argument('--lock',type=Path,default=ROOT/'catalog.lock.json')
    a=p.parse_args()
    if a.command=='inventory': result=inventory(ROOT,a.output)
    elif a.command=='pack': result=pack(ROOT,a.vertical,a.output)
    elif a.command=='verify-workspace': result=verify_workspace(ROOT,a.lock)
    else: result=resolve(a.lock,a.cache,a.artifact_directory)
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
