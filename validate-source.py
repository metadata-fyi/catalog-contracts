#!/usr/bin/env python3
"""Verify a vertical repository against its declared source hashes; no dependencies."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=json.loads((root/'source-manifest.json').read_text())
assert manifest['schema']=='metadata.catalog/1'
seen=set()
for item in manifest['files']:
    name=item['path']
    assert Path(name).name==name and name not in seen,'invalid path'
    seen.add(name);p=root/'data'/name
    assert not p.is_symlink() and p.is_file(),'invalid source'
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    assert p.stat().st_size==item['bytes'] and h.hexdigest()==item['sha256'],'source differs from manifest: '+name
assert {p.name for p in (root/'data').iterdir()}==seen,'unlisted source files'
policy=json.loads((root/'publication-policy.json').read_text())
assert policy['publicExportAllowed'] is False,'public export requires reviewed per-record permission tooling'
print(json.dumps({'status':'passed','vertical':manifest['vertical'],'files':len(seen)}))
