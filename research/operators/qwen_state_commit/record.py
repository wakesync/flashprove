#!/usr/bin/env python3
"""Receipt for experiment 20261109-34-qwen-state-commit, strategy SA (CPU only).

Usage: record.py [build] [honest C...] [hostile C...]
  build          compile chunk.bin
  honest 1 16 64 for each C: 5 windows (seeds 1..5), every chunk proved and verified (one process
                 each, sequential, taskset -c 0-5 is applied by the caller via fp-heavy.sh), then the
                 chain verifier. Writes runs/honest-C<C>.jsonl and runs/chain-C<C>.json.
  hostile 1 16 64 boundary-targeted attacks on seed 1 (runs/hostile-C<C>.jsonl).
Raw lines go to experiments/20261109-34-qwen-state-commit/runs/. Proof files stay in work/ (not committed).
"""
import hashlib, json, os, pathlib, platform, shutil, statistics, subprocess, sys, time
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(here))
import window as W
runs = root / 'experiments/20261109-34-qwen-state-commit/runs'; runs.mkdir(parents=True, exist_ok=True)
work = here / 'work'; work.mkdir(exist_ok=True)
binary = work / 'chunk.bin'
SEEDS = [1, 2, 3, 4, 5]

def sh(argv, timeout=3600):
    t = time.monotonic(); p = subprocess.run([str(a) for a in argv], cwd=root, capture_output=True, text=True, timeout=timeout)
    return p.returncode, round(time.monotonic() - t, 3), p.stdout, p.stderr[-2000:]

def js(out):
    for l in out.splitlines():
        if l.startswith('{'): return json.loads(l)
    return {}

def verify(fx, hd, pf):
    code, wall, out, err = sh([binary, 'verify', fx, hd, pf]); r = js(out)
    return bool(r.get('accept')), r

def prove(fx, hd, pf):
    code, wall, out, err = sh([binary, 'prove', fx, hd, pf]); r = js(out); r['exit'] = code; r['wall'] = wall
    if code != 0: r['stderr'] = err
    return r

def st(x):
    return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0.0, min=min(x), max=max(x))

def do_build():
    c = sh(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
            'research/operators/qwen_state_commit/chunk.cpp', '-o', binary.relative_to(root)])
    assert c[0] == 0, c[3]
    srcs = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [here / 'chunk.cpp', here / 'window.py', here / 'record.py', root / 'research/operators/qwen_deltanet_lookup/lookup.h',
             root / 'research/operators/qwen_deltanet/product.h', root / 'research/operators/qwen_deltanet/reference.py', root / 'blocks/iop/rng.h']}
    (runs / 'build.json').write_text(json.dumps(dict(compile_seconds=c[1], sources=srcs,
        compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0], platform=platform.platform(),
        python=sys.version.split()[0], numpy=np.__version__), indent=1) + '\n')

