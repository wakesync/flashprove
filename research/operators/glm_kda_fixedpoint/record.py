#!/usr/bin/env python3
"""CPU-only bounded receipt; no downloads or framework dependencies."""
import hashlib,json,pathlib,platform,subprocess,time
here=pathlib.Path(__file__).resolve().parent
root=here.parents[2]
rel=str(here.relative_to(root))
report={'platform':platform.platform(),'compiler':subprocess.check_output(['g++','--version'],text=True),'base':'8fca2c4b9ffb5d5180df51095d5f52a33df4a207','commands':[]}
for cmd in [['python3',rel+'/reference.py'],['g++','-std=c++17','-O2','-Wall','-Wextra','-fno-ipa-modref','-DBLK_FIELD=2','-DBLK_HASH=1','-I','blocks',rel+'/test.cpp','-o',rel+'/test.bin'],[rel+'/test.bin']]:
 start=time.monotonic();p=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=300)
 report['commands'].append(dict(argv=cmd,exit=p.returncode,seconds=round(time.monotonic()-start,3),stdout=p.stdout,stderr=p.stderr))
 (here/'evidence.json').write_text(json.dumps(report,indent=2)+'\n')
 print(p.stdout,end='');print(p.stderr,end='')
 if p.returncode:raise SystemExit(p.returncode)
paths=list(here.glob('*.py'))+list(here.glob('*.cpp'))+list(here.glob('*.h'))+[here/'provenance.json',here/'reference.json',here.parent/'affine_rows/product.h',here.parent/'shared_wires/product.h',here.parent/'public_binding/product.h']
report['sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(here/'evidence.json').write_text(json.dumps(report,indent=2)+'\n')
print('record: PASS')
