"""Comparator mutations on wholly synthetic aggregates, never source measurements."""
import copy
import json
import unittest
import recomp181_compare as C
import recomp181_tests as T


def targets():
    b=T.fixture()
    # A real synthetic flip exercises exact identity/margin comparison.
    q=b['e2e']['abl']['prompts']['synthetic-other']['paths']['XS20']
    q['top1_path'][1]=17
    q['top1_agree'][1]=False
    ind=T.evaluate(b)
    summary={'bars':{'top1':0.99,'kl_median_nats':1e-4,'kl_max_nats':0.1},'legs':{}}
    metrics=[]
    lines=[]
    for leg in ('stock','abl'):
        s={'finished':True,'errors':[],'sanity_pass':True,'deterministic':True,
           'context':{'BF16H':{'n':2}},'determinism':{},'cells':{}}
        for duplicate in ('REF#2','XS18#2'):
            s['determinism'][duplicate]={'layers':len(T.LAYERS[leg]),'resid_bit_equal_every_layer':True,'logits_bit_equal':True}
        for arm in ('XS18','XS20'):
            a=ind['cells'][leg+'/'+arm]
            c={'n':a['positions'],'agree':a['agree'],'frac':a['agreement_fraction'],
               'per_prompt':{},'dead_prompts':[],'PASS':a['verdict']=='PASS',
               'pass':{'top1':a['bars']['top1_ge_99pct'],'kl_median':True,'kl_max':True,'no_guard_error':True},'flips':[]}
            for x,y in C.KL.items(): c[y]=a['kl'][x]
            for pid,p in a['per_prompt'].items():
                c['per_prompt'][pid]={'T':p['positions'],'agree':p['agree'],'frac':p['agreement_fraction'],
                                      'kl':{y:p['kl'][x] for x,y in C.PKL.items()}}
            for f in a['flips']:
                c['flips'].append({'prompt':f['prompt'],'pos':f['position'],'ref_top1':f['ref_token'],
                                   'path_top1':f['path_token'],'ref_margin':f['ref_margin']})
            s['cells'][arm]=c
            suffix=arm.lower()+'_'+leg
            metrics.append({'name':'top1_agree_'+suffix,'value':a['agree'],'n':5,'total':5})
            metrics.append({'name':'kl_median_'+suffix,'value':0.0,'n':5,'spread':{'sd':0.0,'min':0.0,'max':0.0}})
            lines.append(f"| {arm} {leg} | {a['agree']} / 5 ({a['agreement_fraction']*100}%) | 0.0 | 0.0 | 0.0 | 0.0 | unused | **{a['verdict']}** |")
        metrics.append({'name':'determinism_'+leg,'value':1})
        summary['legs'][leg]=s
    ledger='    pr: 124\n    metrics:\n'+''.join('      - '+json.dumps(m)+'\n' for m in metrics)
    return ind,summary,ledger,'\n'.join(lines)

class ComparatorTests(unittest.TestCase):
    def test_honest_synthetic_targets(self):
        r=C.compare(*targets())
        self.assertEqual(r['mismatch_count'],0)
        self.assertEqual(r['status'],'MATCH')

    def test_count_flip_margin_decision_and_aggregate_mutations_are_negative(self):
        for kind in ('count','flip_position','flip_id','flip_missing','margin','verdict','bar','median','sd','sanity','determinism'):
            with self.subTest(kind=kind):
                ind,s,ledger,text=targets()
                cell=s['legs']['abl']['cells']['XS20']
                if kind=='count': cell['n']+=1
                elif kind=='flip_position': cell['flips'][0]['pos']+=1
                elif kind=='flip_id': cell['flips'][0]['path_top1']+=1
                elif kind=='flip_missing': cell['flips']=[]
                elif kind=='margin': cell['flips'][0]['ref_margin']+=1e-3
                elif kind=='verdict': cell['PASS']=not cell['PASS']
                elif kind=='bar': cell['pass']['kl_median']=False
                elif kind=='median': cell['kl_median']=1e-3
                elif kind=='sd': cell['kl_sd']=1e-3
                elif kind=='sanity': s['legs']['abl']['sanity_pass']=False
                else: s['legs']['abl']['deterministic']=False
                r=C.compare(ind,s,ledger,text)
                self.assertEqual(r['status'],'NEGATIVE')
                self.assertGreater(r['mismatch_count'],0)

    def test_float_and_rounded_tolerances(self):
        from decimal import Decimal
        c=C.Comparison()
        c.check('inside',1.0,1.0+1e-11,'float')
        c.check('outside',1.0,1.0+1e-8,'float')
        c.check('round_inside',0.0024034514146649144,Decimal('0.002403'),'rounded')
        c.check('round_outside',0.0024036,Decimal('0.002403'),'rounded')
        self.assertEqual([r['match'] for r in c.checks],[True,False,True,False])

if __name__=='__main__':
    unittest.main(verbosity=2)
