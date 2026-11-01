#!/usr/bin/env python3
"""Build a deterministic source artifact in a standalone data repository."""
import argparse,gzip,hashlib,json,subprocess,tarfile,tempfile
from pathlib import Path
root=Path.cwd()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--refresh-manifest',action='store_true');args=p.parse_args()
manifest_path=root/'source-manifest.json';manifest=json.loads(manifest_path.read_text())
if manifest['schema']!='metadata.catalog/1':raise ValueError('schema mismatch')
seen=set()
for entry in manifest['files']:
    name=entry['path']
    if Path(name).name!=name or name in seen:raise ValueError('unsafe/duplicate path')
    seen.add(name);path=root/'data'/name
    if path.is_symlink() or not path.is_file():raise ValueError('invalid file')
    actual={'path':name,'bytes':path.stat().st_size,'sha256':sha(path)}
    if args.refresh_manifest:entry.update(actual)
    elif entry!=actual:raise ValueError('source differs: refresh manifest in a reviewed PR')
if {p.name for p in (root/'data').iterdir()}!=seen:raise ValueError('unlisted source')
if args.refresh_manifest:manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('wb') as output,gzip.GzipFile(filename='',mode='wb',fileobj=output,mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w|') as archive:
    for name,path in [('source-manifest.json',manifest_path),*[(('data/'+e['path']),root/'data'/e['path']) for e in sorted(manifest['files'],key=lambda e:e['path'])]]:
        info=tarfile.TarInfo(name);info.size=path.stat().st_size;info.mode=0o644;info.mtime=0
        with path.open('rb') as f:archive.addfile(info,f)
receipt={'schema':manifest['schema'],'vertical':manifest['vertical'],'sha256':sha(args.output),'bytes':args.output.stat().st_size,'sourceManifestSha256':sha(manifest_path)}
args.output.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
