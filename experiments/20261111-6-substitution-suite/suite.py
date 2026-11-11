#!/usr/bin/env python3
"""Registered paired verification suite. Run from repo root; refuses existing receipts.
Build with verifier/build.sh then build_variants.py. --dry-run invokes no verifier.
Proofs and mutated inputs stay under bin/subst6; hashes and full checker output are receipts.

Two modes that call the checkers:
- registered (default, --out): the mode of the registered run, unchanged. It keeps the lane's fixed
  wall-clock stop 2026-11-11T06:40Z and the 1800 s budget, so any call after that stop does setup,
  then records no case. It exits 0 even on a partial run (PREREG amendment 5).
- reproduce (--reproduce DIR --budget-min N): a new run for reproduction, not the registered one.
  No fixed wall-clock stop; it stops N minutes after its own start. Refuses a DIR that exists or lies
  under runs/. Writes DIR/reproduce.jsonl, DIR/reproduce.summary.json, altered inputs in DIR/work/.
  Exit 0 = every planned case and repetition ran and passed, 1 = all ran and one failed,
  3 = incomplete or empty run. --reps K (1..5) and --cases A,B,... select a subset.
"""
import argparse, copy, datetime, hashlib, json, math, os, pathlib, re, statistics, struct, subprocess, sys, time
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WORK=ROOT/'bin/subst6/registered'
EX=ROOT/'examples/accepted-proof'; GAP=ROOT/'examples/accepted-proof-clipped-gap'
CP=ROOT/'bin/cp_verify'; HB=ROOT/'bin/subst6/handoff.bin'; HD=ROOT/'bin/subst6/handoff_fp94.bin'
sys.path.insert(0,str(ROOT/'research/operators/qwen_handoff'))
import fixtures as X
sys.path.insert(0,str(ROOT/'tools/manifest'))
import tamper as M
import ed25519

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def clean(s): return s.replace(str(ROOT),'<repo>').replace(sys.executable,'python3')
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def run(cmd):
    t=time.monotonic(); p=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True,timeout=180)
    out=clean(p.stdout+p.stderr); lines=out.strip().splitlines()
    obj=next((json.loads(l) for l in reversed(p.stdout.splitlines()) if l.startswith('{')),None)
    return dict(command=[clean(str(x)) for x in cmd],exit=p.returncode,output=out,last=lines[-1] if lines else '',seconds=time.monotonic()-t,json=obj)
def cp(ex=EX,config=None,ivk=None,req=None,y=None,proof=None,ident=None,policy=None,binary=CP):
    cmd=[binary,config or ex/'config',ivk or ex/'ivk',req or ex/'example.req',y or ex/'example.y',proof or ex/'example.proof','-id',ident or (ex/'ID.txt').read_text().strip(),'-j','1','-q']
    if policy:cmd+=['-policy',policy]
    return cmd
def checkp(end):
    return [sys.executable,ROOT/'integrations/check_proof.py',EX/'example.proof',EX/'example.req','--public-key-dir',EX/'ivk','--parameter-file',EX/'config/policy.txt','--scales-file',EX/'config/KL.bin','--commitment-id',(EX/'ID.txt').read_text().strip(),'--range','60:64','--next-token','199','--end-token',str(end),'--threads','1']
