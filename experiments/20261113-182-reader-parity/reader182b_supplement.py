"""Supplementary release matrix, after the first series. Never replaces first-series results. Usage: python3 reader182b_matrix.py REPO PRIVATE_BUILD
No verifier proof is made or checked. UBSan unavailable through unchanged unit.sh.
"""
import datetime, hashlib, json, pathlib, re, resource, statistics, struct, subprocess, sys, time
C=pathlib.Path(sys.argv[1]).resolve()
B=pathlib.Path(sys.argv[2]).resolve()
E=C/'experiments/20261113-182-reader-parity'
R=E/'runs/supplementary-matrix'
S=pathlib.Path(__file__).with_name('STATE-reader182b.md')
def note(s):
 if S.exists():
  with S.open('a') as f: f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' '+s+'\n')
def clean(s): return s.replace(str(C),'<REPO>').replace(str(B),'<PRIVATE_BUILD>')
def limit():
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 resource.setrlimit(resource.RLIMIT_CPU,(115,120))
budget=json.loads((E/'runs/continuation-budget.json').read_text())
stop=min(budget['first_build_epoch']+1500,datetime.datetime.fromisoformat('2026-11-13T21:40:00+00:00').timestamp())
def run(cmd):
 if time.time()>=stop: raise SystemExit('registered build/test budget expired')
 p=subprocess.run([str(x) for x in cmd],cwd=C,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,preexec_fn=limit,timeout=min(150,stop-time.time()))
 return {'command':clean(' '.join(str(x) for x in cmd)),'exit':p.returncode,'output':clean(p.stdout),'stderr':clean(p.stderr)}
def save(p,x): p.write_text(json.dumps(x,indent=2)+'\n')
def put(t,k,v):
 t,n=re.subn(r'^'+k+r' .*$',k+' '+str(v),t,flags=re.M)
 assert n==1,(k,n)
 return t
def nodigest(t): return re.sub(r'^t(?:silu|sig|rope|exp)\d+ .*\n','',t,flags=re.M)
def malformed(t,kind):
 lines=t.splitlines(True)
 ids=[i for i,l in enumerate(lines) if re.match(r't(?:silu|sig|rope|exp)\d+ ',l)]
 assert len(ids)==32
 if kind=='partial': del lines[ids[-1]]
 if kind=='reordered': lines[ids[4]],lines[ids[5]]=lines[ids[5]],lines[ids[4]]
 if kind=='duplicate': lines[ids[5]]=lines[ids[4]]
 if kind=='invalid': lines[ids[5]]='tsilu5 4294967296\n'
 return ''.join(lines)
R.mkdir()
F=R/'fixtures'
F.mkdir()
kit=C/'prover/tests/configurations/pinned_no_proof_of_work'
old=C/'experiments/20261113-156-dense-table-digests/runs/served/dense-files'
dense=(old/'routed-experts.dense-with-digests.policy.txt').read_text()
expert=(kit/'policy.txt').read_text()
cases={}
def add(name,t,b,a,v): cases[name]={'bytes':t,'before':b,'after':a,'verifier':v}
ok='ok'
add('dense-valid',dense,'policy-tables',ok,'met')
add('dense-no-digests',nodigest(dense),ok,ok,'not-met:table-digests')
for kind in ['partial','reordered','duplicate','invalid']:
 tag='parse:policy-line-form' if kind=='invalid' else 'parse:policy-tables'
 add('dense-'+kind,malformed(dense,kind),tag,tag,'policy-tables')
 add('experts-'+kind,malformed(expert,kind),tag,tag,'policy-tables')
for i in range(8): add('dense-sigmoid-'+str(i),put(dense,'tsig'+str(i),1),'policy-tables','policy-tables','policy-tables')
for prefix,which in [('tsilu','silu'),('trope','rope'),('texp','exp')]:
 val=int(re.search('^'+prefix+'7 (\\d+)$',dense,re.M).group(1))^1
 add('dense-changed-'+which,put(dense,prefix+'7',val),'policy-tables',ok,'table-digest-'+which)
for k in ['rcl','gcl']:
 t=dense.replace('xl 5\n',k+' 1\nxl 5\n')
 add('dense-'+k,t,'policy-'+k,'policy-'+k,'policy-'+k)
 t=put(expert,k,0)
 add('experts-'+k+'-zero',t,'policy-'+k,'policy-'+k,'policy-'+k)
for k,v,tag in [('hr',1,'header-absent-class'),('wb_r',13,'header-absent-kind')]:
 add('dense-'+tag,put(dense,k,v),'policy-tables' if k=='wb_r' else tag,tag,tag)
add('experts-valid',expert,ok,ok,'met')
add('experts-no-digests',nodigest(expert),ok,ok,'not-met:table-digests')
for prefix,which in [('tsilu','silu'),('tsig','sigmoid'),('trope','rope'),('texp','exp')]:
 val=int(re.search('^'+prefix+'7 (\\d+)$',expert,re.M).group(1))^1
 add('experts-changed-'+which,put(expert,prefix+'7',val),ok,ok,'table-digest-'+which)
