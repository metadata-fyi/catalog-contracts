#!/usr/bin/env python3
import copy,json,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];cases=[]
validator=root/'catalog-contracts/validate-normalized.py'
if not validator.exists():validator=root/'validate-normalized.py'
base={'entities':[{'ref':'figures/items/example','legacyId':'example','aliases':['example-alias'],'relationships':[],'metadataPermission':{'approved':True,'license':'CC0-1.0','evidence':'synthetic original fixture'}}],'assets':[]}
def check(value,ok,label):
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
        json.dump(value,f);f.flush();result=subprocess.run([sys.executable,str(validator),f.name],capture_output=True)
        assert (result.returncode==0)==ok,label
    cases.append(label)
check(base,True,'original synthetic metadata accepted')
x=copy.deepcopy(base);x['entities'][0]['relationships']=['figures/items/missing'];check(x,False,'dangling relationship rejected')
x=copy.deepcopy(base);x['entities'][0]['metadataPermission']={};check(x,False,'unapproved metadata rejected')
x=copy.deepcopy(base);x['entities'].append({**copy.deepcopy(x['entities'][0]),'ref':'figures/items/other','legacyId':'other'});check(x,False,'ambiguous aliases rejected')
x=copy.deepcopy(base);x['entities'][0]['legacyId']='changed';check(x,False,'renamed identity rejected')
x=copy.deepcopy(base);x['assets']=[{'entityId':'figures/items/example','id':'sample'}];check(x,False,'unproven media rejected')
x=copy.deepcopy(base);x['entities'].append({**copy.deepcopy(x['entities'][0]),'ref':'figures/items/example-alias','legacyId':'example-alias','aliases':[]});check(x,False,'alias colliding with canonical identity rejected')
x=copy.deepcopy(base);x['entities'][0].update(ref='figures/items/line/example',legacyId='line/example');x['entities'].append({**copy.deepcopy(x['entities'][0]),'ref':'figures/items/other/example','legacyId':'other/example'});check(x,False,'alias ambiguity across slash-containing legacy IDs rejected')
out=root/'outputs/catalog-architecture/normalized-e2e.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'status':'passed','cases':cases},indent=2)+'\n');print(out.read_text())
