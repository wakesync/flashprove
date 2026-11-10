#!/usr/bin/env python3
"""Runs the upstream planner (`cp_verify -plan arrays`) on proxy shapes and sums its arrays.

Why: the dense family of Qwen3.8-27B (norms, projections, SwiGLU MLP, softmax attention, output
head) is an operator family the upstream prover already proves. Its planner prints every array a
request's proof commits to, with rows and columns, for any shape it admits. That is a count from
the program that would run, not a guess. This script makes proxy parameter files from the stored
full-size configuration by changing shape lines only, runs the planner, and writes the sums.

A proxy is NOT a Qwen configuration. It has Maverick's attention (40 x 128 heads, since the
planner requires H * dh = d) and no DeltaNet. It is used for three things only: the layer link of
a dense layer at f = 17,408, the output head at V = 248,320, and the linearity of both in f and V.

usage: planner_proxy.py --cp-verify <path to cp_verify> --out <runs dir>
No GPU. Each planner call takes a few seconds.
"""
import argparse, collections, json, os, shutil, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BASE = os.path.join(ROOT, 'prover', 'examples', 'target_full_f2')

# name -> shape overrides on target_full_f2. 'dense' switches the experts off (NE 0).
PROXIES = collections.OrderedDict([
    ('maverick', dict()),
    ('dense_f8192', dict(dense=True, f=8192)),
    ('dense_f16384', dict(dense=True, f=16384)),
    ('dense_f17408', dict(dense=True, f=17408)),
    ('dense_f17408_V248320', dict(dense=True, f=17408, V=248320)),
    ('dense_f17408_V248320_L64', dict(dense=True, f=17408, V=248320, L=64)),
    # descriptive, not registered: the slope in the key / value width (G 8 -> 4 halves dkv), and the
    # small synthetic example this fork has timed on an H100 (PR #23, #26)
    ('dense_f17408_G4', dict(dense=True, f=17408, G=4)),
    ('small_roomy', dict(base='target_small_f2_roomy')),
])


DIGEST = ('tsilu', 'tsig', 'trope', 'texp')
EXPERT_SEGMENTS = ('XR', 'LR', 'LT', 'DD', 'LH', 'SEL', 'L3', 'CLR', 'MR', 'G0', 'CG')
EXPERT_KINDS = ('wb_gs', 'wb_us', 'wb_gr', 'wb_ur', 'wb_dnr', 'wb_r')


