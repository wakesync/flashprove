#!/usr/bin/env python3
import subprocess,json,time,pathlib,shutil
root=pathlib.Path('<REPO>')
out=pathlib.Path(__file__).resolve().parent
state=out.parent/'INTEGRATION-V2-STATE.md'
work='<WORK>'
argv=['python3','-u','run_suite.py','cpu',work,'--jobs','4']
samples=[]
for i in range(3):
 samples.append({'time':time.time(),'free':shutil.disk_usage('/').free})
 if i<2: time.sleep(15)
(out/'full-capacity.json').write_text(json.dumps(samples,indent=2)+'\n')
if min(x['free'] for x in samples)<4*1024**3 or samples[0]['free']-samples[-1]['free']>512*1024**2:
 state.write_text('HOLD. Fresh full suite not launched: capacity unstable. See integration-v2-evidence/full-capacity.json. No merge.\n')
 raise SystemExit(2)
start=time.time()
with (out/'full.log').open('w') as f:
 p=subprocess.Popen(argv,cwd=root,stdout=f,stderr=subprocess.STDOUT)
 state.write_text(f'# Integration V2 full CPU running\n\nHEAD 133da749937115883c95edfc4b6e372c16209449. Sole integration owner. PID {p.pid}. Normal confined CPU suite, jobs 4, work {work}. Durable stdout integration-v2-evidence/full.log; aggregate full-result.json and full.exit will be persisted on completion. Capacity preflight three samples passed. No focused rerun, no bypass, no merge. PR4 HOLD pending receipts and independent review.\n')
 code=p.wait()
(out/'full.exit').write_text(str(code)+'\n')
(out/'full-result.json').write_text(json.dumps({'argv':argv,'head':'133da749937115883c95edfc4b6e372c16209449','exit':code,'start':start,'seconds':time.time()-start,'work':work,'free_after':shutil.disk_usage('/').free},indent=2)+'\n')
screens=pathlib.Path(work)/'screens'
if screens.exists(): shutil.copytree(screens,out/'full-screens',dirs_exist_ok=True)
lines=(out/'full.log').read_text(errors='replace').splitlines()
(out/'full-rows.txt').write_text('\n'.join(x for x in lines if any(s in x for s in ('passed','FAILED','not run','in part','ACCEPT','LOOK','exit')))+'\n')
state.write_text(f'# Integration V2 full CPU finished\n\nHEAD 133da749937115883c95edfc4b6e372c16209449. Aggregate exit {code}. Durable evidence integration-v2-evidence/full-result.json, full.exit, full.log, full-rows.txt, full-screens/. Original work retained at {work}. PR4 HOLD pending failure/skip review and independent review. No merge, no confinement bypass.\n')
