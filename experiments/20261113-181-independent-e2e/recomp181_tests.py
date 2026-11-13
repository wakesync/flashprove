"""Wholly synthetic fixtures; no historical measured records are read here."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import recomp181_reader as R

COUNTS = {'p01-ordinary-short': 3, 'synthetic-other': 2}
BF = {'synthetic-other'}
DET = {'p01-ordinary-short'}
LAYERS = {'stock': {0,1,2,3}, 'abl': {3}}

def fixture():
    prompts = []
    for pid,n in COUNTS.items():
        ids = list(range(100,100+n))
        prompts.append({'id':pid, 'origin':'synthetic', 'text':'synthetic', 'n_tokens':n,
                        'token_ids':ids,'ids_sha256':hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
    b = {'prompts':{'tokenizer_sha256':'0'*64, 'n_prompts':2, 'total_tokens':5,
         'bf16h_subset':sorted(BF),'determinism_subset':sorted(DET),'prompts':prompts},
         'e2e':{},'divergence':{},'heads':{},'errors':{}}
    for leg in LAYERS:
        d = {'leg':leg,'checkpoint':leg,'note':'synthetic fixture only','seconds':0,
             'sanity_p01_last_top1':25358,'sanity_pass':True,'prompts':{}}
        for pid,n in COUNTS.items():
            tokens = [25358]*n
            paths = {}
            for arm in R.path_ids(pid,BF,DET):
                paths[arm] = {'top1_agree':[True]*n, 'top1_path':tokens.copy(),
                              'kl':[0.0]*n,'maxdiff_over_std':[0.0]*n}
            d['prompts'][pid] = {'T':n,'ref_top1':tokens,'ref_margin':[1.0]*n,'paths':paths}
        b['e2e'][leg] = d
        b['divergence'][leg], b['heads'][leg], b['errors'][leg] = [],[],[]
        for l in sorted(LAYERS[leg]):
            linear = l%4 != 3
            row = {'leg':leg,'layer':l,'type':'linear_attention' if linear else 'full_attention','seconds':0,
                   'det_bit_equal':{a+'|'+p:True for a in ('REF#2','XS18#2') for p in DET}}
            if linear:
                row['inputs_s'] = 0
            for arm,ids in R.path_prompts(COUNTS,BF,DET).items():
                row[arm] = {p:0.0 for p in ids}
            b['divergence'][leg].append(row)
            if linear:
                for arm in ('XS18','XS20','XS18#2'):
                    for p in R.path_prompts(COUNTS,BF,DET)[arm]:
                        b['heads'][leg].append({'leg':leg,'layer':l,'path':arm,'prompt':p,'rel_y':[0.0]*48})
    return b

def evaluate(b):
    return R.aggregate(b, COUNTS, BF, DET, LAYERS)

def set_at(obj,path,value):
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = value

class ReaderTests(unittest.TestCase):
    def invalid(self, change):
        b = fixture()
        change(b)
        with self.assertRaises((R.InvalidEvidence,ValueError,TypeError)):
            evaluate(b)

    def test_positive_synthetic_and_shared_prefix(self):
        result = evaluate(fixture())
        self.assertEqual(len(result['cells']),4)
        self.assertTrue(all(c['verdict']=='PASS' for c in result['cells'].values()))
        self.assertEqual(result['layer_coverage']['abl']['physical_layers'],1)
        self.assertEqual(result['bf16h_context_positions'],2)

    def test_prompt_missing_extra_duplicate(self):
        changes = [lambda b:b['prompts']['prompts'].pop(),
                   lambda b:b['prompts']['prompts'].append(copy.deepcopy(b['prompts']['prompts'][0])),
                   lambda b:b['prompts']['prompts'][0].update(id='extra'),
                   lambda b:b['e2e']['stock']['prompts'].pop('synthetic-other'),
                   lambda b:b['e2e']['stock']['prompts'].update(extra={}),
                   lambda b:b['prompts'].update(n_prompts=3),
                   lambda b:b['prompts'].update(total_tokens=6),
                   lambda b:b['prompts']['bf16h_subset'].append('synthetic-other'),
                   lambda b:b['prompts']['determinism_subset'].clear()]
        for i, change in enumerate(changes):
            with self.subTest(i=i): self.invalid(change)

    def test_all_per_position_arrays_lengths_and_T(self):
        for field in ('ref_top1','ref_margin'):
            with self.subTest(field=field):
                self.invalid(lambda b:b['e2e']['stock']['prompts']['p01-ordinary-short'][field].pop())
        for field in ('top1_agree','top1_path','kl','maxdiff_over_std'):
            for delta in ('short','long'):
                with self.subTest(field=field,delta=delta):
                    def change(b):
                        a=b['e2e']['abl']['prompts']['synthetic-other']['paths']['XS20'][field]
                        a.pop() if delta=='short' else a.append(a[0])
                    self.invalid(change)
        self.invalid(lambda b:b['e2e']['abl']['prompts']['synthetic-other'].update(T=3))
        self.invalid(lambda b:b['prompts']['prompts'][0].update(n_tokens=2))
        self.invalid(lambda b:b['prompts']['prompts'][0]['token_ids'].pop())
        self.invalid(lambda b:b['prompts']['prompts'][0].update(ids_sha256='f'*64))

    def test_token_flag_types_and_domains(self):
        path=['e2e','stock','prompts','synthetic-other','paths','XS20']
        for field, v in [('top1_path',25359),('top1_path',-1),('top1_path',248320),
                         ('top1_path',True),('top1_path',25358.0),('top1_agree',False),
                         ('top1_agree',1),('kl',True),('maxdiff_over_std',-1.0)]:
            with self.subTest(field=field,v=v):
                self.invalid(lambda b:set_at(b,path+[field,0],v))

    def test_layer_missing_extra_duplicate_and_wrong_type(self):
        for leg in LAYERS:
            for kind in ('missing','extra','duplicate','wrong_type','leg','missing_prompt','extra_prompt'):
                with self.subTest(leg=leg,kind=kind):
                    def change(b):
                        rows=b['divergence'][leg]
                        if kind=='missing': rows.pop()
                        elif kind=='extra':
                            r=copy.deepcopy(rows[0])
                            r['layer']=63
                            rows.append(r)
                        elif kind=='duplicate': rows.append(copy.deepcopy(rows[0]))
                        elif kind=='wrong_type': rows[0]['type']='not_attention'
                        elif kind=='leg': rows[0]['leg']='wrong'
                        elif kind=='missing_prompt': rows[0]['XS18'].pop('synthetic-other')
                        else: rows[0]['XS20']['extra']=0
                    self.invalid(change)

    def test_head_missing_extra_duplicate_truncated(self):
        for kind in ('missing','extra','duplicate','short','long','negative','bool','missing_det_path'):
            with self.subTest(kind=kind):
                def change(b):
                    rows=b['heads']['stock']
                    if kind=='missing': rows.pop()
                    elif kind=='extra': rows[0]['layer']=63
                    elif kind=='duplicate': rows.append(copy.deepcopy(rows[0]))
                    elif kind=='short': rows[0]['rel_y'].pop()
                    elif kind=='long': rows[0]['rel_y'].append(0)
                    elif kind=='negative': rows[0]['rel_y'][0]=-1
                    elif kind=='bool': rows[0]['rel_y'][0]=False
                    else: b['heads']['stock']=[r for r in rows if r['path']!='XS18#2']
                self.invalid(change)

    def test_determinism_missing_and_false(self):
        self.invalid(lambda b:b['divergence']['stock'][0].pop('det_bit_equal'))
        self.invalid(lambda b:b['divergence']['abl'][0]['det_bit_equal'].clear())
        self.invalid(lambda b:b['e2e']['stock']['prompts']['p01-ordinary-short']['paths'].pop('REF#2'))
        self.invalid(lambda b:b['divergence']['stock'][0]['det_bit_equal'].update({'REF#2|p01-ordinary-short':1}))
        changes=[lambda b:b['divergence']['stock'][0]['det_bit_equal'].update({'REF#2|p01-ordinary-short':False}),
                 lambda b:b['divergence']['abl'][0]['REF#2'].update({'p01-ordinary-short':1e-9}),
                 lambda b:b['divergence']['abl'][0]['XS18#2'].update({'p01-ordinary-short':1e-9}),
                 lambda b:set_at(b,['e2e','stock','prompts','p01-ordinary-short','paths','XS18#2','kl',0],1e-9),
                 lambda b:set_at(b,['e2e','abl','prompts','p01-ordinary-short','paths','REF#2','maxdiff_over_std',0],1e-9)]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                b=fixture()
                change(b)
                r=evaluate(b)
                self.assertFalse(r['global_recorded_determinism'])
                self.assertTrue(all(c['verdict']=='FAIL' for c in r['cells'].values()))

    def test_sanity_and_guard(self):
        self.invalid(lambda b:b['e2e']['stock'].update(sanity_pass=False))
        self.invalid(lambda b:b['e2e']['stock'].update(sanity_p01_last_top1=42))
        self.invalid(lambda b:b['errors']['abl'].append({'error':'OverflowError'}))
        self.invalid(lambda b:b['e2e']['stock']['prompts']['synthetic-other']['paths']['XS20'].update(error='OverflowError'))
        b=fixture()
        p=b['e2e']['stock']['prompts']['p01-ordinary-short']
        p['ref_top1'][-1]=42
        for q in p['paths'].values(): q['top1_path'][-1]=42
        b['e2e']['stock'].update(sanity_pass=False,sanity_p01_last_top1=42)
        self.assertTrue(all(c['verdict']=='FAIL' for c in evaluate(b)['cells'].values()))

    def test_nonfinite_json_and_duplicate_keys(self):
        for text in ('{"x":NaN}','{"x":Infinity}','{"x":-Infinity}',
                     '{"x":1e999}','{"x":0,"x":1}','{"p":{"a":1,"a":2}}'):
            with self.subTest(text=text), self.assertRaises(R.InvalidEvidence): R.loads(text)
        for value in (float('nan'),float('inf'),-float('inf')):
            for path in (['e2e','stock','prompts','synthetic-other','paths','XS20','kl',0],
                         ['divergence','stock',0,'XS18','synthetic-other'],
                         ['heads','stock',0,'rel_y',0]):
                with self.subTest(value=value,path=path): self.invalid(lambda b:set_at(b,path,value))

    def test_negative_kl_retained_at_registered_tolerance(self):
        b=fixture()
        b['e2e']['stock']['prompts']['synthetic-other']['paths']['XS20']['kl'][0]=-1e-12
        r=evaluate(b)['cells']['stock/XS20']
        self.assertEqual(r['kl']['min'],-1e-12)
        self.assertEqual(r['negative_kl'][0]['kl'],-1e-12)
        self.assertEqual(r['verdict'],'PASS')
        self.invalid(lambda b:set_at(b,['e2e','stock','prompts','synthetic-other','paths','XS20','kl',0],math.nextafter(-1e-12,-math.inf)))

    def test_threshold_edges_inclusive_no_epsilon(self):
        self.assertTrue(all(R.bars(99,100,1e-4,0.1).values()))
        self.assertFalse(R.bars(98,100,1e-4,0.1)['top1_ge_99pct'])
        self.assertTrue(R.bars(1447,1461,0,0)['top1_ge_99pct'])
        self.assertFalse(R.bars(1446,1461,0,0)['top1_ge_99pct'])
        self.assertFalse(R.bars(100,100,math.nextafter(1e-4,math.inf),0.1)['kl_median_le_1e_4'])
        self.assertFalse(R.bars(100,100,1e-4,math.nextafter(0.1,math.inf))['kl_max_le_0_1'])
        self.assertTrue(all(R.bars(100,100,math.nextafter(1e-4,-math.inf),math.nextafter(0.1,-math.inf)).values()))

    def test_median_sd_and_nearest_rank(self):
        s=R.stats([4,1,3,2])
        self.assertEqual(s['median'],2.5)
        self.assertAlmostEqual(s['sample_sd'],math.sqrt(5/3))
        self.assertEqual(s['p99_nearest_rank'],4)
        self.assertEqual(R.stats(list(range(1,101)))['p99_nearest_rank'],99)
        self.assertEqual(R.stats(list(range(1,1462)))['p99_nearest_rank'],1447)

    def test_flip_recovered_from_ids(self):
        b=fixture()
        q=b['e2e']['abl']['prompts']['synthetic-other']['paths']['XS20']
        q['top1_path'][1]=17
        q['top1_agree'][1]=False
        c=evaluate(b)['cells']['abl/XS20']
        self.assertEqual(c['agree'],4)
        self.assertEqual(c['flips'],[{'checkpoint':'abl','arm':'XS20','prompt':'synthetic-other','position':1,
                                      'ref_token':25358,'path_token':17,'ref_margin':1.0}])
        self.assertEqual(c['verdict'],'FAIL')

    def test_cli_rejection_no_output_and_hash_admission(self):
        # Synthetic serialization exercises the same strict CLI admission before fixed-denominator check.
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            src=d/'source'
            (src/'runs').mkdir(parents=True)
            b=fixture()
            files={'PREREG.md':'synthetic source prereg','e2e.py':'synthetic non-executable provenance',
                   'prompts-e2e.json':json.dumps(b['prompts'])}
            for leg in LAYERS:
                files['runs/e2e-'+leg+'.json']=json.dumps(b['e2e'][leg])
                for name in ('divergence','heads'):
                    files['runs/'+name+'-'+leg+'.jsonl']=''.join(json.dumps(x)+'\n' for x in b[name][leg])
            hashes={name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()}
            for leg in LAYERS: hashes['runs/errors-'+leg+'.jsonl']=None
            for name,text in files.items(): (src/name).write_text(text)
            prereg=d/'PREREG.md'
            prereg.write_text('```json\n'+json.dumps(hashes)+'\n```\n```json\n{}\n```\n')
            # Hashes admit the synthetic files, pure API validates their synthetic contract.
            loaded,_=R.read_bundle(src,hashes)
            self.assertEqual(evaluate(loaded)['cells']['stock/XS18']['verdict'],'PASS')
            def reject():
                out=d/'never-created.json'
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    rc=R.main(['--source',str(src),'--prereg',str(prereg),'--output',str(out)])
                self.assertEqual(rc,2)
                self.assertFalse(out.exists())
            reject()  # CLI cannot be relaxed to accept synthetic denominator.
            p=src/'runs/e2e-stock.json'
            original=p.read_text()
            p.write_text(original+' ')
            reject()
            p.write_text(original)
            (src/'runs/errors-stock.jsonl').write_text('')
            reject()  # Even an empty unexpected error log violates the pinned manifest.
            (src/'runs/errors-stock.jsonl').unlink()
            hashes.pop('runs/heads-abl.jsonl')
            prereg.write_text('```json\n'+json.dumps(hashes)+'\n```\n```json\n{}\n```\n')
            reject()

if __name__=='__main__':
    unittest.main(verbosity=2)
