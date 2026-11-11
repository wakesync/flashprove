#!/usr/bin/env python3
"""H4-r2 immutable receipts. prepare: compile only. run: invoke ONLY inside fp-heavy.sh.
Two serial queues execute concurrently, always taskset 0-5: hostile then UBSan; control then honest.
No previous run file is overwritten. Registration fixes 110 minutes from gate and hard stop 22:12Z.
"""
import concurrent.futures,datetime,hashlib,json,os,pathlib,subprocess,sys,time
here=pathlib.Path(__file__).resolve().parent;root=here.parents[2]
rel=str(here.relative_to(root));work=here/'work';work.mkdir(exist_ok=True)
out=root/'experiments/20261109-32-qwen-deltanet-lookup-build/runs'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def state(message):
    if os.getenv('M2_STATE'):
        with open(os.environ['M2_STATE'],'a') as f:f.write(f'- {now()} {message}\n')
flags=['-std=c++17','-O2','-Wall','-Wextra','-fno-ipa-modref','-DBLK_FIELD=2','-DBLK_HASH=1','-I','blocks']
binaries=[('m2-r2','m2.cpp',[]),('m2-ubsan-r2','m2.cpp',['-fsanitize=undefined','-fno-sanitize-recover=undefined']),('m2-control-r2','m2.cpp',['-DM2_CONTROL_NO_CG_CHECK']),('isqrt-r2','isqrt_test.cpp',[]),('isqrt-ld64-r2','isqrt_test.cpp',['-mlong-double-64','-fsanitize=undefined','-fno-sanitize-recover=undefined'])]
if sys.argv[1]=='prepare':
    records=[]
    for name,src,extra in binaries:
        start=now();state('BUILD '+name)
        cmd=['g++',*flags,*extra,f'{rel}/{src}','-o',f'{rel}/work/{name}.bin']
        p=subprocess.run(cmd,cwd=root,capture_output=True,text=True)
        (work/(name+'-build.log')).write_text(p.stderr)
        records.append(dict(name=name,start=start,end=now(),exit=p.returncode,flags=flags+extra,sha256=sha(work/(name+'.bin')) if not p.returncode else None,warnings=p.stderr.count('warning:')))
        state('BUILD '+name+' exit '+str(p.returncode))
        if p.returncode:raise SystemExit(p.stderr)
    save(out/'stage2-build-r2.json',records);raise SystemExit(0)
assert sys.argv[1]=='run'
gate=time.monotonic();gate_utc=now();deadline=min(gate+110*60,gate+(datetime.datetime.fromisoformat('2026-11-10T22:12:00+00:00')-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
sources={str(p.relative_to(root)):sha(p) for p in sorted(here.glob('*')) if p.suffix in ('.h','.cpp','.py')}
save(out/'stage2-gate-r2.json',dict(gate_granted_utc=gate_utc,head=head,sources=sources,cores='0-5',budget_seconds=6600,hard_stop='2026-11-10T22:12:00Z',shared_loaded_host=True))
state('RUN START gate granted '+gate_utc+' head '+head)
import reference_m2
fixtures={}
for seed in range(1,11):
    p=work/f'stage2-seed{seed}-r2.bin';reference_m2.write_fixture(str(p),seed);fixtures[seed]=sha(p)
save(out/'stage2-fixtures-r2.json',fixtures)
def run(name,argv,binary=None):
    start=now()
    if time.monotonic()>=deadline:
        save(out/(name+'-receipt.json'),dict(start=start,skipped=True,reason='registered stop reached',head=head))
        state('TEST SKIPPED '+name+' stop reached');return 124
    state('TEST START '+name)
    with (out/(name+'.jsonl')).open('x') as fo,(out/(name+'.stderr')).open('x') as fe:
        proc=subprocess.Popen(['taskset','-c','0-5',*argv],cwd=root,stdout=fo,stderr=fe)
        timed=False
        try:code=proc.wait(timeout=max(0.01,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            proc.kill();code=proc.wait();timed=True
    receipt=dict(start=start,end=now(),exit=code,timed_out=timed,binary_sha256=sha(binary) if binary else None,head=head,argv=argv)
    save(out/(name+'-receipt.json'),receipt);state('TEST END '+name+' exit '+str(code))
    return code
def entry(name,binary,mode,seed=1):
    return run(name,[f'{rel}/work/{binary}.bin',f'{rel}/work/stage2-seed{seed}-r2.bin',mode],work/(binary+'.bin'))
def suite_queue():
    entry('stage2-hostile-seed1-r2','m2-r2','hostile')
    entry('stage2-hostile-seed1-ubsan-r2','m2-ubsan-r2','hostile')
def other_queue():
    entry('stage2-control-r2','m2-control-r2','control')
    for seed in range(1,11):
        if time.monotonic()>=deadline:break
        entry(f'stage2-honest-seed{seed}-r2','m2-r2','honest',seed)
# Audit first; none invokes the M2 fixture binary.
run('stage2-design-regression-r2',[sys.executable,'research/operators/qwen_deltanet_m2/norm_alias_regression.py','--check','research/operators/qwen_deltanet_m2/norm_alias_expected.json'])
run('stage2-audit-r2',[sys.executable,f'{rel}/followup_audit.py'])
for name in ('isqrt-r2','isqrt-ld64-r2'):
    run(name,[f'{rel}/work/{name}.bin'],work/(name+'.bin'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    jobs=[pool.submit(suite_queue),pool.submit(other_queue)]
    for job in jobs:job.result()
state('RUN DONE H4-r2; summarize immutable raw receipts')