# Fixture construction, not a request/standard-form debug execution. The dense kit
# retains the 13 words per layer and packs the unchanged verifier's array plan.
D=F/'dense-base'
D.mkdir()
(D/'policy.txt').write_text(nodigest(dense))
L=int(re.search(r'^L (\d+)$',dense,re.M).group(1))
(D/'KL.bin').write_bytes((kit/'KL.bin').read_bytes()[:4*13*L])
p=run([B/'verifier/cp_verify','-plan','arrays',D,'0'])
save(R/'fixture-array-plan.json',p)
assert p['exit']==4,p
(D/'arrays.txt').write_text(p['output'])
p=run([sys.executable,'-B','prover/tools/pack_layout.py','--arrays',D/'arrays.txt','17','4'])
save(R/'fixture-pack-layout.json',p)
assert p['exit']==0,p
(D/'layout.txt').write_text(p['output'])
lt=int(re.search(r'^lt (\d+)$',dense,re.M).group(1))
n=1<<lt
(F/'request.bin').write_bytes(struct.pack('<'+'I'*(n+2),*([7]*n+[n-1,n])))
(F/'reply.bin').write_bytes(struct.pack('<I',5))
for name,c in sorted(cases.items()):
 d=F/name
 d.mkdir()
 (d/'policy.txt').write_text(c.pop('bytes'))
 src=D if name.startswith('dense-') else kit
 for f in ['KL.bin','layout.txt']: (d/f).write_bytes((src/f).read_bytes())
save(R/'expectations.json',cases)
save(R/'fixture-hashes.json',{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in F.rglob('*') if p.is_file()})
note('Prepared '+str(len(cases))+' synthetic fixtures. Beginning separately labelled supplementary matrix. Original series retained unchanged.')
def reader_tag(p):
 if p['exit']==0: return 'ok'
 m=re.search(r'^parse: (?!ok)([^: ]+)',p['output'],re.M)
 if m: return 'parse:'+m.group(1)
 m=re.search(r'^admission: ([^: ]+)',p['output'],re.M)
 return m.group(1) if m else 'unknown'
def vf_tag(p):
 m=re.search(r'^NO: ([^ :\n]+)',p['output'],re.M)
 if m: return m.group(1)
 m=re.search(r'^plan: not the standard parameter form \((.*?)\)',p['output'],re.M)
 if m: return 'not-met:'+m.group(1)
 return 'met' if p['exit']==4 else 'unknown'
records=[]
counts=[]
for rep in range(1,6):
 errors=0
 for name,c in sorted(cases.items()):
  d=F/name
  observed={}
  for arm in (['before','after'] if rep%2 else ['after','before']):
   p=run([B/(arm+'-release')/'parameter_file_tables_test',d/'policy.txt'])
   p.update(repetition=rep,case=name,arm=arm,mode='release',expected=c[arm])
   p['observed']=reader_tag(p)
   p['matches']=p['observed']==p['expected']
   observed[arm]=p['observed']
   errors+=not p['matches']
   records.append(p)
   save(R/(f'{rep:02}-{name}-{arm}.json'),p)
  if name.startswith('experts-') and observed['before']!=observed['after']: raise SystemExit('KILL: unexplained experts change')
  if c['before'].startswith('parse:') and observed['after']=='ok': raise SystemExit('KILL: malformed group admitted')
  p=run([B/'verifier/cp_verify','-plan','request',d/'policy.txt',d/'KL.bin','0','-layout',d/'layout.txt','-prompt',F/'request.bin','-reply',F/'reply.bin','-q'])
  p.update(repetition=rep,case=name,arm='verifier',mode='release',expected=c['verifier'])
  p['observed']=vf_tag(p)
  p['matches']=p['observed']==p['expected']
  errors+=not p['matches']
  records.append(p)
  save(R/(f'{rep:02}-{name}-verifier.json'),p)
 counts.append(errors)
 note('Release repetition '+str(rep)+' complete: '+str(errors)+' expectation mismatches.')
controls=[]
for arm in ['before','after']:
 for test in ['parameter_file_one_bits_test','parameter_file_one_place_test']:
  source=B/'baseline'/(test+'.cpp') if arm=='before' else 'tests/'+test+'.cpp'
  p=run(['bash','prover/tests/unit.sh','run',source,B/(arm+'-release'),'tests/configurations/pinned_no_proof_of_work/policy.txt'])
  log=B/(arm+'-release')/(test+'.log')
  p['test_output']=clean(log.read_text()) if log.exists() else ''
  controls.append(p)
  save(R/(arm+'-'+test+'.json'),p)
summary={'fixtures':len(cases),'repetitions':5,'reader_calls':len(cases)*10,'verifier_calls':len(cases)*5,'controls':len(controls),'control_failures':sum(p['exit']!=0 for p in controls),'mismatches_per_repetition':counts,'median':statistics.median(counts),'population_sd':statistics.pstdev(counts),'min':min(counts),'max':max(counts),'UBSan':'NOT RUN: unchanged unit.sh offers no sanitizer flags interface','elapsed_since_first_build_seconds':time.time()-budget['first_build_epoch']}
save(R/'summary.json',summary)
print(json.dumps(summary,indent=2))
note('Matrix complete: '+json.dumps(summary))
