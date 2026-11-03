#!/usr/bin/env python3
"""Independent integer specification and separate same-oracle circuit lowering."""
from fractions import Fraction
from pathlib import Path
import json, struct, random
P=2**64-2**32+1
SCALE=4
# All public inputs and rounded/linear intermediates are signed four-bit integers.
INPUT=(-3,3,-3,2,3,3) # state, post-exp decay, key, value, beta, scaled query

def reference(x):
    s,d,k,v,b,q=x
    stages={}
    def rounded(name,a,b):
        # Independent rational floor, deliberately not graph divmod.
        z=Fraction(a*b,SCALE); n=z.numerator//z.denominator
        stages[name]=n
        return n
    dec=rounded('decay',s,d)
    mem=rounded('memory',dec,k)
    diff=v-mem; stages['difference']=diff
    delta=rounded('delta',diff,b)
    update=rounded('update',k,delta)
    state=dec+update; stages['state']=state
    out=rounded('output',state,q)
    if any(not -8<=z<=7 for z in (*x,*stages.values())): raise ValueError('overflow: reject, never saturate or wrap')
    return state,out,stages

def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def float_reference(x):
    # Scalar post-gate operation order from pinned Transformers fallback.
    s,d,k,v,b,q=map(lambda z:f32(z/SCALE),x)
    dec=f32(s*d);mem=f32(dec*k);delta=f32(f32(v-mem)*b)
    state=f32(dec+f32(k*delta));return state,f32(state*q)

# Boundary and negative-floor coverage, independent from witness lowering.
for a in range(-8,8):
    for b in range(-8,8):
        n,r=divmod(a*b,SCALE)
        assert n==Fraction(a*b,SCALE).__floor__() and 0<=r<SCALE
rng=random.Random(19); accepted=0;rejected=0;max_error=0
for x in [INPUT]+[tuple(rng.randrange(-8,8) for _ in range(6)) for _ in range(4096)]:
    try:s,o,_=reference(x)
    except ValueError:rejected+=1;continue
    fs,fo=float_reference(x);max_error=max(max_error,abs(s/SCALE-fs),abs(o/SCALE-fo));accepted+=1
expected=reference(INPUT)
table=[];coords=[];wires=[];affines=[];rounds=[];bits=[]
def val(x):return table[x[1]][x[0]]
def rel(terms,target=0):affines.append((terms,target))
def gate(a,b):
    c=len(table);table.append([val(a) if isinstance(a,tuple) else a,val(b) if isinstance(b,tuple) else b,0]);table[c][2]=table[c][0]*table[c][1]
    for row,x in enumerate((a,b)):
        if isinstance(x,tuple):wires.append((*x,row,c))
        else:coords.append((row,c,x))
    return (2,c)
def private(n):
    c=len(table);table.append([n,1,n]);coords.append((1,c,1));return (0,c)
def bounded(x,width,signed):
    offset=2**(width-1) if signed else 0;n=val(x)+offset
    assert 0<=n<2**width
    terms=[(x,1)]
    for i in range(width):
        bit=(n>>i)&1;c=len(table);table.append([bit,bit,bit]);wires.append((0,c,1,c));rel([((2,c),1),((0,c),-1)])
        terms.append(((0,c),-(1<<i)));bits.append(c)
    rel(terms,-offset)
def linear(terms):
    x=private(sum(val(a)*b for a,b in terms));rel([(x,1)]+[(a,-b) for a,b in terms]);bounded(x,4,True);return x
def rounded(a,b):
    product=gate(a,b);n,r=divmod(val(product),SCALE);q=private(n);rem=private(r)
    bounded(q,4,True);bounded(rem,2,False)
    rel([(product,1),(q,-SCALE),(rem,-1)])
    rounds.append((product,q,rem));return q
s,d,k,v,b,q=INPUT
D=rounded(s,d);M=rounded(D,k);V=gate(v,1)
DIFF=linear([(V,1),(M,-1)]);DELTA=rounded(DIFF,b)
U=rounded(k,DELTA);STATE=linear([(D,1),(U,1)]);OUT=rounded(STATE,q)
assert (val(STATE),val(OUT))==expected[:2]
coords.extend([(*STATE,expected[0]),(*OUT,expected[1])])
assert len(table)<=64 and max(len(coords),len(wires),len(affines))<=64
f=lambda n:'F{'+str(n%P)+'ULL}'
lines=['// Generated signed four-bit, scale-four staged-floor fixture.','Table fixture(){Table t(1,3,64);']
for c,values in enumerate(table):
    for r,n in enumerate(values):lines.append(f't.set({r},{c},E::from({f(n)}));')
lines+=['return t;}','std::vector<Coordinate> coordinates={'+','.join('{'+f'{r},{c},{f(n)}'+'}' for r,c,n in coords)+'};','std::vector<WireEquality> wires={'+','.join('{'+','.join(map(str,w))+'}' for w in wires)+'};','std::vector<AffineRelation> relations={'+','.join('{{'+','.join('{'+f'{x[0]},{x[1]},{f(n)}'+'}' for x,n in terms)+'},'+f(target)+'}' for terms,target in affines)+'};']
# Attack all private range bits and all non-public rounded quotient/remainder cells.
attack_cols=bits+[x[1] for _,q,r in rounds for x in (q,r) if x!=OUT]
lines.append('std::vector<unsigned> attack_columns={'+','.join(map(str,attack_cols))+'};')
lines.append(f'constexpr unsigned FIRST_Q={rounds[0][1][1]}, FIRST_R={rounds[0][2][1]};')
here=Path(__file__).resolve().parent
(here/'fixture.h').write_text('\n'.join(lines)+'\n')
(here/'reference.json').write_text(json.dumps(dict(inputs=INPUT,expected=expected,float32_postgate=float_reference(INPUT),float32_implementation='stdlib struct IEEE binary32 rounding after each scalar op; NOT torch or fused kernel execution',boundary_products=256,random_seed=19,comparison_cases=4097,accepted=accepted,overflow_rejected=rejected,max_absolute_state_or_output_divergence=max_error,gates=len(table),coordinates=len(coords),wires=len(wires),affine_rows=len(affines),hostile_proofs=len(attack_cols)+3),indent=2)+'\n')
print('reference: PASS; 256 signed products; 4097 bounded/overflow cases; explicit FP32 divergence recorded')