def hverify(stmt,pf,binary=HB):return [binary,'verify',stmt,'-',pf]
def put(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path

def c_cases(dry=False):
    WORK.mkdir(parents=True,exist_ok=True)
    cases=[]
    def add(n,cmd,expected,control=None,kind='proof_constraint',reason=None):
        cases.append(dict(case=n,cmd=cmd,expected=expected,control=control or cp(),kind=kind,reason=reason))
    gp='clipped-gap,9244130,323343,1,16,8'
    add('C-CFG1',cp(config=GAP/'config',policy=gp),'NO: model-statement',kind='application_validation')
    add('C-CFG1b',cp(config=GAP/'config'),'NO: policy',kind='application_validation')
    add('C-CFG2',cp(ex=GAP,req=EX/'example.req',y=EX/'example.y',proof=EX/'example.proof',policy=gp),'proof-class',cp(ex=GAP,policy=gp))
    cfg=WORK/'config-comment';cfg.mkdir(exist_ok=True)
    for p in (EX/'config').iterdir():put(cfg/p.name,p.read_bytes()+(b'# subst6 byte binding control\n' if p.name=='layout.txt' else b''))
    ident='DRY-RUN'
    if not dry:
        r=run([CP,'-plan','id',cfg,EX/'ivk/key.bin'])
        (WORK/'derived-id.json').write_text(json.dumps(r))
        match=re.search(r'commitment ID: ([a-f0-9]{64})',r['output'])
        if not match:raise RuntimeError(r)
        ident=match[1]
    add('C-CFG3',cp(config=cfg,ident=ident),'NO: key-refused')
    add('C-CFG3b',cp(config=cfg),'NO: model-statement',kind='application_validation')
    add('C-REQ1',cp(req=GAP/'example.req',y=GAP/'example.y'),'request-class')
    words=list(struct.unpack('<66I',(EX/'example.req').read_bytes()))
    for n,mut in [('C-REQ2',lambda w:w.__setitem__(5,w[5]+1)),('C-REQ3',lambda w:w.__setitem__(slice(3,5),[w[4],w[3]])),('C-REQ4',lambda w:w.__setitem__(64,59)),('C-RPL1',lambda w:w.__setitem__(62,w[62]+1)),('C-PFX1',lambda w:w.__setitem__(0,w[0]+1))]:
        w=words.copy();mut(w);req=put(WORK/(n+'.req'),struct.pack('<66I',*w));add(n,cp(req=req),'NO: proof-refused')
    add('C-REQ5',cp(proof=GAP/'example.proof'),'proof-class')
    add('C-RPL2',cp(),'accept',kind='not_enforced')
    add('C-TOK5',cp(),'accept',kind='not_enforced')
    add('C-TOK4',checkp(5),'check_proof: rejected',checkp(199),'application_validation','not one of your end tokens')
    for i in [1,2]:add('C-DOM'+str(i),cp(binary=ROOT/f'bin/subst6/dom{i}/cp_verify'),'NO: proof-refused' if i==1 else 'NO: key-refused')
    pf=(EX/'example.proof').read_bytes()
    variants=[pf[:-1],pf[:len(pf)//2],pf[:16],b'',pf+b'\0',pf+bytes(4096)]
    for at in [0,len(pf)//2,len(pf)-1]:
        b=bytearray(pf);b[at]^=1;variants.append(bytes(b))
    for i,b in enumerate(variants,1):add(f'C-MAL{i}',cp(proof=put(WORK/f'C-MAL{i}.proof',b)),'malformed-class',kind='parser_or_proof')
    if not dry:
        # Build digest acquisition is setup, logged; it is not an excluded case.
        r=run(cp());(WORK/'build-digest.json').write_text(json.dumps(r))
        digest=re.search(r' build=([a-f0-9]{64})',r['output']).group(1)
        md=WORK/'manifest';md.mkdir(exist_ok=True)
        m,recipe=M.make_fixture(md,digest);mp,sp=M.write_signed(md,m)
        def manifest(overrides=None,p=mp,s=sp):return [sys.executable,ROOT/'tools/manifest/manifest.py',*M.verify_argv(md,p,s,recipe,overrides)]
        control=manifest()
        bad=md/'bad-tokenizer';bad.mkdir(exist_ok=True)
        for p in (md/'tokenizer').iterdir():put(bad/p.name,p.read_bytes()+(b' ' if p.name=='tokenizer.json' else b''))
        add('C-TOK1',manifest({'--tokenizer-dir':str(bad)}),'manifest: REFUSED: serving.tokenizer.files',control,'application_validation')
        ct=put(md/'bad-template',b'changed template\n')
        add('C-TOK2',manifest({'--chat-template':str(ct)}),'manifest: REFUSED: serving.chat_template',control,'application_validation')
        add('C-TOK3',manifest({'--end-tokens':'1'}),'manifest: REFUSED: serving.end_tokens',control,'application_validation')
        hostile=copy.deepcopy(m);hostile['serving']['tokenizer']['files'][0]['sha256']=sha(bad/hostile['serving']['tokenizer']['files'][0]['path'])
        hostile['signer']['public_key']=ed25519.public_key(M.ATTACKER_SECRET).hex()
        ap,asp=M.write_signed(md,hostile,M.ATTACKER_SECRET,'attacker.json')
        add('C-TOK6',manifest({'--tokenizer-dir':str(bad)},ap,asp),'manifest: REFUSED: signature',control,'application_validation')
    return cases

def h_cases(seed,rep,debug=False):
    d=WORK/f'handoff-{seed}';d.mkdir(parents=True,exist_ok=True)
    s,parts=X.generate(seed,4 if debug else 8,1 if debug else 2)
    stmt=put(d/'own.stmt',X.statement_bytes(s));wd=d/'honest';X.write_parts(wd,parts)
    pf=d/'honest.proof';gen=run([HB,'prove',stmt,wd,pf])
    if gen['exit']!=0:raise RuntimeError(gen)
    cases=[];control=hverify(stmt,pf)
    def add(n,cmd,expected='h-reject',kind='proof_constraint',generation=None,ctl=None):
        cases.append(dict(case=n,cmd=cmd,expected=expected,control=ctl or control,kind=kind,reason=None,generation=generation))
    def changed(n,mut):
        x=copy.deepcopy(s);mut(x);st=put(d/(n+'.stmt'),X.statement_bytes(x));add(n,hverify(st,pf));return st
    changed('H-CFG1',lambda x:x.__setitem__('model',bytes([x['model'][0]^1])+x['model'][1:]))
    changed('H-CFG2',lambda x:x.__setitem__('weights',bytes([x['weights'][0]^1])+x['weights'][1:]))
    changed('H-REQ1',lambda x:x.__setitem__('request',x['request']+1))
    changed('H-REQ2',lambda x:x['outputs'][0].__setitem__(0,x['outputs'][0][0]+1))
    changed('H-REQ3',lambda x:x['xs'].__setitem__((0,0),x['xs'][0,0]+1))
    other,_=X.generate(seed+1,s['D'],s['C']);add('H-RPL1',hverify(put(d/'other.stmt',X.statement_bytes(other)),pf))
    st=changed('H-PFX1',lambda x:x['S0'].__setitem__((0,0),x['S0'][0,0]+1))
    bad=bytearray(st.read_bytes());bad[136:168]=stmt.read_bytes()[136:168]
    add('H-PFX2',hverify(put(d/'bad-opening.stmt',bad),pf),'FAIL: verifier initial root opening','application_validation')
    changed('H-PFX3',lambda x:x['H0'].__setitem__((0,0),x['H0'][0,0]+1))
    for n,target,pp in [('H-PFX4',st,copy.deepcopy(parts)),('H-PFX5',stmt,copy.deepcopy(parts))]:
        if n=='H-PFX5':pp[1]['S0'][0,0]+=1;X.redo(pp,1)
        w=d/n;X.write_parts(w,pp);p=w/'hostile.proof';g=run([HB,'hostile',target,w,p])
        if g['exit']!=0 or not g['json']['products_hold']:raise RuntimeError(g)
        add(n,hverify(target,p),generation=g)
    fp94=d/'fp94.proof';g=run([HD,'prove',stmt,wd,fp94])
    if g['exit']!=0:raise RuntimeError(g)
    add('H-DOM1',hverify(stmt,fp94),generation=g)
    add('H-DOM2',hverify(stmt,pf,HD),ctl=hverify(stmt,fp94,HD))
    data=pf.read_bytes();b=bytearray(data);b[len(b)//2]^=1
    for i,b in enumerate([data[:-1],data+b'\0',bytes(b),b''],1):add(f'H-MAL{i}',hverify(stmt,put(d/f'mal{i}.proof',b)),'h-malformed',kind='parser_or_proof')
    return cases,gen

def accepted(r):
    return r['exit']==0 and (r['last']=='YES' or r['last'].startswith(('WITHIN LIMITS:','manifest: ACCEPTED','check_proof: verified')) or bool(r['json'] and r['json'].get('accept')))
def judge(r,c):
    e=c['expected'];last=r['last'];j=r['json']
    if e=='accept':return accepted(r)
    if e=='proof-class':return r['exit']==1 and last in ['NO: proof-refused','NO: key-refused','NO: entry-refused']
    if e=='request-class':return r['exit']==1 and last in ['NO: proof-refused','NO: statement-range','NO: token-range']
    if e=='malformed-class':return r['exit']==1 and last.startswith('NO: ') and ('proof' in last or 'header' in last)
    if e in ('h-reject','h-malformed'):return r['exit']==1 and ((j and j.get('accept') is False) or (e=='h-malformed' and last.startswith('FAIL:')))
    return r['exit']==1 and last.startswith(e) and (not c.get('reason') or c['reason'] in r['output'])
def actual_kind(r):
    if accepted(r):return 'accepted'
    if r['json'] and r['json'].get('check')=='proof-verifier':return 'proof_constraint'
    if r['last'] in ['NO: proof-refused','NO: key-refused','NO: entry-refused']:return 'proof_constraint'
    return 'application_validation'
def stats(v):return dict(n=len(v),median=statistics.median(v),sd=statistics.stdev(v) if len(v)>1 else 0,min=min(v),max=max(v))

# Reproduction mode (PREREG amendment 5). Separate from the registered path below, which is unchanged.
H_NAMES=['H-CFG1','H-CFG2','H-REQ1','H-REQ2','H-REQ3','H-RPL1','H-PFX1','H-PFX2','H-PFX3','H-PFX4','H-PFX5','H-DOM1','H-DOM2','H-MAL1','H-MAL2','H-MAL3','H-MAL4']
EXIT_PASS,EXIT_CASE_FAILED,EXIT_INCOMPLETE=0,1,3
def reproduce(args):
    global WORK
    b=args.budget_min
    if b is None or not math.isfinite(b) or not 0<b<=600:raise SystemExit('suite.py --reproduce: --budget-min must be finite, > 0 and <= 600')
    reps=args.reps if args.reps is not None else 5
    if not 1<=reps<=5:raise SystemExit('suite.py --reproduce: --reps must be 1..5')
    d=pathlib.Path(args.reproduce).resolve();runs=(HERE/'runs').resolve()
    if d==runs or runs in d.parents:raise SystemExit('suite.py --reproduce: refusing a directory under runs/ (registered receipts)')
    if d.exists() or d.is_symlink():raise SystemExit('suite.py --reproduce: refusing an existing directory: '+str(d))
    sel=[n for n in args.cases.split(',') if n] if args.cases else None
    start=time.monotonic();budget=b*60;started=utc()
    d.mkdir(parents=True);WORK=d/'work'
    out=d/'reproduce.jsonl';rows=[];partial=False;planned=None
    with out.open('x') as f:
        f.write(json.dumps(dict(event='start',mode='reproduce',started_utc=started,budget_seconds=budget,reps=reps,cases=sel,note='reproduction run, not the registered run'))+'\n');f.flush()
        cases=c_cases()
        names=[c['case'] for c in cases]+H_NAMES
        if sel is not None:
            bad=[n for n in sel if n not in names]
            if bad:raise SystemExit('suite.py --reproduce: unknown case(s): '+','.join(bad))
            cases=[c for c in cases if c['case'] in sel]
        planned=sel if sel is not None else names
        need_h=any(n.startswith('H-') for n in planned)
        for rep in range(1,reps+1):
            hc=[]
            if need_h:
                if time.monotonic()-start>budget:partial=True;break
                hc,g=h_cases(200+rep,rep)
                if sel is not None:hc=[c for c in hc if c['case'] in sel]
                f.write(json.dumps(dict(event='generation',mode='reproduce',rep=rep,result=g))+'\n');f.flush()
            for c in cases+hc:
                if time.monotonic()-start>budget:partial=True;break
                pair={}
                for arm in (['control','attack'] if rep%2 else ['attack','control']):pair[arm]=run(c['control'] if arm=='control' else c['cmd'])
                row=dict(mode='reproduce',case=c['case'],rep=rep,expected=c['expected'],intended_kind=c['kind'],actual_kind=actual_kind(pair['attack']),control=pair['control'],attack=pair['attack'],generation=c.get('generation'),control_accepts=accepted(pair['control']),attack_accepts=accepted(pair['attack']),intended=judge(pair['attack'],c))
                row['pass']=row['control_accepts'] and row['intended'];rows.append(row)
                f.write(json.dumps(row)+'\n');f.flush();print(c['case'],rep,row['attack']['last'],row['pass'],flush=True)
            if partial:break
    got={(r['case'],r['rep']) for r in rows}
    complete=(not partial) and bool(rows) and all((n,rep) in got for n in planned for rep in range(1,reps+1))
    summary={}
    for n in sorted({r['case'] for r in rows}):
        rr=[r for r in rows if r['case']==n]
        summary[n]=dict(n=len(rr),controls=sum(r['control_accepts'] for r in rr),accepted=sum(r['attack_accepts'] for r in rr),intended=sum(r['intended'] for r in rr),verdict='PASS' if len(rr)==reps and all(r['pass'] for r in rr) else 'FAIL',acceptance=stats([int(r['attack_accepts']) for r in rr]),seconds=stats([r['attack']['seconds'] for r in rr]),checks=sorted({r['attack']['last'] for r in rr}),kinds=sorted({r['actual_kind'] for r in rr}))
    code=EXIT_INCOMPLETE if not complete else (EXIT_PASS if all(r['pass'] for r in rows) else EXIT_CASE_FAILED)
    hashes={'work/'+str(p.relative_to(WORK)):sha(p) for p in sorted(WORK.rglob('*')) if p.is_file()}
    for x in [EX,GAP]:
        hashes.update({str(p.relative_to(ROOT)):sha(p) for p in x.rglob('*') if p.is_file()})
    doc=dict(mode='reproduce',note='reproduction run, not the registered run; not evidence for the PREREG verdict',started_utc=started,finished_utc=utc(),budget_seconds=budget,reps=reps,selected=sel,planned=len(planned)*reps,rows=len(rows),partial=partial,complete=complete,exit=code,elapsed_seconds=time.monotonic()-start,cases=summary,inputs=hashes)
    with out.with_suffix('.summary.json').open('x') as f:json.dump(doc,f,indent=2);f.write('\n')
    print(json.dumps(dict(mode='reproduce',rows=len(rows),planned=len(planned)*reps,complete=complete,exit=code)),flush=True)
    return code

def main():
    a=argparse.ArgumentParser();a.add_argument('--dry-run',action='store_true');a.add_argument('--debug',action='store_true');a.add_argument('--out',default='runs/registered.jsonl')
    a.add_argument('--reproduce',metavar='DIR',help='reproduction mode: new run into DIR (not under runs/), see the docstring');a.add_argument('--budget-min',type=float);a.add_argument('--reps',type=int);a.add_argument('--cases')
    args=a.parse_args()
    if args.reproduce:return reproduce(args)
    if args.budget_min is not None or args.reps is not None or args.cases:a.error('--budget-min, --reps and --cases need --reproduce')
    if args.dry_run:
        print(json.dumps([{**c,'cmd':list(map(str,c['cmd'])),'control':list(map(str,c['control']))} for c in c_cases(True)],indent=1));return
    if args.debug:
        cs,g=h_cases(909,1,True)
        print(json.dumps({'debug_generation':g,'checks':[(c['case'],judge(run(c['cmd']),c)) for c in cs]}));return
    out=HERE/args.out;out.parent.mkdir(exist_ok=True)
    if out.exists():raise RuntimeError('refusing to overwrite receipt')
    start=time.monotonic();started=utc();deadline=datetime.datetime(2026,11,11,6,40,tzinfo=datetime.timezone.utc)
    rows=[];partial=False;cases=c_cases()
    with out.open('x') as f:
        f.write(json.dumps(dict(event='start',started_utc=started,gate_granted='process start',budget_seconds=1800))+'\n');f.flush()
        for rep in range(1,6):
            hc,g=h_cases(200+rep,rep)
            f.write(json.dumps(dict(event='generation',rep=rep,result=g))+'\n');f.flush()
            for c in cases+hc:
                if time.monotonic()-start>1800 or datetime.datetime.now(datetime.timezone.utc)>=deadline:partial=True;break
                pair={}
                for arm in (['control','attack'] if rep%2 else ['attack','control']):pair[arm]=run(c['control'] if arm=='control' else c['cmd'])
                row=dict(case=c['case'],rep=rep,expected=c['expected'],intended_kind=c['kind'],actual_kind=actual_kind(pair['attack']),control=pair['control'],attack=pair['attack'],generation=c.get('generation'),control_accepts=accepted(pair['control']),attack_accepts=accepted(pair['attack']),intended=judge(pair['attack'],c))
                row['pass']=row['control_accepts'] and row['intended'];rows.append(row)
                f.write(json.dumps(row)+'\n');f.flush();print(c['case'],rep,row['attack']['last'],row['pass'],flush=True)
            if partial:break
    summary={}
    for n in sorted({r['case'] for r in rows}):
        rr=[r for r in rows if r['case']==n]
        summary[n]=dict(n=len(rr),controls=sum(r['control_accepts'] for r in rr),accepted=sum(r['attack_accepts'] for r in rr),intended=sum(r['intended'] for r in rr),verdict='PASS' if len(rr)==5 and all(r['pass'] for r in rr) else 'FAIL',acceptance=stats([int(r['attack_accepts']) for r in rr]),seconds=stats([r['attack']['seconds'] for r in rr]),checks=sorted({r['attack']['last'] for r in rr}),kinds=sorted({r['actual_kind'] for r in rr}))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(WORK.rglob('*')) if p.is_file()}
    for d in [EX,GAP]:
        hashes.update({str(p.relative_to(ROOT)):sha(p) for p in d.rglob('*') if p.is_file()})
    doc=dict(started_utc=started,finished_utc=utc(),partial=partial,elapsed_seconds=time.monotonic()-start,cases=summary,inputs=hashes)
    with out.with_suffix('.summary.json').open('x') as f:json.dump(doc,f,indent=2);f.write('\n')
if __name__=='__main__':sys.exit(main())
