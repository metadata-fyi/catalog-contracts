#!/usr/bin/env python3
"""Validate explicit identity/relationship/media envelopes for public exports."""
import datetime,json,re,sys
from urllib.parse import urlparse
def validate(catalog):
    ids=set();aliases={}
    entities=catalog['entities']
    for e in entities:
        identity=e['ref']
        if not isinstance(identity,str) or not re.fullmatch(r'[a-z]+/[a-z]+/[^\s]+',identity) or identity in ids: raise ValueError('invalid/duplicate identity')
        if not e.get('legacyId') or identity.split('/',2)[2]!=e['legacyId']: raise ValueError('legacy ID must be preserved')
        ids.add(identity)
        key=('/'.join(identity.split('/',2)[:2]),e['legacyId'].casefold())
        if key in aliases and aliases[key]!=identity: raise ValueError('ambiguous canonical identity')
        aliases[key]=identity
    for e in entities:
        for alias in e.get('aliases',[]):
            if not isinstance(alias,str) or not alias: raise ValueError('invalid alias')
            key=('/'.join(e['ref'].split('/',2)[:2]),alias.casefold())
            if key in aliases and aliases[key]!=e['ref']: raise ValueError('ambiguous alias')
            aliases[key]=e['ref']
        for target in e.get('relationships',[]):
            if target not in ids: raise ValueError('dangling relationship')
        permission=e.get('metadataPermission',{})
        if permission.get('approved') is not True or not permission.get('license') or not permission.get('evidence'): raise ValueError('metadata permission missing')
    asset_ids=set()
    for asset in catalog.get('assets',[]):
        if asset['id'] in asset_ids: raise ValueError('duplicate asset identity')
        asset_ids.add(asset['id'])
        if asset['entityId'] not in ids: raise ValueError('dangling media entity')
        for key in ('id','creator','license','licenseUrl','attribution','permissionEvidence','acquiredAt','sha256','width','height','sourceUrl'):
            if key not in asset or asset[key] in (None,''): raise ValueError('media evidence missing: '+key)
        datetime.datetime.fromisoformat(asset['acquiredAt'])
        if asset.get('redistributionApproved') is not True: raise ValueError('media permission missing')
        if not re.fullmatch('[0-9a-f]{64}',asset['sha256']): raise ValueError('invalid media digest')
        for key in ('sourceUrl','licenseUrl'):
            url=urlparse(asset[key])
            if url.scheme!='https' or not url.hostname: raise ValueError('invalid media URL')
        if any(not isinstance(asset[k],int) or isinstance(asset[k],bool) or asset[k]<=0 for k in ('width','height')): raise ValueError('invalid media dimensions')
    return {'status':'passed','entities':len(ids),'assets':len(catalog.get('assets',[]))}
if __name__=='__main__': print(json.dumps(validate(json.load(open(sys.argv[1])))))
