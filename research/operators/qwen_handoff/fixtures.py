#!/usr/bin/env python3
"""Synthetic inputs and fixed-slot hostile witnesses. No verifier reads these witnesses."""
import copy
import hashlib
import pathlib
import sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'research/operators/qwen_deltanet'))
import reference as R

MODEL = hashlib.sha256(b'synthetic-deltanet-SA-M1b-handoff-v1').digest()
WEIGHTS = hashlib.sha256(b'synthetic-no-weight-matmul-proved').digest()

def le(words):
    return np.asarray(words, dtype='<i8').tobytes()

def describe(s, c):
    return [s['F'], s['D'], s['C'], s['T'], s['request'], s['layer'], 1, 2,
            c, c*s['C'], s['C'], *s['model'], *s['weights']]

def records(S, toks, F):
    rec = []
    for tok in toks:
        M, delta, S, o = R.step(S, tok, F)
        rec.append((M, delta, S.copy(), o))
    return rec

def generate(seed, D, C):
    R.D = D
    S0, toks, rec = R.fixture(seed, F=12, T=2*C)
    rng = np.random.default_rng(seed+10000)
    xs = rng.integers(-1000, 1000, size=(3+2*C, 3*D), dtype=np.int64)
    s = dict(D=D, C=C, T=2*C, F=12, request=117, layer=3, model=MODEL, weights=WEIGHTS,
             S0=S0, H0=xs[:3].copy(), toks=toks, xs=xs[3:].copy(), outputs=[r[3] for r in rec])
    parts=[]
    for c in range(2):
        sub=toks[c*C:(c+1)*C]
        start=S0 if c==0 else rec[C-1][2]
        parts.append(dict(desc=describe(s,c), S0=start.copy(), toks=copy.deepcopy(sub),
                          F=12, rec=records(start,sub,12), Hin=xs[c*C:c*C+3].copy(),
                          Hout=xs[(c+1)*C:(c+1)*C+3].copy(), xs=xs[c*C+3:(c+1)*C+3].copy()))
    return s,parts

def statement_bytes(s):
    opening=le(s['S0'].reshape(-1))+le(s['H0'].reshape(-1))
    root=hashlib.sha256(b'fp-handoff-initial-v1'+opening).digest()
    out=b'FPHAND01'+le([s['D'],s['F'],s['C'],s['T'],s['request'],s['layer'],1,2])
    out+=s['model']+s['weights']+root+opening
    for t in s['toks']:
        out+=le([t['a'],t['beta']])+le(t['k'])+le(t['v'])+le(t['q'])
    out+=le(s['xs'].reshape(-1))+le(np.asarray(s['outputs']).reshape(-1))
    return out

def write_parts(d,parts):
    d.mkdir(parents=True,exist_ok=True)
    for c,p in enumerate(parts):
        D=p['S0'].shape[0]
        out=le([len(p['toks']),D,p['F']])+le(p['S0'].reshape(-1))
        for t in p['toks']:
            out+=le([t['a'],t['beta']])+le(t['k'])+le(t['v'])+le(t['q'])
        for M,delta,S,o in p['rec']:out+=le(M)+le(delta)+le(S.reshape(-1))+le(o)
        (d/f'c{c}.fx').write_bytes(out)
        (d/f'c{c}.packet').write_bytes(le(p['desc'])+le(p['Hin'].reshape(-1))+le(p['Hout'].reshape(-1))+le(p['xs'].reshape(-1)))

def redo(parts,start=0):
    for c in range(start,2):
        if c>start:parts[c]['S0']=parts[c-1]['rec'][-1][2].copy()
        p=parts[c];p['rec']=records(p['S0'],p['toks'],p['F'])

CASES = ['mixed_F12_F13','split_chunk','replaced_token_inputs','two_sided_history_shift',
         'changed_last_chunk_history','other_layer','other_first_state','dropped_chunk',
         'truncated_window','prefix_only_window','other_model_weights','other_request',
         'changed_intermediate_state']

def hostile(name,s,original):
    p=copy.deepcopy(original)
    if name=='mixed_F12_F13':
        p[1]['F']=13;p[1]['desc'][0]=13;redo(p,1)
    elif name=='split_chunk':
        # A 3-chunk proposal in the fixed two-slot circuit. The additional proposal's metadata
        # is represented, not a third independently verified proof: n=3, shortened first slot.
        for x in p:x['desc'][7]=3
        p[0]['desc'][10]=1;p[1]['desc'][9]=1;p[1]['desc'][10]=1
    elif name=='replaced_token_inputs':
        R.D=s['D'];other=R.gen_tokens(7000+s['request'], 'R1', s['C'],12)
        p[1]['toks']=other;redo(p,1)
    elif name=='two_sided_history_shift':
        p[0]['Hout']=np.roll(p[0]['Hout'],1,axis=0);p[1]['Hin']=p[0]['Hout'].copy()
    elif name=='changed_last_chunk_history':p[1]['Hout'][0,0]+=1
    elif name=='other_layer':
        for x in p:x['desc'][5]+=1
    elif name=='other_first_state':p[0]['S0']+=1;redo(p)
    elif name=='dropped_chunk':
        for x in p:x['desc'][7]=1
        # Empty first slot padded with an identity transition, then the original second chunk.
        for t in p[0]['toks']:t['a']=4096;t['beta']=0
        p[0]['desc'][10]=0;p[1]['desc'][8]=0;p[1]['desc'][9]=0;redo(p)
    elif name=='truncated_window':
        for x in p:x['desc'][3]-=1
        p[1]['desc'][10]-=1;p[1]['toks'][-1]['a']=4096;p[1]['toks'][-1]['beta']=0;redo(p,1)
    elif name=='prefix_only_window':
        for x in p:x['desc'][3]=s['C'];x['desc'][7]=1
        p[1]['desc'][10]=0
        for t in p[1]['toks']:t['a']=4096;t['beta']=0
        redo(p,1)
    elif name=='other_model_weights':
        for x in p:x['desc'][11]^=1;x['desc'][43]^=1
    elif name=='other_request':
        for x in p:x['desc'][4]+=1
    elif name=='changed_intermediate_state':p[1]['S0']+=1;redo(p,1)
    else:raise ValueError(name)
    return p
