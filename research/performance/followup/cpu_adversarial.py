import json, subprocess, shutil, hashlib
from pathlib import Path
import argparse
p=argparse.ArgumentParser()
p.add_argument('upstream',type=Path);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);p.add_argument('--cpu',default=15,type=int)
args=p.parse_args()
a=args.upstream.resolve();b=args.candidate.resolve();out=args.output.resolve();out.mkdir(exist_ok=False)
source=a/'examples/accepted-proof'
rows=[]
for name,rel,action in [('honest',None,None),('proof-middle','example.proof','flip'),('proof-truncated','example.proof','truncate'),('key-middle','ivk/key.bin','flip'),('leaf-middle','ivk/leaf/0.bin','flip'),('request-token','example.req','flip'),('reply-token','example.y','flip'),('wrong-id',None,None),('policy-invalid','config/policy.txt','policy')]:
 f=out/name;shutil.copytree(source,f)
 if rel:
  p=f/rel
  if not p.exists() and name=='leaf-middle':p=next((f/'ivk/leaf').glob('*.bin'))
  data=bytearray(p.read_bytes())
  if action=='flip':data[len(data)//2]^=1
  elif action=='truncate':data=data[:-1]
  elif action=='policy':data+=b'\nunknown_research_test 1\n'
  p.write_bytes(data)
 ident=(f/'ID.txt').read_text().strip()
 if name=='wrong-id':ident=('0' if ident[0]!='0' else '1')+ident[1:]
 pair=[]
 for label,r in [('upstream',a),('candidate',b)]:
  cmd=['taskset','-c',str(args.cpu),str(r/'bin/cp_verify'),str(f/'config'),str(f/'ivk'),str(f/'example.req'),str(f/'example.y'),str(f/'example.proof'),'-id',ident,'-j','1']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
  (out/(name+'-'+label+'.stdout')).write_text(p.stdout)
  (out/(name+'-'+label+'.stderr')).write_text(p.stderr)
  # Compare every accounting and public result line, except source digest.
  semantic=[x for x in p.stdout.splitlines() if x.startswith(('accounting:','commitment:','proof of work:','covered:','result-v1','YES','NO:'))]
  semantic=[x.split(' build=')[0] for x in semantic]
  pair.append({'arm':label,'exit':p.returncode,'last':p.stdout.splitlines()[-1] if p.stdout else '', 'semantic':semantic})
 rows.append({'case':name,'results':pair,'equal':pair[0]['exit']==pair[1]['exit'] and pair[0]['semantic']==pair[1]['semantic']})
 (out/'results.json').write_text(json.dumps(rows,indent=2))
 if not rows[-1]['equal']:raise RuntimeError(name+' mismatch')
 valid = (pair[0]['exit']==0 and pair[0]['last']=='YES') if name=='honest' else (pair[0]['exit']==1 and pair[0]['last'].startswith('NO:'))
 if not valid: raise RuntimeError(name+' unexpected verdict')
print([(r['case'],r['results'][0]['last'],r['equal']) for r in rows])
