#!/usr/bin/env python3
"""Receipt for experiment 20261109-34-qwen-state-commit, strategy SA (CPU only).

Usage: record.py [build] [honest C...] [hostile C...]
  build          compile chunk.bin
  honest 1 16 64 for each C: 5 windows (seeds 1..5), every chunk proved and verified (one process
                 each, sequential), then the chain verifier with the statement pinned.
  hostile 1 16 64 boundary-targeted attacks on seed 1: the registered classes b1..b5, the cases the two
                 reviews of PR #71 constructed (n1..n9), and the cases the harness cannot reject (open).

Run files. The registered runs (runs/honest-C*.jsonl, chain-C*.json, hostile-C*.jsonl, build.json) were
written by this script at commit d39f598, with the unpinned chain check, and are never rewritten. This
version writes every file with the suffix in SUFFIX (-r2): runs/build-r2.json, honest-C<C>-r2.jsonl,
chain-C<C>-r2.json, hostile-C<C>-r2.jsonl. Proof files stay in work/ (not committed).

The statement descriptor (window.statement) is computed here from the registered constants (seed, C, T,
request, layer). It is never read from a window or variant directory, which is what a prover controls.
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
SUFFIX = '-r2'

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
            [here / 'chunk.cpp', here / 'window.py', here / 'record.py', here / 'sb_ref.py', here / 'sb_summary.py',
             here / 'count.py', root / 'research/operators/qwen_deltanet_lookup/lookup.h',
             root / 'research/operators/qwen_deltanet/product.h', root / 'research/operators/qwen_deltanet/reference.py', root / 'blocks/iop/rng.h']}
    (runs / f'build{SUFFIX}.json').write_text(json.dumps(dict(compile_seconds=c[1], sources=srcs,
        chunk_bin_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0], platform=platform.platform(),
        python=sys.version.split()[0], numpy=np.__version__), indent=1) + '\n')

V = lambda f, h, p: verify(f, h, p)[0]

def honest(C):
    lines = []; chains = []
    for s in SEEDS:
        d = work / f'w-C{C}-s{s}'; shutil.rmtree(d, ignore_errors=True)
        man = W.build_window(s, C, d)
        stmt = W.statement(s, C)   # held by the verifier: not read from d
        for ch in man['chunks']:
            r = prove(d / ch['fixture'], d / ch['header'], d / ch['proof'])
            ok, v = verify(d / ch['fixture'], d / ch['header'], d / ch['proof'])
            row = dict(seed=s, C=C, chunk=ch['c'], accept=ok, prove=r, verify=v)
            lines.append(row); print(json.dumps(dict(seed=s, C=C, chunk=ch['c'], accept=ok, prove_s=r.get('prove_s'), verify_s=v.get('verify_s'))), flush=True)
            (runs / f'honest-C{C}{SUFFIX}.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in lines))
        t = time.monotonic(); okc, why, chk = W.chain_check(d, stmt, W.names_of(man), V); cs = round(time.monotonic() - t, 2)
        chains.append(dict(seed=s, C=C, chunks=len(man['chunks']), chain_accept=okc, why=why, check=chk, chain_check_s=cs,
                           statement_id=W.statement_id(stmt), statement=stmt))
        print(json.dumps({k: v for k, v in chains[-1].items() if k != 'statement'}), flush=True)
        shutil.rmtree(d, ignore_errors=True)   # keep the disk small
    summ = summarize(C, lines, chains)
    (runs / f'chain-C{C}{SUFFIX}.json').write_text(json.dumps(dict(
        note='r2: chain verifier with the statement pinned (window.chain_check). Every chunk proof was made again. Four '
             'single-threaded workers ran at the same time, one core each, on a shared loaded host, so the times in this file '
             'are not comparable to the registered run and are not reported as results.',
        chains=chains, summary=summ), indent=1) + '\n')
    print(json.dumps(summ, indent=1))

def summarize(C, lines, chains):
    P = [l['prove'] for l in lines]; Vv = [l['verify'] for l in lines]
    per_window = {}
    for l in lines:
        w = per_window.setdefault(l['seed'], dict(prove_s=0.0, verify_s=0.0, proof_bytes=0, core_columns=0, relations=0, columns_used=0, range_cells=0))
        w['prove_s'] += l['prove']['prove_s']; w['verify_s'] += l['verify']['verify_s']; w['proof_bytes'] += l['prove']['proof_bytes']
        w['core_columns'] += l['prove']['core_columns']; w['relations'] += l['prove']['relations']; w['columns_used'] += l['prove']['columns_used']; w['range_cells'] += l['prove']['range_cells']
    pw = list(per_window.values())
    T = W.T; Dn = W.D
    return dict(C=C, T=T, D=Dn, chunk_proofs=len(lines), accepted=sum(l['accept'] for l in lines), chains_accepted=sum(c['chain_accept'] for c in chains), chains=len(chains),
                per_chunk=dict(prove_s=st([p['prove_s'] for p in P]), verify_s=st([v['verify_s'] for v in Vv]), proof_bytes=st([p['proof_bytes'] for p in P]),
                               peak_rss_kb_prove=st([p['peak_rss_kb'] for p in P]), log_length=st([p['log_length'] for p in P]),
                               relations=st([p['relations'] for p in P]), core_columns=st([p['core_columns'] for p in P])),
                per_window=dict(prove_s=st([w['prove_s'] for w in pw]), verify_s=st([w['verify_s'] for w in pw]), proof_bytes=st([w['proof_bytes'] for w in pw])),
                per_token=dict(core_columns=pw[0]['core_columns'] / T, laid_columns=pw[0]['columns_used'] / T, relations=pw[0]['relations'] / T,
                               range_cells=pw[0]['range_cells'] / T, core_columns_per_state_cell=pw[0]['core_columns'] / T / (Dn * Dn),
                               carried_handle_values=(Dn * Dn + 9 * Dn) / C))

# ---------------- hostile (boundary-targeted) ----------------
def write_chunk(d, name, S0, toks):
    fx, Sout = W.chunk_fixture(S0, toks); (d / f'{name}.fx').write_bytes(fx); return Sout

def put(v, name, idx, start, S0, tk, Hin, Hout, req=1, layer=0, Fx=None):
    """Write one chunk (public words, header, history words) with consistent handles and prove it honestly.
    Returns (S_out, manifest row)."""
    fx, Sout = W.chunk_fixture(S0, tk, Fx); (v / f'{name}.fx').write_bytes(fx)
    hin = W.handle(req, layer, idx, start, S0, Hin); hout = W.handle(req, layer, idx + 1, start + len(tk), Sout, Hout)
    (v / f'{name}.hdr').write_bytes(W.header_bytes(req, layer, idx, start, len(tk), hin, hout))
    np.save(v / f'{name}.hin.npy', Hin); np.save(v / f'{name}.hout.npy', Hout)
    r = prove(v / f'{name}.fx', v / f'{name}.hdr', v / f'{name}.proof'); assert r['exit'] == 0, r
    return Sout, W.entry(name, idx, start, len(tk), hin, hout)

def hostile(C):
    out = []; T = W.T if C < 64 else 128  # C = 64 needs two chunks: a 128-token window
    d = work / f'h-C{C}'; shutil.rmtree(d, ignore_errors=True)
    man = W.build_window(1, C, d, T=T)
    stmt0 = W.statement(1, C, T)          # held by the verifier
    n = len(man['chunks']); c = 1 if n > 1 else 0  # the attacked boundary is between chunk c-1 and c
    for ch in man['chunks']:
        r = prove(d / ch['fixture'], d / ch['header'], d / ch['proof']); assert r['exit'] == 0, r
    path = runs / f'hostile-C{C}{SUFFIX}.jsonl'
    def flush(extra=None):
        path.write_text(''.join(json.dumps(x) + '\n' for x in out) + (json.dumps(extra) + '\n' if extra else ''))
    def rec(cls, what, res, expect='reject', origin=None, extra=None):
        row = dict(cls=cls, attack=what, chain_accept=res['accept'], why=res['why'], check=res['check'], rejected=res['accept'] is False, expect=expect)
        if 'legacy_accept' in res: row.update(legacy_accept=res['legacy_accept'], legacy_why=res['legacy_why'])
        if origin: row['origin'] = origin
        row.update(extra or {}); out.append(row); print(json.dumps(row), flush=True); flush()
    def variant(tag, edit, stmt=None, legacy=False):
        """Copy the honest window into a variant dir, apply edit(dir, manifest) -> manifest, run the pinned
        chain verifier against the statement the verifier holds (and, for the reviewers' cases, the legacy
        check against the prover's manifest)."""
        v = d.parent / f'{d.name}-{tag}'; shutil.rmtree(v, ignore_errors=True); shutil.copytree(d, v)
        try:
            m2 = edit(v, json.loads(json.dumps(man)))
            ok, why, chk = W.chain_check(v, stmt or stmt0, W.names_of(m2), V)
            res = dict(accept=ok, why=why, check=chk)
            if legacy:
                lo, lw = W.chain_check_unpinned(v, m2, V); res.update(legacy_accept=lo, legacy_why=lw)
        except (AssertionError, OverflowError) as ex:   # the construction itself could not be built honestly
            res = dict(accept=None, why='NOT RUN: ' + repr(ex)[:300], check='not-run')
        finally:
            shutil.rmtree(v, ignore_errors=True)
        return res
    okb, whyb, chkb = W.chain_check(d, stmt0, W.names_of(man), V); lo, lw = W.chain_check_unpinned(d, man, V)
    rec('control', 'honest chain', dict(accept=okb, why=whyb, check=chkb, legacy_accept=lo, legacy_why=lw), expect='accept',
        extra=dict(statement_id=W.statement_id(stmt0), statement=stmt0))
    base_ok = okb
    S_all, toks, xconv = W.gen_window(1, T)
    Hw = lambda end: xconv[W.WARM + end - 3:W.WARM + end]
    Sb = [S_all] + [W.read_fixture(d / x['fixture'])[2] for x in man['chunks']]   # honest boundary states
    tk = lambda j: toks[j * C:(j + 1) * C]
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

    # ---- registered classes b1..b5 (PREREG H2), unchanged constructions, now against the pinned verifier ----
    if c > 0:
        # b1a: wrong carried state, honestly proved from it; the following chunk is re-proved too when it exists
        def e(v, m2):
            S0 = Sin.copy(); S0[0, 0] += 1; Sout, hout = reprove_with(v, m2, S0)
            if c + 1 < n:
                nxt = man['chunks'][c + 1]; Hn = np.load(v / nxt['h_in']); Hno = np.load(v / nxt['h_out'])
                So = write_chunk(v, f'c{c+1}', Sout, toks[(c + 1) * C:(c + 2) * C])
                (v / f'c{c+1}.hdr').write_bytes(W.header_bytes(1, 0, c + 1, (c + 1) * C, C, W.handle(1, 0, c + 1, (c + 1) * C, Sout, Hn), W.handle(1, 0, c + 2, (c + 2) * C, So, Hno)))
                prove(v / f'c{c+1}.fx', v / f'c{c+1}.hdr', v / f'c{c+1}.proof')
            return m2
        rec('b1-wrong-state', f'S_in(chunk {c})[0,0] += 1, chunk proved honestly from it (and later chunks re-proved)', variant('b1a', e))
        # b1b: words and header honest, proof made from the tampered state (swapped in)
        def e(v, m2):
            t = v / 'tmp'; t.mkdir()
            S0 = Sin.copy(); S0[0, 0] += 1; write_chunk(t, 'x', S0, ctoks)
            prove(t / 'x.fx', v / f'c{c}.hdr', v / f'c{c}.proof'); shutil.rmtree(t); return m2
        rec('b1-wrong-state', f'chunk {c}: honest words and header, proof made from S_in[0,0] + 1', variant('b1b', e))
        # b2: state from another chunk (chunk c's S_in := chunk c-1's S_in), honestly proved
        def e(v, m2):
            _, S_prev_in, _ = W.read_fixture(d / prev['fixture']); reprove_with(v, m2, S_prev_in.copy()); return m2
        rec('b2-other-chunk-state', f'S_in(chunk {c}) := S_in(chunk {c-1}), proved honestly', variant('b2a', e))
        # b2b: whole chunk c-1 (fixture, header, proof, history) replayed in slot c
        def e(v, m2):
            for suf in ('fx', 'hdr', 'proof', 'hin.npy', 'hout.npy'): shutil.copy(d / f'c{c-1}.{suf}', v / f'c{c}.{suf}')
            return m2
        rec('b2-other-chunk-state', f'chunk {c-1} replayed verbatim in slot {c}', variant('b2b', e))
        # b3: chunk dropped (chain presented without chunk c)
        def e(v, m2):
            m2['chunks'] = [x for x in m2['chunks'] if x['c'] != c]; return m2
        rec('b3-skipped-step', f'chunk {c} dropped from the chain', variant('b3a', e))
        # b4: proof of chunk c-1 presented with chunk c's words and header
        def e(v, m2):
            shutil.copy(d / f'c{c-1}.proof', v / f'c{c}.proof'); return m2
        rec('b4-replayed-boundary', f'proof of chunk {c-1} presented with chunk {c}\'s words and header', variant('b4a', e))
    # b3: skipped step inside a chunk (complete hostile proof, true local targets); chunk verifier alone
    if C >= 2:
        sp = work / f'skip-C{C}.proof'
        code, wall, o, err = sh([binary, 'hostile-skip', d / ch['fixture'], d / ch['header'], sp])
        r = js(o); rec('b3-skipped-step', f'chunk {c}: witness skips token {C // 2} (decay 1, beta 0), complete hostile proof',
                       dict(accept=bool(r.get('accept')), why='chunk verifier', check='chunk-proof'), extra=dict(violated_relations=r.get('violated_relations')))
        sp.unlink(missing_ok=True)
    # b4b: every chunk proof of request 1 replayed for request 2. The verifier's statement is for request 2
    # (same registered state and inputs); headers and handles are recomputed for request 2, proofs are request 1's.
    def e(v, m2):
        m2['request'] = 2; m2['initial_handle'] = W.handle(2, 0, 0, 0, S_all, xconv[W.WARM - 3:W.WARM])
        for x in m2['chunks']:
            _, S0, So = W.read_fixture(v / x['fixture']); H0 = np.load(v / x['h_in']); Ho = np.load(v / x['h_out'])
            (v / x['header']).write_bytes(W.header_bytes(2, 0, x['c'], x['start'], C, W.handle(2, 0, x['c'], x['start'], S0, H0), W.handle(2, 0, x['c'] + 1, x['start'] + C, So, Ho)))
        return m2
    rec('b4-replayed-boundary', 'every chunk proof of request 1 replayed under request 2 (headers and handles recomputed)', variant('b4b', e, stmt=W.statement(1, C, T, req=2)))
    # b5: replaced conv history at boundary c
    if c > 0:
        def e(v, m2):
            H2 = Hin.copy(); H2[0, 0] += 1; np.save(v / f'c{c}.hin.npy', H2); return m2
        rec('b5-conv-history', f'H_in(chunk {c})[0,0] += 1, header and proof unchanged', variant('b5a', e))
        def e(v, m2):
            H2 = Hin.copy(); H2[0, 0] += 1; reprove_with(v, m2, Sin.copy(), H0=H2); return m2
        rec('b5-conv-history', f'H_in(chunk {c})[0,0] += 1, header recomputed and chunk re-proved honestly', variant('b5b', e))

    # ---- cases constructed by the reviews of PR #71 (n1..n9). Every chunk proof in them is an honest,
    # complete proof of the chunk it is presented with; the legacy check accepts them (legacy_accept). ----
    A = 'astra review, PR #71 comment 6758363867'; O = 'opus review, PR #71 comment 6758460446'
    if c > 0:
        # n1 mixed F: chunk c proved in the same relation at F = 13, the suffix re-proved at F = 12 from its output
        def e(v, m2):
            S, m2['chunks'][c] = put(v, f'c{c}', c, c * C, Sb[c], tk(c), Hw(c * C), Hw((c + 1) * C), Fx=13)
            for j in range(c + 1, n): S, m2['chunks'][j] = put(v, f'c{j}', j, j * C, S, tk(j), Hw(j * C), Hw((j + 1) * C))
            m2['final_state_max_abs_diff_vs_honest'] = int(np.abs(S - Sb[n]).max()); e.diff = m2['final_state_max_abs_diff_vs_honest']
            return m2
        r = variant('n1', e, legacy=True)
        rec('n1-mixed-F', f'chunk {c} proved at F = 13, later chunks re-proved at F = 12 from its output; the manifest still says F = 12', r, origin=A + ' (item 1, probe 20)',
            extra=dict(final_state_max_abs_diff_vs_honest=getattr(e, 'diff', None)))
        # n1b: the F = 13 chunk relabelled as F = 12 in its fixture (proof and words unchanged)
        def e(v, m2):
            put(v, f'c{c}', c, c * C, Sb[c], tk(c), Hw(c * C), Hw((c + 1) * C), Fx=13)
            w = np.frombuffer((v / f'c{c}.fx').read_bytes(), dtype='<i8').copy(); w[2] = 12; (v / f'c{c}.fx').write_bytes(w.tobytes()); return m2
        rec('n1-mixed-F', f'chunk {c} proved at F = 13, its fixture then relabelled F = 12 (words and proof unchanged)', variant('n1b', e, legacy=True), origin='this lane')
    if c > 0 and C >= 2:
        # n2 split: chunk c presented as two honest chunks of C/2, later chunks renumbered and re-proved
        def e(v, m2):
            h = C // 2
            S, e1 = put(v, 's0', c, c * C, Sb[c], tk(c)[:h], Hw(c * C), Hw(c * C + h))
            S, e2 = put(v, 's1', c + 1, c * C + h, S, tk(c)[h:], Hw(c * C + h), Hw((c + 1) * C))
            new = m2['chunks'][:c] + [e1, e2]
            for j in range(c + 1, n):
                S, ent = put(v, f't{j}', j + 1, j * C, S, tk(j), Hw(j * C), Hw((j + 1) * C)); new.append(ent)
            m2['chunks'] = new; return m2
        rec('n2-split-chunk', f'chunk {c} split into two honest chunks of {C // 2} tokens, later chunks renumbered and re-proved', variant('n2', e, legacy=True), origin=O + ' (R10)')
    if c > 0 and 2 <= C < 64:
        # n2b uneven chunks, same chunk count: chunks c-1 and c re-cut as C/2 and 3C/2 tokens
        def e(v, m2):
            h = C // 2; lo = (c - 1) * C
            S, m2['chunks'][c - 1] = put(v, f'c{c-1}', c - 1, lo, Sb[c - 1], toks[lo:lo + h], Hw(lo), Hw(lo + h))
            S, m2['chunks'][c] = put(v, f'c{c}', c, lo + h, S, toks[lo + h:lo + 2 * C], Hw(lo + h), Hw(lo + 2 * C))
            return m2
        rec('n2-split-chunk', f'chunks {c-1} and {c} re-cut as {C // 2} and {3 * C // 2} tokens (same number of chunks, same tokens)', variant('n2b', e, legacy=True), origin='this lane')
    # n3 foreign layer: the whole window honestly proved under layer-1 headers, manifest says layer 1
    def e(v, m2):
        S = Sb[0]
        for j in range(n): S, m2['chunks'][j] = put(v, f'c{j}', j, j * C, S, tk(j), Hw(j * C), Hw((j + 1) * C), layer=1)
        m2['layer'] = 1; m2['initial_handle'] = W.handle(1, 1, 0, 0, Sb[0], Hw(0)); return m2
    rec('n3-foreign-layer', 'every chunk honestly proved under layer-1 headers and handles; the verifier asked for layer 0', variant('n3', e, legacy=True), origin=O + ' (R3c)')
    # n4 foreign first state: chunk 0 starts from another in-range state, whole chain re-proved, manifest handle updated
    def e(v, m2):
        S = Sb[0].copy(); S[3, 4] += 1000 if S[3, 4] < 0 else -1000
        m2['initial_handle'] = W.handle(1, 0, 0, 0, S, Hw(0))
        for j in range(n): S, m2['chunks'][j] = put(v, f'c{j}', j, j * C, S, tk(j), Hw(j * C), Hw((j + 1) * C))
        return m2
    rec('n4-foreign-first-state', 'chunk 0 starts from another in-range state (one cell moved by 1000), chain re-proved, manifest initial handle updated', variant('n4', e, legacy=True), origin=O + ' (R5b); ' + A + ' (probe 7)')
    if 0 < c < n - 1:
        # n5 dropped chunk: chunk c removed, later chunks renumbered, shifted and re-proved; manifest T reduced
        def e(v, m2):
            S = Sb[c]; new = m2['chunks'][:c]
            for j in range(c + 1, n):
                S, ent = put(v, f'd{j}', j - 1, (j - 1) * C, S, tk(j), Hw((j - 1) * C), Hw(j * C)); new.append(ent)
            m2['chunks'] = new; m2['T'] = T - C; return m2
        rec('n5-dropped-chunk', f'chunk {c} removed, later chunks renumbered and re-proved from the state before it, manifest T = {T - C}', variant('n5', e, legacy=True), origin=O + ' (R8b)')
    if C >= 2:
        # n6 truncated last chunk: proved over its first C/2 tokens only, manifest T reduced
        def e(v, m2):
            j = n - 1; h = C // 2
            _, m2['chunks'][j] = put(v, f'c{j}', j, j * C, Sb[j], tk(j)[:h], Hw(j * C), Hw(j * C + h)); m2['T'] = T - (C - h); return m2
        rec('n6-truncated-chunk', f'last chunk proved over its first {C // 2} tokens only, manifest T = {T - (C - C // 2)}', variant('n6', e, legacy=True), origin=O + ' (R9b); ' + A + ' (probe 13)')
    if n > 1:
        # n7 prefix-only window: the first n-1 chunks, untouched, manifest T reduced
        def e(v, m2):
            m2['chunks'] = m2['chunks'][:n - 1]; m2['T'] = (n - 1) * C; return m2
        rec('n7-prefix-only', f'only the first {n - 1} chunk(s) presented, manifest T = {(n - 1) * C}', variant('n7', e, legacy=True), origin=O + ' (R15)')
    # n8 last-chunk history: H_out of the last chunk changed, header recomputed, chunk re-proved
    def e(v, m2):
        j = n - 1; H2 = Hw(T).copy(); H2[0, 0] += 1
        _, m2['chunks'][j] = put(v, f'c{j}', j, j * C, Sb[j], tk(j), Hw(j * C), H2); return m2
    rec('n8-last-chunk-history', 'H_out of the last chunk changed in one word, header recomputed, chunk re-proved honestly', variant('n8', e, legacy=True), origin=O + ' (R18)')
    # n9 empty chain with the manifest retargeted to T = 0
    def e(v, m2):
        m2['chunks'] = []; m2['T'] = 0; return m2
    rec('n9-empty-chain', 'no chunk presented, manifest T = 0', variant('n9', e, legacy=True), origin=A + ' (probe 19)')

    # ---- control for the declared short last chunk: T not a multiple of C, honest ----
    short_ok = None
    if C >= 16:
        Ts = T - C // 2; ds = work / f'h-C{C}-short'; shutil.rmtree(ds, ignore_errors=True)
        ms = W.build_window(1, C, ds, T=Ts)
        for x in ms['chunks']:
            r = prove(ds / x['fixture'], ds / x['header'], ds / x['proof']); assert r['exit'] == 0, r
        ok, why, chk = W.chain_check(ds, W.statement(1, C, Ts), W.names_of(ms), V); short_ok = ok
        rec('control', f'honest window of T = {Ts} tokens: last chunk has {Ts - (len(ms["chunks"]) - 1) * C} tokens, as the statement declares', dict(accept=ok, why=why, check=chk), expect='accept')
        ok, why, chk = W.chain_check(ds, stmt0, W.names_of(ms), V)
        rec('n6-truncated-chunk', f'the honest T = {Ts} window presented for the statement T = {T}', dict(accept=ok, why=why, check=chk), origin='this lane')
        shutil.rmtree(ds, ignore_errors=True)

    # ---- open: accepted by design of this harness (expect accept). Listed, not counted as rejections. ----
    if c > 0:
        # o1 token inputs of chunk c replaced by another request's (seed 2), honestly proved, suffix re-proved
        def e(v, m2):
            other = W.gen_window(2, T)[1]
            S, m2['chunks'][c] = put(v, f'c{c}', c, c * C, Sb[c], other[c * C:(c + 1) * C], Hw(c * C), Hw((c + 1) * C))
            for j in range(c + 1, n): S, m2['chunks'][j] = put(v, f'c{j}', j, j * C, S, tk(j), Hw(j * C), Hw((j + 1) * C))
            return m2
        rec('open-inputs-not-bound', f'token inputs of chunk {c} replaced by another window\'s (seed 2), proved honestly, later chunks re-proved', variant('o1', e), expect='accept', origin=O + ' (R16); ' + A + ' (probe 17)')
        # o2 conv history shifted by one token consistently on both sides of boundary c
        def e(v, m2):
            Hs = np.roll(Hw(c * C), 1, axis=0)
            put(v, f'c{c-1}', c - 1, (c - 1) * C, Sb[c - 1], tk(c - 1), Hw((c - 1) * C), Hs)
            put(v, f'c{c}', c, c * C, Sb[c], tk(c), Hs, Hw((c + 1) * C)); return m2
        rec('open-history-consistent-shift', f'conv history at boundary {c} rotated by one token on both sides, both chunks re-proved', variant('o2', e), expect='accept', origin=O + ' (R7b); ' + A + ' (probe 10)')

    reg = [x for x in out if x['cls'].startswith('b')]; new = [x for x in out if x['cls'].startswith('n')]; opn = [x for x in out if x['cls'].startswith('open')]
    by_check = {}
    for x in reg + new:
        if x['rejected']: by_check[x['check']] = by_check.get(x['check'], 0) + 1
    summ = dict(C=C, T=T, chunks=n, attacked_boundary=c, control_accept=base_ok, short_last_control_accept=short_ok,
                registered=dict(rejected=sum(x['rejected'] for x in reg), total=len(reg)),
                reviewer_cases=dict(rejected=sum(x['rejected'] for x in new), total=len(new),
                                    legacy_accepted=sum(bool(x.get('legacy_accept')) for x in new), legacy_checked=sum('legacy_accept' in x for x in new)),
                open_cases=dict(accepted=sum(bool(x['chain_accept']) for x in opn), total=len(opn)),
                not_run=sum(x['check'] == 'not-run' for x in out),
                rejected_by_check=by_check,
                rejected=sum(x['rejected'] for x in reg + new), total=len(reg + new))
    flush(dict(summary=summ))
    print(json.dumps(summ), flush=True)
    shutil.rmtree(d, ignore_errors=True)
    for p in d.parent.glob(f'{d.name}-*'): shutil.rmtree(p, ignore_errors=True)

if __name__ == '__main__':
    a = sys.argv[1:]
    if 'build' in a: do_build()
    if 'honest' in a:
        i = a.index('honest') + 1
        while i < len(a) and a[i].isdigit(): honest(int(a[i])); i += 1
    if 'hostile' in a:
        i = a.index('hostile') + 1
        while i < len(a) and a[i].isdigit(): hostile(int(a[i])); i += 1
