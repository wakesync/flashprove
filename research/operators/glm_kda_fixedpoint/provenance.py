#!/usr/bin/env python3
"""Fetch only two small pinned source files; never weights."""
import hashlib,json,urllib.request
from pathlib import Path
here=Path(__file__).resolve().parent
prior=json.loads((here.parent/'glm_kda_slice/provenance.json').read_text())
for item in prior:
    with urllib.request.urlopen(item['url'],timeout=60) as response:
        data=response.read();assert response.status==200
    assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
    item['matches_pr16']=True
(here/'provenance.json').write_text(json.dumps(prior,indent=2)+'\n')
print('provenance: PASS; pinned publisher config and Transformers source byte-match PR16')
