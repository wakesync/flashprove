#!/usr/bin/env python3
"""Float is used ONLY in this fidelity reference, never the table/proof path."""
import json
import math
import pathlib
import random
import statistics
import sys
from tables import load

HERE=pathlib.Path(__file__).resolve().parent
RUNS=HERE.parents[2]/'experiments/20261109-35-qwen-operators/runs'


def distribution(xs):
    s=sorted(xs)
    return dict(n=len(s),median=statistics.median(s),p95=s[math.ceil(.95*len(s))-1],max=max(s),min=min(s),sd=statistics.stdev(s))


def main(op):
    out=[]
    for f in (12,14,16):
        S=1<<f
        if op=='nonlinear':
            rng=random.Random(35)
            # Integer quantized inputs sampled uniformly; include every grid edge and last ulp.
            xs=[rng.randrange(-8*S,8*S) for _ in range(4096)]
            xs += [(i-2048)*(S//256) for i in range(4096)]
            xs += [-8*S,8*S-1,0,-1,1]
            names=['silu','sigmoid','softplus','decay-half','decay-one','decay-two']
            for j,name in enumerate(names):
                tab=load(name,f); errors=[]
                for X in xs:
                    x=X/S;sig=1/(1+math.exp(-x));sp=math.log1p(math.exp(x))
                    ref=[x*sig,sig,sp,math.exp(-.5*sp),math.exp(-sp),math.exp(-2*sp)][j]
                    got=tab[X//(S//256)+2048]/S
                    errors.append(abs(got-ref))
                out.append(dict(op=name,F=f,threshold=.006,passed=max(errors)<=.006,error=distribution(errors)))
        elif op=='conv':
            errors=[]
            for seed in range(1,11):
                rng=random.Random(seed)
                x=[rng.randrange(-S,S) for _ in range(7)]
                w=[rng.randrange(-S,S) for _ in range(4)]
                for t in range(4):
                    num=sum(x[t+j]*w[j] for j in range(4))
                    got=(num//S)/S
                    ref=sum((x[t+j]/S)*(w[j]/S) for j in range(4))
                    errors.append(abs(got-ref))
            out.append(dict(op=op,F=f,threshold=1/S,passed=max(errors)<=1/S,error=distribution(errors)))
        elif op=='rotary':
            from rotary_tables import load as rotary_load
            tab=rotary_load(f); errors=[]; positions=[]; unchanged=0
            for seed in range(1,11):
                rng=random.Random(seed); pos=rng.randrange(1024);positions.append(pos)
                xs=[rng.randrange(-S,S) for _ in range(256)]
                ys=xs.copy()
                for j in range(32):
                    C,U=tab[64*pos+2*j:64*pos+2*j+2]
                    ys[j]=(xs[j]*C-xs[j+32]*U)//S
                    ys[j+32]=(xs[j+32]*C+xs[j]*U)//S
                    angle=pos*math.pow(10000000,-j/32)
                    c,s=math.cos(angle),math.sin(angle)
                    ref=(xs[j]*c-xs[j+32]*s)/S
                    ref2=(xs[j+32]*c+xs[j]*s)/S
                    errors.extend((abs(ys[j]/S-ref),abs(ys[j+32]/S-ref2)))
                unchanged+=sum(ys[j]==xs[j] for j in range(64,256))
            assert unchanged==1920
            out.append(dict(op=op,F=f,threshold=2/S,passed=max(errors)<=2/S,
                            error=distribution(errors),positions=positions,unchanged=unchanged))
        else:
            D=128 if op=='l2' else 256
            tab=load('l2-128' if op=='l2' else 'rsqrt',f)
            errors=[];keys=[]
            for seed in range(1,11):
                rng=random.Random(seed)
                xs=[rng.randrange(-S,S) for _ in range(D)]
                energy=sum(x*x for x in xs)
                key=(1024*energy)//(D*S*S)-256
                assert 0<=key<4096
                keys.append(key)
                for x in xs:
                    got=((x*tab[key])//S)/S
                    ref=(x/S)/math.sqrt(energy/(S*S*(1 if op=='l2' else D)))
                    errors.append(abs(got-ref))
            out.append(dict(op=op,F=f,threshold=.01,passed=max(errors)<=.01,error=distribution(errors),keys=keys))
    RUNS.mkdir(exist_ok=True)
    (RUNS/f'{op}-fidelity.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
    assert all(r['passed'] for r in out)


if __name__=='__main__':main(sys.argv[1])
