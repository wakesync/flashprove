#!/usr/bin/env python3
"""Re-derive the closed no-wrap identities emitted by head.h, plus pinned-table part G.
The connection of these formulas to emitted relations is a source audit, not a formal proof.
"""
import json, pathlib, struct, sys
here=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(here.parent/'qwen_deltanet_m2'))
import norm_alias_regression as design
p=2**64-2**32+1; c=2**23-1; limb=2**12-1
r24=limb*(1+2**12);r36=limb*(1+2**12+2**24)
F=4096;delta=(2**18+1)*c
# Substitute operand ties of build(): M+g6.a=v, delta=2^18 hi+lo, sigma/Rc=limbs.
# S2/S4 duplicate sigma's limb sum instead of G_ss.a. Substitution is identical.
rows={
 'I1 M floor: 2^2F M + r - a sum_i S_i k_i':F*F*c+r24+F*128*c*F,
 'I2 delta floor: 2^F delta + r - (v - M) beta':F*delta+limb+(2**31-1+c)*F,
 "I3 state floor: 2^F S' + r - a S - k_i delta_j":F*c+limb+F*c+F*delta,
 "I4 output floor: 2^F o + r - sum_i S'_i q_i":F*c+limb+128*c*F,
 'I5 state ends: cell - S0, cell - S_T':c+2**18-1,
 "N1 e1: sum o^2 + eps' - sigma^2 - e1":128*c*c+2147+r24*r24+r24,
 "N2 e2: sigma^2 + 2 sigma - sum o^2 - eps' - e2":r24*r24+2*r24+128*c*c+2147+r24,
 'N3 rr: Rc sigma + rr - 2^36':r36*r24+r24+2**36,
 'N4 gap: sigma - 1 - rr - gap':r24+1+r24+r24,
 'N5 w floor: 2^24 w + r - o Rc':2**24*c+r24+c*r36,
 'N6 y floor: cg w - 2^F y - r':r24*c+F*(2**31-1)+limb}
assert rows==design.ledger(design.CLASS)
assert all(x<p for x in rows.values())
table=struct.unpack('<4096q',(here/'tables/silu-f12.i64le').read_bytes())
g=[]
for gain in (10000,14100,14143,20000):
    # Gain encoding is round-half-up of gain*46341, an integer fixed configuration.
    G=(gain*46341+5000)//10000
    maximum=max(abs(G*v//4096) for v in table)
    g.append(dict(gain_x10000=gain,G=G,max_abs_cg=maximum,below_bound=maximum<2**24))
# Domain is [-32768,32767], a strict subset of decoded z class. Every other z is derive reject.
result=dict(ledger=rows,all_below_p=True,matches_design_closed_identities=True,
 term_difference=dict(build=4782528,model=4782496,extra_per_token=2,tokens=16,
 explanation='S2/S4 each bind an operand to two sigma limbs (3 terms), model binds to G_ss.a (2 terms)'),
 pinned_G=dict(rows=g,admitted_z_values=65536,outside_domain_z_values=2**21-1-65536),
 isqrt='pure integer; squares and neighbours through INT64_MAX tested by isqrt_test.cpp')
print(json.dumps(result,indent=2))