def honest(C):
    lines = []; chains = []
    for s in SEEDS:
        d = work / f'w-C{C}-s{s}'; shutil.rmtree(d, ignore_errors=True)
        man = W.build_window(s, C, d)
        for ch in man['chunks']:
            r = prove(d / ch['fixture'], d / ch['header'], d / ch['proof'])
            ok, v = verify(d / ch['fixture'], d / ch['header'], d / ch['proof'])
            row = dict(seed=s, C=C, chunk=ch['c'], accept=ok, prove=r, verify=v)
            lines.append(row); print(json.dumps(dict(seed=s, C=C, chunk=ch['c'], accept=ok, prove_s=r.get('prove_s'), verify_s=v.get('verify_s'))), flush=True)
            (runs / f'honest-C{C}.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in lines))
        t = time.monotonic(); okc, why = W.chain_check(d, man, lambda f, h, p: verify(f, h, p)[0]); cs = round(time.monotonic() - t, 2)
        chains.append(dict(seed=s, C=C, chunks=len(man['chunks']), chain_accept=okc, why=why, chain_check_s=cs))
        print(json.dumps(chains[-1]), flush=True)
        # keep the disk small: drop proofs of finished windows except seed 1 (hostile reuses it)
        if s != 1:
            for p in d.glob('*.proof'): p.unlink()
    summ = summarize(C, lines, chains)
    (runs / f'chain-C{C}.json').write_text(json.dumps(dict(chains=chains, summary=summ), indent=1) + '\n')
    print(json.dumps(summ, indent=1))

def summarize(C, lines, chains):
    P = [l['prove'] for l in lines]; V = [l['verify'] for l in lines]
    per_window = {}
    for l in lines:
        w = per_window.setdefault(l['seed'], dict(prove_s=0.0, verify_s=0.0, proof_bytes=0, core_columns=0, relations=0, columns_used=0, range_cells=0))
        w['prove_s'] += l['prove']['prove_s']; w['verify_s'] += l['verify']['verify_s']; w['proof_bytes'] += l['prove']['proof_bytes']
        w['core_columns'] += l['prove']['core_columns']; w['relations'] += l['prove']['relations']; w['columns_used'] += l['prove']['columns_used']; w['range_cells'] += l['prove']['range_cells']
    pw = list(per_window.values())
    T = W.T; Dn = W.D
    return dict(C=C, T=T, D=Dn, chunk_proofs=len(lines), accepted=sum(l['accept'] for l in lines), chains_accepted=sum(c['chain_accept'] for c in chains), chains=len(chains),
                per_chunk=dict(prove_s=st([p['prove_s'] for p in P]), verify_s=st([v['verify_s'] for v in V]), proof_bytes=st([p['proof_bytes'] for p in P]),
                               peak_rss_kb_prove=st([p['peak_rss_kb'] for p in P]), log_length=st([p['log_length'] for p in P]),
                               relations=st([p['relations'] for p in P]), core_columns=st([p['core_columns'] for p in P])),
                per_window=dict(prove_s=st([w['prove_s'] for w in pw]), verify_s=st([w['verify_s'] for w in pw]), proof_bytes=st([w['proof_bytes'] for w in pw])),
                per_token=dict(core_columns=pw[0]['core_columns'] / T, laid_columns=pw[0]['columns_used'] / T, relations=pw[0]['relations'] / T,
                               range_cells=pw[0]['range_cells'] / T, core_columns_per_state_cell=pw[0]['core_columns'] / T / (Dn * Dn),
                               carried_handle_values=(Dn * Dn + 9 * Dn) / C))

# ---------------- hostile (boundary-targeted) ----------------
def write_chunk(d, name, S0, toks):
    fx, Sout = W.chunk_fixture(S0, toks); (d / f'{name}.fx').write_bytes(fx); return Sout

def hostile(C):
    out = []; T = W.T if C < 64 else 128  # C = 64 needs two chunks: a 128-token window
    d = work / f'h-C{C}'; shutil.rmtree(d, ignore_errors=True)
    man = W.build_window(1, C, d, T=T)
    n = len(man['chunks']); c = 1 if n > 1 else 0  # the attacked boundary is between chunk c-1 and c
    for ch in man['chunks']:
        r = prove(d / ch['fixture'], d / ch['header'], d / ch['proof']); assert r['exit'] == 0, r
    base_ok, why = W.chain_check(d, man, lambda f, h, p: verify(f, h, p)[0])
    out.append(dict(cls='control', attack='honest chain', chain_accept=base_ok, why=why, rejected=not base_ok, expect_accept=True))
    S_all, toks, xconv = W.gen_window(1, T)
    def rec(cls, what, ok, why, extra=None):
        row = dict(cls=cls, attack=what, chain_accept=ok, why=why, rejected=not ok, **(extra or {})); out.append(row); print(json.dumps(row), flush=True)
        (runs / f'hostile-C{C}.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in out))
    def variant(tag, edit):
        """Copy the honest window into a variant dir, apply edit(dir, manifest) -> manifest, run the chain verifier."""
        v = d.parent / f'{d.name}-{tag}'; shutil.rmtree(v, ignore_errors=True); shutil.copytree(d, v)
        m2 = edit(v, json.loads(json.dumps(man)))
        ok, why = W.chain_check(v, m2, lambda f, h, p: verify(f, h, p)[0]); shutil.rmtree(v, ignore_errors=True); return ok, why
    ch = man['chunks'][c]; prev = man['chunks'][c - 1] if c > 0 else None
    Hin = np.load(d / ch['h_in']); Hout_c = np.load(d / ch['h_out'])
    Tn, Sin, _ = W.read_fixture(d / ch['fixture'])
    ctoks = toks[c * C:(c + 1) * C]
    def reprove_with(v, m2, S0, H0=None, req=1, idx=None, start=None):
        """Honestly re-prove chunk c of variant v from state S0 (and history H0), with a consistent header."""
        idx = c if idx is None else idx; start = c * C if start is None else start
        H0 = Hin if H0 is None else H0
        Sout = write_chunk(v, f'c{c}', S0, ctoks)
        hin = W.handle(req, 0, idx, start, S0, H0); hout = W.handle(req, 0, idx + 1, start + C, Sout, Hout_c)
        (v / f'c{c}.hdr').write_bytes(W.header_bytes(req, 0, idx, start, C, hin, hout)); np.save(v / f'c{c}.hin.npy', H0)
        r = prove(v / f'c{c}.fx', v / f'c{c}.hdr', v / f'c{c}.proof'); assert r['exit'] == 0, r
        m2['chunks'][c]['handle_in'] = hin; m2['chunks'][c]['handle_out'] = hout
        return Sout, hout
    def fix_next(v, m2, hout):
        """Make chunk c+1's words claim the tampered S_out: not possible without re-proving it; leave it (attack on boundary c only)."""
        return m2
    # b1a: wrong carried state, honestly proved from it (chunk c's S_in = honest + 1 at [0,0]); the
    # following chunk is re-proved too when it exists, so only boundary c is inconsistent.
    if c > 0:
        def e(v, m2):
            S0 = Sin.copy(); S0[0, 0] += 1; Sout, hout = reprove_with(v, m2, S0)
            if c + 1 < n:  # chunk c+1 re-proved from the tampered chain so boundary c+1 is consistent
                nxt = man['chunks'][c + 1]; Hn = np.load(v / nxt['h_in']); Hno = np.load(v / nxt['h_out'])
                So = write_chunk(v, f'c{c+1}', Sout, toks[(c + 1) * C:(c + 2) * C])
                (v / f'c{c+1}.hdr').write_bytes(W.header_bytes(1, 0, c + 1, (c + 1) * C, C, W.handle(1, 0, c + 1, (c + 1) * C, Sout, Hn), W.handle(1, 0, c + 2, (c + 2) * C, So, Hno)))
                prove(v / f'c{c+1}.fx', v / f'c{c+1}.hdr', v / f'c{c+1}.proof')
            return m2
        rec('b1-wrong-state', f'S_in(chunk {c})[0,0] += 1, chunk proved honestly from it (and later chunks re-proved)', *variant('b1a', e))
        # b1b: words and header honest, proof made from the tampered state (swapped in)
        def e(v, m2):
            t = v / 'tmp'; t.mkdir()
            S0 = Sin.copy(); S0[0, 0] += 1; write_chunk(t, 'x', S0, ctoks)
            prove(t / 'x.fx', v / f'c{c}.hdr', v / f'c{c}.proof'); shutil.rmtree(t); return m2
        rec('b1-wrong-state', f'chunk {c}: honest words and header, proof made from S_in[0,0] + 1', *variant('b1b', e))
        # b2: state from another chunk (chunk c's S_in := chunk c-1's S_in), honestly proved
        def e(v, m2):
            _, S_prev_in, _ = W.read_fixture(d / prev['fixture']); reprove_with(v, m2, S_prev_in.copy()); return m2
        rec('b2-other-chunk-state', f'S_in(chunk {c}) := S_in(chunk {c-1}), proved honestly', *variant('b2a', e))
        # b2b: whole chunk c-1 (fixture, header, proof, history) replayed in slot c
        def e(v, m2):
            for suf in ('fx', 'hdr', 'proof', 'hin.npy', 'hout.npy'): shutil.copy(d / f'c{c-1}.{suf}', v / f'c{c}.{suf}')
            return m2
        rec('b2-other-chunk-state', f'chunk {c-1} replayed verbatim in slot {c}', *variant('b2b', e))
        # b3: chunk dropped (manifest without chunk c)
        def e(v, m2):
            m2['chunks'] = [x for x in m2['chunks'] if x['c'] != c]; return m2
        rec('b3-skipped-step', f'chunk {c} dropped from the chain', *variant('b3a', e))
        # b4: replayed boundary handle under another chunk index (header rewritten to idx c, proof from slot c-1)
        def e(v, m2):
            shutil.copy(d / f'c{c-1}.proof', v / f'c{c}.proof'); return m2
        rec('b4-replayed-boundary', f'proof of chunk {c-1} presented with chunk {c}\'s words and header', *variant('b4a', e))
    # b3: skipped step inside a chunk (complete hostile proof, true local targets)
    if C >= 2:
        code, wall, o, err = sh([binary, 'hostile-skip', d / ch['fixture'], d / ch['header'], work / 'skip.proof'])
        r = js(o); rec('b3-skipped-step', f'chunk {c}: witness skips token {C // 2} (decay 1, beta 0), complete hostile proof', bool(r.get('accept')), 'chunk verifier', dict(violated_relations=r.get('violated_relations')))
        (work / 'skip.proof').unlink(missing_ok=True)
    # b4: replay under another request id: header req = 2 with recomputed handles, proof from req 1
    def e(v, m2):
        m2['request'] = 2; m2['initial_handle'] = W.handle(2, 0, 0, 0, S_all, xconv[W.WARM - 3:W.WARM])
        for x in m2['chunks']:
            _, S0, So = W.read_fixture(v / x['fixture']); H0 = np.load(v / x['h_in']); Ho = np.load(v / x['h_out'])
            (v / x['header']).write_bytes(W.header_bytes(2, 0, x['c'], x['start'], C, W.handle(2, 0, x['c'], x['start'], S0, H0), W.handle(2, 0, x['c'] + 1, x['start'] + C, So, Ho)))
        return m2
    rec('b4-replayed-boundary', 'every chunk proof of request 1 replayed under request 2 (headers and handles recomputed)', *variant('b4b', e))
    # b5: replaced conv history at boundary c
    if c > 0:
        def e(v, m2):
            H2 = Hin.copy(); H2[0, 0] += 1; np.save(v / f'c{c}.hin.npy', H2); return m2
        rec('b5-conv-history', f'H_in(chunk {c})[0,0] += 1, header and proof unchanged', *variant('b5a', e))
        def e(v, m2):
            H2 = Hin.copy(); H2[0, 0] += 1; reprove_with(v, m2, Sin.copy(), H0=H2); return m2
        rec('b5-conv-history', f'H_in(chunk {c})[0,0] += 1, header recomputed and chunk re-proved honestly', *variant('b5b', e))
    hs = [x for x in out if x['cls'] != 'control']
    summ = dict(C=C, T=T, chunks=n, attacked_boundary=c, control_accept=base_ok, rejected=sum(x['rejected'] for x in hs), total=len(hs))
    (runs / f'hostile-C{C}.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in out) + json.dumps(dict(summary=summ)) + '\n')
    print(json.dumps(summ), flush=True)
    for p in d.parent.glob(f'{d.name}*'): shutil.rmtree(p, ignore_errors=True)

if __name__ == '__main__':
    a = sys.argv[1:]
    if 'build' in a: do_build()
    if 'honest' in a:
        i = a.index('honest') + 1
        while i < len(a) and a[i].isdigit(): honest(int(a[i])); i += 1
    if 'hostile' in a:
        i = a.index('hostile') + 1
        while i < len(a) and a[i].isdigit(): hostile(int(a[i])); i += 1
