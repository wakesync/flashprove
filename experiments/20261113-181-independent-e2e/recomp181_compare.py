"""Post-output comparison only. Never used by the independent reader.

Reads original targets from the frozen git commit, after an independent receipt
exists. The original summarizer is never read, imported or executed.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import recomp181_reader as R

KL = {'median':'kl_median','max':'kl_max','min':'kl_min',
      'sample_sd':'kl_sd','p99_nearest_rank':'kl_p99'}
PKL = {'median':'median','max':'max','min':'min',
       'sample_sd':'sd','p99_nearest_rank':'p99'}

class Comparison:
    def __init__(self):
        self.checks=[]
    def check(self,name,a,b,mode='exact'):
        if mode=='float':
            R.number(a,name)
            R.number(b,name)
            tolerance=1e-12+1e-10*max(abs(a),abs(b))
            ok=abs(a-b)<=tolerance
        elif mode=='rounded':
            # b is a Decimal constructed from the original printed numeric lexeme.
            a=Decimal(str(a))
            tolerance=Decimal('0.5')*(Decimal(10)**b.as_tuple().exponent)+abs(b)*Decimal('1e-12')
            ok=abs(a-b)<=tolerance
        else:
            ok=type(a) is type(b) and a==b
            tolerance=0
        self.checks.append({'field':name,'independent':str(a) if isinstance(a,Decimal) else a,
                            'target':str(b) if isinstance(b,Decimal) else b,'mode':mode,
                            'tolerance':str(tolerance) if isinstance(tolerance,Decimal) else tolerance,'match':ok})

def compare(ind,summary,ledger_text,results_text):
    c=Comparison()
    c.check('source_main',ind['source_main'],R.SOURCE_SHA)
    c.check('cells',sorted(ind['cells']),sorted(l+'/'+a for l in ('stock','abl') for a in R.ARMS))
    c.check('summary.bars',summary['bars'],{'top1':0.99,'kl_median_nats':1e-4,'kl_max_nats':0.1})
    for leg in ('stock','abl'):
        s=summary['legs'][leg]
        c.check(leg+'.finished',True,s['finished'])
        c.check(leg+'.errors',[],s['errors'])
        c.check(leg+'.sanity',ind['checks'][leg]['sanity'],s['sanity_pass'])
        c.check(leg+'.deterministic',ind['global_recorded_determinism'],s['deterministic'])
        c.check(leg+'.BF16H_context_n',ind['bf16h_context_positions'],s['context']['BF16H']['n'])
        for duplicate in ('REF#2','XS18#2'):
            t=s['determinism'][duplicate]
            c.check(leg+'.'+duplicate+'.layers',ind['layer_coverage'][leg]['physical_layers'],t['layers'])
            c.check(leg+'.'+duplicate+'.residual',ind['layer_coverage'][leg]['recorded_residual_determinism'],t['resid_bit_equal_every_layer'])
            c.check(leg+'.'+duplicate+'.logits',ind['checks'][leg]['logit_determinism'],t['logits_bit_equal'])
        for arm in R.ARMS:
            name=leg+'/'+arm
            a=ind['cells'][name]
            b=s['cells'][arm]
            c.check(name+'.n',a['positions'],b['n'])
            c.check(name+'.agree',a['agree'],b['agree'])
            c.check(name+'.fraction',a['agreement_fraction'],b['frac'],'float')
            c.check(name+'.prompt_count',a['prompts'],len(b['per_prompt']))
            c.check(name+'.dead_prompts',[],b['dead_prompts'])
            c.check(name+'.verdict',a['verdict']=='PASS',b['PASS'])
            for x,y in [('top1_ge_99pct','top1'),('kl_median_le_1e_4','kl_median'),('kl_max_le_0_1','kl_max')]:
                c.check(name+'.bar.'+x,a['bars'][x],b['pass'][y])
            c.check(name+'.guard',True,b['pass']['no_guard_error'])
            for x,y in KL.items(): c.check(name+'.kl.'+x,a['kl'][x],b[y],'float')
            c.check(name+'.prompt_ids',sorted(a['per_prompt']),sorted(b['per_prompt']))
            for pid,p in a['per_prompt'].items():
                q=b['per_prompt'][pid]
                c.check(name+'.'+pid+'.n',p['positions'],q['T'])
                c.check(name+'.'+pid+'.agree',p['agree'],q['agree'])
                c.check(name+'.'+pid+'.fraction',p['agreement_fraction'],q['frac'],'float')
                for x,y in PKL.items(): c.check(name+'.'+pid+'.kl.'+x,p['kl'][x],q['kl'][y],'float')
            af=sorted(a['flips'],key=lambda f:(f['prompt'],f['position']))
            bf=sorted(b['flips'],key=lambda f:(f['prompt'],f['pos']))
            c.check(name+'.flip_count',len(af),len(bf))
            for i,(x,y) in enumerate(zip(af,bf)):
                for k,j in [('prompt','prompt'),('position','pos'),('ref_token','ref_top1'),('path_token','path_top1')]:
                    c.check(name+f'.flip{i}.'+k,x[k],y[j])
                c.check(name+f'.flip{i}.margin',x['ref_margin'],y['ref_margin'],'float')
    # Only the JSON-inline metric rows belonging to PR #124, not a general YAML parser.
    block=re.search(r'^    pr: 124\n(.*?)(?=^  - id:|\Z)',ledger_text,re.M|re.S)
    R.require(block is not None,'missing PR124 ledger row')
    metrics=[]
    for line in block.group(1).splitlines():
        if line.startswith('      - {'):
            metrics.append(json.loads(line[8:],parse_float=Decimal))
    by_name={m['name']:m for m in metrics}
    R.require(len(by_name)==len(metrics),'duplicate ledger metric name')
    used=[]
    for leg in ('stock','abl'):
        for arm in R.ARMS:
            a=ind['cells'][leg+'/'+arm]
            suffix=arm.lower()+'_'+leg
            top=by_name['top1_agree_'+suffix]
            used.append(top['name'])
            for key,v in [('value',a['agree']),('n',a['positions']),('total',a['positions'])]:
                c.check('ledger.'+top['name']+'.'+key,v,top[key])
            kl=by_name['kl_median_'+suffix]
            used.append(kl['name'])
            c.check('ledger.'+kl['name']+'.n',a['positions'],kl['n'])
            c.check('ledger.'+kl['name']+'.value',a['kl']['median'],kl['value'],'rounded')
            for key,x in [('sd','sample_sd'),('min','min'),('max','max')]:
                c.check('ledger.'+kl['name']+'.'+key,a['kl'][x],kl['spread'][key],'rounded')
        det=by_name['determinism_'+leg]
        used.append(det['name'])
        c.check('ledger.'+det['name'],int(ind['global_recorded_determinism']),det['value'])
    # Check the four main RESULTS table rows at their printed precision.
    found=set()
    for line in results_text.splitlines():
        m=re.match(r'^\| (XS18|XS20) (stock|abl) \|',line)
        if not m: continue
        arm,leg=m.groups()
        R.require((leg,arm) not in found,'duplicate RESULTS cell')
        found.add((leg,arm))
        cols=[x.strip() for x in line.split('|')[1:-1]]
        a=ind['cells'][leg+'/'+arm]
        nmatch=re.fullmatch(r'([\d,]+) / ([\d,]+) \(([\d.]+)%\)',cols[1])
        R.require(nmatch is not None,'unreadable RESULTS counts')
        c.check('RESULTS.'+leg+'/'+arm+'.agree',a['agree'],int(nmatch[1].replace(',','')))
        c.check('RESULTS.'+leg+'/'+arm+'.n',a['positions'],int(nmatch[2].replace(',','')))
        c.check('RESULTS.'+leg+'/'+arm+'.percent',a['agreement_fraction']*100,Decimal(nmatch[3]),'rounded')
        for i,k in [(2,'median'),(3,'p99_nearest_rank'),(4,'max'),(5,'sample_sd')]:
            c.check('RESULTS.'+leg+'/'+arm+'.'+k,a['kl'][k],Decimal(cols[i]),'rounded')
        c.check('RESULTS.'+leg+'/'+arm+'.verdict',a['verdict'],cols[7].strip('*'))
    R.require(len(found)==4,'missing RESULTS rows')
    mismatches=[r for r in c.checks if not r['match']]
    return {'status':'MATCH' if not mismatches else 'NEGATIVE',
            'scope':'aggregation-only comparison, no whole-experiment replication',
            'comparison_count':len(c.checks),'mismatch_count':len(mismatches),
            'mismatches':mismatches,'checks':c.checks,'ledger_metrics_compared':used,
            'excluded':'BF16H metrics beyond subset count, max-logit-diff aggregates, local-head outlier aggregates and weight manifests are outside this audit'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--independent',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prereg',type=Path,default=Path(__file__).with_name('PREREG.md'))
    a=p.parse_args(argv)
    try:
        R.require(not a.output.exists(),'output exists; use a fresh name')
        # This read happens before any target is opened.
        independent_bytes=a.independent.read_bytes()
        ind=R.loads(independent_bytes.decode())
        blocks=re.findall(r'```json\n(.*?)\n```',a.prereg.read_text(),re.S)
        R.require(len(blocks)==2,'prereg target manifest missing')
        manifest=R.loads(blocks[1])
        targets={}
        for path,digest in manifest.items():
            raw=subprocess.check_output(['git','-C',str(a.repo),'show',R.SOURCE_SHA+':'+path])
            R.require(hashlib.sha256(raw).hexdigest()==digest,'target hash mismatch: '+path)
            targets[path]=raw.decode()
        result=compare(ind,R.loads(targets[R.SOURCE+'/runs/summary.json']),targets['research/results.yaml'],targets[R.SOURCE+'/RESULTS.md'])
        result['independent_sha256']=hashlib.sha256(independent_bytes).hexdigest()
        result['target_sha256']=manifest
        with a.output.open('x') as f: f.write(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
        print(f"{result['status']}: {result['comparison_count']} comparisons, {result['mismatch_count']} mismatches")
        return 0 if result['status']=='MATCH' else 1
    except (R.InvalidEvidence, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as e:
        print('COMPARISON INVALID: '+str(e),file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())