def make_config(dst, dense=False, f=None, V=None, L=None, G=None, base=None):
    """Writes policy.txt and KL.bin of a proxy. 'dense' follows the repository's own recipe for a
    model without experts (verifier/tests/served_form_test.py, no_experts()): NE 0, hr 0, the six
    expert weight kinds 0, no rcl / gcl lines, no table digest lines, the router's and the clamps'
    lookup segments out of the call lines, iota_0..7 recomputed (verifier/tests/forest_lines.py),
    and KL.bin cut to 13 words a layer."""
    sys.path.insert(0, os.path.join(ROOT, 'verifier', 'tests'))
    import forest_lines
    src = os.path.join(ROOT, 'prover', 'examples', base) if base else BASE
    lines = open(os.path.join(src, 'policy.txt')).read().split('\n')
    kl = open(os.path.join(src, 'KL.bin'), 'rb').read()
    words = list(struct.unpack('<%dI' % (len(kl) // 4), kl))
    L0 = int([x for x in lines if x.startswith('L ')][0].split(' ')[1])

    def put(name, value):
        for i, x in enumerate(lines):
            if x.split(' ')[0] == name:
                lines[i] = '%s %d' % (name, value)
                return
        raise SystemExit('no line ' + name)

    if f is not None:
        put('f', f)
    if V is not None:
        put('V', V)
    if L is not None:
        put('L', L)
    if G is not None:
        put('G', G)
    if dense:
        put('NE', 0); put('hr', 0)
        if f is not None:
            put('fe', f // 2)
        for k in EXPERT_KINDS:
            put(k, 0)
        lines[:] = [x for x in lines if x.split(' ')[0] not in ('rcl', 'gcl') and not any(x.startswith(t) and x[len(t)].isdigit() for t in DIGEST if len(x) > len(t))]
        cut = [' '.join(w for i, w in enumerate(x.split(' ')) if i < 3 or w not in EXPERT_SEGMENTS) if x.startswith('call ') else x for x in lines]
        lines[:] = [x for x in cut if not (x.startswith('call ') and len(x.split(' ')) < 4)]
    text = '\n'.join(lines)
    value = forest_lines.values_of(text)
    fit = forest_lines.layer(value, forest_lines.calls_of(text))
    for k, v in fit.items():
        put(k, v)
    open(os.path.join(dst, 'policy.txt'), 'w').write('\n'.join(lines))
    nl = L if L is not None else L0
    if dense:
        kw = []
        for l in range(nl):
            kw += words[13 * (l % L0): 13 * (l % L0) + 13]
    else:
        kw = words
    open(os.path.join(dst, 'KL.bin'), 'wb').write(struct.pack('<%dI' % len(kw), *kw))


def run(cp_verify, name, kw, outdir):
    d = tempfile.mkdtemp(prefix='m3proxy-')
    try:
        make_config(d, **kw)
        r = subprocess.run([cp_verify, '-plan', 'arrays', d, '128'], capture_output=True, text=True)
        txt = r.stdout
        open(os.path.join(outdir, 'planner-%s.arrays.txt' % name), 'w').write(txt)
        err = [l for l in (r.stdout + r.stderr).split('\n') if l and not l.startswith('array:')]
    finally:
        shutil.rmtree(d)
    links = collections.OrderedDict()
    for l in txt.split('\n'):
        if not l.startswith('array:'): continue
        p = l.split()
        link, cls, rows, cols, nm = int(p[1]), p[4], int(p[7]), int(p[8]), p[10]
        e = links.setdefault(link, dict(entries=0, cells=0, other=0, by_class=collections.Counter()))
        n = rows * cols
        e['entries'] += n; e['by_class'][cls] += n
        # 'M' arrays hold packed cells (three cell rows to a packed row); U3, ZZ, BZ do not
        if nm.startswith('M'): e['cells'] += n
        else: e['other'] += n
    sizes = [v['entries'] for v in links.values()]
    res = dict(name=name, overrides=kw, exit_code=r.returncode, links=len(links), entries_total=sum(sizes),
               planner_messages=err[:6])
    if links:
        ks = list(links)
        head = links[ks[-1]]
        layer = [links[k] for k in ks[:-1][0::2]]
        attn = [links[k] for k in ks[:-1][1::2]]
        res.update(
            layer_links=len(layer), attention_links=len(attn),
            layer_link_entries_first=layer[0]['entries'] if layer else None,
            layer_link_entries_typical=layer[1]['entries'] if len(layer) > 1 else None,
            layer_link_cells_typical=layer[1]['cells'] if len(layer) > 1 else None,
            layer_link_other_typical=layer[1]['other'] if len(layer) > 1 else None,
            attention_link_entries=attn[0]['entries'] if attn else None,
            attention_link_cells=attn[0]['cells'] if attn else None,
            head_link_entries=head['entries'], head_link_cells=head['cells'],
            largest_link_entries=max(sizes))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cp-verify', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    res = collections.OrderedDict()
    for name, kw in PROXIES.items():
        res[name] = run(a.cp_verify, name, kw, a.out)
        print(name, json.dumps({k: v for k, v in res[name].items() if k != 'overrides'}))
    # H4: linearity of the layer link in f
    a8, a16, a17 = (res.get(k, {}).get('layer_link_entries_typical') for k in ('dense_f8192', 'dense_f16384', 'dense_f17408'))
    if a8 and a16 and a17:
        slope = (a16 - a8) / (16384 - 8192)
        pred = a16 + slope * (17408 - 16384)
        res['H4'] = dict(f8192=a8, f16384=a16, f17408=a17, predicted_f17408=round(pred), error=abs(pred - a17) / a17,
                         pass_=abs(pred - a17) / a17 <= 0.01)
    else:
        res['H4'] = dict(pass_=False, note='the planner did not return arrays for one of the three shapes')
    open(os.path.join(a.out, 'planner-proxy.json'), 'w').write(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res['H4']))


if __name__ == '__main__':
    main()
