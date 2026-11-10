#!/usr/bin/env python3
"""Strategy SA windows, chunk headers and the chain verifier (issue #34).

A window is T = 64 tokens of one head at D = 32 (shrunk from 128, PREREG) with the M1 token
generator, split into chunks of C tokens. Each chunk is one M1b-relation statement whose public
words are S_in, the per-token inputs, the outputs and S_out (the fixture format of
research/operators/qwen_deltanet/reference.py), plus a header bound into the chunk's transcript.

Conv history. The head here has no conv (M1b's statement starts after conv), so the carried conv
history is modelled as a public block of 3 taps x 3D channel words (the head's q, k and v channels)
per boundary: H_out of chunk c is the last 3 tokens' pre-conv inputs of chunk c, synthetic integers
from the seed. Only its binding is tested, not the conv relation (that is PR #67's gadget, unreviewed).

Handle (stand-in for an in-proof carried commitment, see README): SHA-256 over
  "fp-qwen-boundary-v1" | request id | layer | boundary index b | token position | D | S words | H words
all as little-endian i64.

Chain verifier (chain_check, since the fix of PR #71's reviews): it takes a STATEMENT DESCRIPTOR that
the verifier holds (statement(): model/arithmetic identifier slot, request, layer, T, C, D, F, the
initial handle and the digest of the conv history at the end of the window) and an ordered list of
chunk names from the prover. Nothing else is read from the prover's directory except the chunk files
themselves. It rejects unless: the number of chunks is ceil(T / C); every fixture says F and D of the
statement; every chunk has exactly C tokens, except the last one, which has T - (n - 1) C; every header
says the statement's request and layer, index c, token start c*C, that length and D; the handles
recomputed from the words equal the header's; chunk c's input handle equals chunk c-1's output handle
(chunk 0: the statement's initial handle); every chunk proof verifies (chunk.bin verify); and the last
chunk's conv history out has the statement's digest.

chain_check_unpinned is the check the registered runs of commit 733bfe5 used. It trusts a manifest
written by the prover and never compares F or the chunk size. It is kept only so that the cases the
reviewers found accepted can be reproduced next to the fixed verifier (record.py hostile).
"""
import hashlib, json, pathlib, struct, sys
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R

D = 32; F = 12; T = 64; WARM = 64
TAG = b'fp-qwen-boundary-v1'
HDR = b'fp-qwen-chunk-header-v1'
HDR_LEN = len(HDR) + 48 + 64
STMT = 'fp-qwen-chain-statement-v1'
# Slot for the model / arithmetic identifier (weights commitment, scales, relation version). A placeholder
# here: there are no weights in this experiment, and the chunk header and handle do not carry it.
MODEL_ID = 'placeholder: synthetic M1 head, no weights, relation of research/operators/qwen_deltanet_lookup'

def le(xs):
    return np.asarray(xs, dtype='<i8').tobytes()

def handle(req, layer, b, pos, S, H):
    h = hashlib.sha256(); h.update(TAG); h.update(le([req, layer, b, pos, D])); h.update(le(np.asarray(S).reshape(-1))); h.update(le(np.asarray(H).reshape(-1)))
    return h.hexdigest()

def gen_window(seed, T=T):
    """Tokens and integer reference at D = 32 (reference.R.D patched), plus synthetic conv inputs."""
    R.D = D
    toks = R.gen_tokens(seed, 'R1', WARM + T, F)
    S = np.zeros((D, D), dtype=np.int64)
    for tok in toks[:WARM]: S = R.step(S, tok, F)[2]
    rng = np.random.default_rng(1000 + seed)
    xconv = rng.integers(-(1 << 14), 1 << 14, size=(WARM + T, 3 * D), dtype=np.int64)  # pre-conv q,k,v channels
    return S, toks[WARM:], xconv

def chunk_fixture(S0, toks, Fx=None):
    """Public words of one chunk. Fx: fixed-point bits of the chunk (default the registered F; another
    value is used only by the mixed-precision negative case of record.py)."""
    Fx = F if Fx is None else Fx
    arr = [np.array([len(toks), D, Fx], dtype=np.int64), S0.reshape(-1)]
    rec = []; S = S0
    for tok in toks:
        M, delta, S, o = R.step(S, tok, Fx); rec.append((M, delta, S.copy(), o))
    for tok in toks: arr += [np.array([tok['a'], tok['beta']], dtype=np.int64), tok['k'], tok['v'], tok['q']]
    for M, delta, Sx, o in rec: arr += [M, delta, Sx.reshape(-1), o]
    return np.concatenate(arr).astype('<i8').tobytes(), S

def header_bytes(req, layer, c, start, C, hin, hout):
    return HDR + le([req, layer, c, start, C, D]) + bytes.fromhex(hin) + bytes.fromhex(hout)

def build_window(seed, C, outdir, req=1, layer=0, T=T):
    """Writes chunk fixtures, headers and a manifest; returns the manifest dict."""
    outdir = pathlib.Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    S, toks, xconv = gen_window(seed, T)
    Hw = lambda end: xconv[WARM + end - 3:WARM + end]  # last 3 pre-conv inputs before token `end`
    chunks = []
    init = handle(req, layer, 0, 0, S, Hw(0))
    for c in range(-(-T // C)):
        lo, hi = c * C, min((c + 1) * C, T)   # the last chunk is short when C does not divide T
        Sin = S; Hin = Hw(lo)
        fx, S = chunk_fixture(Sin, toks[lo:hi])
        Hout = Hw(hi)
        hin = handle(req, layer, c, lo, Sin, Hin); hout = handle(req, layer, c + 1, hi, S, Hout)
        hd = header_bytes(req, layer, c, lo, hi - lo, hin, hout)
        (outdir / f'c{c}.fx').write_bytes(fx); (outdir / f'c{c}.hdr').write_bytes(hd)
        np.save(outdir / f'c{c}.hin.npy', Hin); np.save(outdir / f'c{c}.hout.npy', Hout)
        chunks.append(entry(f'c{c}', c, lo, hi - lo, hin, hout))
    man = dict(seed=seed, C=C, T=T, D=D, F=F, request=req, layer=layer, initial_handle=init, chunks=chunks)
    (outdir / 'manifest.json').write_text(json.dumps(man, indent=1) + '\n')
    return man

def entry(name, c, start, n, hin, hout):
    """One manifest row (prover-side bookkeeping; the pinned chain verifier reads only the chunk name)."""
    return dict(c=c, start=start, len=n, fixture=f'{name}.fx', header=f'{name}.hdr', proof=f'{name}.proof',
                h_in=f'{name}.hin.npy', h_out=f'{name}.hout.npy', handle_in=hin, handle_out=hout)

def names_of(man):
    """The ordered chunk names a prover presents (all the pinned verifier takes from the manifest)."""
    return [ch['fixture'][:-3] for ch in man['chunks']]

def hist_digest(H):
    return hashlib.sha256(le(np.asarray(H).reshape(-1))).hexdigest()

def statement(seed, C, T=T, req=1, layer=0):
    """The statement descriptor THE VERIFIER holds. Computed from the registered constants, the registered
    initial state and the window's conv inputs, never from a prover's output directory.
    - model_id: slot for the model / arithmetic identifier (placeholder here, see MODEL_ID)
    - request, layer, T (window length), C (chunk policy: every chunk has C tokens, the last T - (n-1) C)
    - D, F: head size and fixed-point bits of the relation every chunk must be proved in
    - initial_handle: handle of the first chunk's (S_in, H_in). In this experiment a warmed-up state, not
      zero and not a proved continuation root.
    - final_history_sha256: digest of the last three pre-conv input rows of the window, a stand-in for
      what a commitment to the layer inputs would fix. Interior histories are not in the statement."""
    S, toks, xconv = gen_window(seed, T)
    return dict(version=STMT, model_id=MODEL_ID, request=req, layer=layer, T=T, C=C, D=D, F=F,
                initial_handle=handle(req, layer, 0, 0, S, xconv[WARM - 3:WARM]),
                final_history_sha256=hist_digest(xconv[WARM + T - 3:WARM + T]))

def statement_id(stmt):
    return hashlib.sha256(json.dumps(stmt, sort_keys=True).encode()).hexdigest()

def read_fixture(path):
    w = np.frombuffer(pathlib.Path(path).read_bytes(), dtype='<i8')
    Tn, Dn, Fn = (int(x) for x in w[:3]); p = 3
    S0 = w[p:p + Dn * Dn].reshape(Dn, Dn); p += Dn * Dn
    p += Tn * (2 + 3 * Dn)
    for _ in range(Tn - 1): p += 3 * Dn + Dn * Dn
    p += 2 * Dn; Sout = w[p:p + Dn * Dn].reshape(Dn, Dn); p += Dn * Dn + Dn
    assert p == len(w)
    return Tn, S0, Sout

def read_fixture_words(path):
    """Strict reader: (T, D, F, S_in, S_out) or None when the file is not exactly one chunk fixture."""
    raw = pathlib.Path(path).read_bytes()
    if len(raw) % 8 or len(raw) < 24: return None
    w = np.frombuffer(raw, dtype='<i8')
    Tn, Dn, Fn = (int(x) for x in w[:3])
    if Tn < 1 or Dn < 1 or Tn > (1 << 20) or Dn > (1 << 12): return None
    if len(w) != 3 + Dn * Dn + Tn * (2 + 3 * Dn) + Tn * (3 * Dn + Dn * Dn): return None
    S0 = w[3:3 + Dn * Dn].reshape(Dn, Dn)
    p = len(w) - Dn - Dn * Dn
    return dict(T=Tn, D=Dn, F=Fn, S_in=S0, S_out=w[p:p + Dn * Dn].reshape(Dn, Dn))

def parse_header(b):
    assert b[:len(HDR)] == HDR
    vals = struct.unpack('<6q', b[len(HDR):len(HDR) + 48]); rest = b[len(HDR) + 48:]
    return dict(req=vals[0], layer=vals[1], c=vals[2], start=vals[3], C=vals[4], D=vals[5], hin=rest[:32].hex(), hout=rest[32:64].hex())

def chain_check(outdir, stmt, names, verify_chunk):
    """The chain verifier, statement pinned. stmt: the descriptor the verifier holds (statement()).
    names: the ordered chunk names the prover presents; for each, <name>.fx (public words), .hdr, .proof,
    .hin.npy and .hout.npy are read from outdir. verify_chunk(fixture, header, proof) -> bool is
    chunk.bin verify. Returns (accept, why, check): `check` names the comparison that decided."""
    outdir = pathlib.Path(outdir)
    if stmt.get('version') != STMT or stmt.get('D') != D: return False, 'statement not understood', 'statement'
    req, layer, Tt, C, Fn = stmt['request'], stmt['layer'], stmt['T'], stmt['C'], stmt['F']
    if Tt < 1 or C < 1: return False, 'statement not understood', 'statement'
    n = -(-Tt // C)
    if len(names) != n:
        return False, f'chunk count: {len(names)} presented, the statement (T = {Tt}, C = {C}) needs {n}', 'chunk-count'
    prev = stmt['initial_handle']; pos = 0; Hout = None
    for idx, name in enumerate(names):
        want = min(C, Tt - idx * C)          # C tokens, except the declared last chunk
        raw = (outdir / f'{name}.hdr').read_bytes()
        if len(raw) != HDR_LEN or raw[:len(HDR)] != HDR: return False, f'header length or tag at chunk {idx}', 'header-format'
        hd = parse_header(raw)
        fx = read_fixture_words(outdir / f'{name}.fx')
        if fx is None: return False, f'fixture malformed at chunk {idx}', 'fixture-format'
        if fx['F'] != Fn: return False, f'arithmetic at chunk {idx}: fixture F = {fx["F"]}, statement F = {Fn}', 'fixture-F'
        if fx['D'] != D: return False, f'head size at chunk {idx}: fixture D = {fx["D"]}, statement D = {D}', 'fixture-D'
        if fx['T'] != want: return False, f'chunk length at chunk {idx}: {fx["T"]} tokens, the statement needs {want}', 'chunk-length'
        if hd['req'] != req or hd['layer'] != layer or hd['c'] != idx or hd['start'] != pos or hd['C'] != want or hd['D'] != D:
            return False, f'header fields at chunk {idx}', 'header-fields'
        Hin = np.load(outdir / f'{name}.hin.npy'); Hout = np.load(outdir / f'{name}.hout.npy')
        if Hin.shape != (3, 3 * D) or Hout.shape != (3, 3 * D) or Hin.dtype != np.int64 or Hout.dtype != np.int64:
            return False, f'history words malformed at chunk {idx}', 'history-format'
        hin = handle(req, layer, idx, pos, fx['S_in'], Hin); hout = handle(req, layer, idx + 1, pos + want, fx['S_out'], Hout)
        if hin != hd['hin'] or hout != hd['hout']: return False, f'header handles do not match words at chunk {idx}', 'handle-words'
        if hin != prev: return False, f'boundary {idx}: carried handle mismatch', 'carried-handle'
        if not verify_chunk(outdir / f'{name}.fx', outdir / f'{name}.hdr', outdir / f'{name}.proof'): return False, f'chunk {idx} proof rejected', 'chunk-proof'
        prev = hout; pos += want
    if pos != Tt: return False, 'token ranges do not cover T', 'coverage'
    if hist_digest(Hout) != stmt['final_history_sha256']:
        return False, 'last chunk: conv history out does not match the statement', 'final-history'
    return True, 'ok', 'ok'

def chain_check_unpinned(outdir, man, verify_chunk):
    """LEGACY, do not use as a verifier. The check of the registered runs (commit 733bfe5), body unchanged.
    It reads request, layer, T and the initial handle from the manifest `man`, which the prover writes,
    compares header C with the fixture's own length only, and never looks at the fixture's F. Kept so
    that record.py can show the same hostile chain accepted here and rejected by chain_check."""
    outdir = pathlib.Path(outdir); chunks = man['chunks']; req, layer = man['request'], man['layer']
    prev = man['initial_handle']; pos = 0
    for idx, ch in enumerate(chunks):
        hd = parse_header((outdir / ch['header']).read_bytes())
        Tn, S0, Sout = read_fixture(outdir / ch['fixture'])
        Hin = np.load(outdir / ch['h_in']); Hout = np.load(outdir / ch['h_out'])
        if hd['req'] != req or hd['layer'] != layer or hd['c'] != idx or hd['start'] != pos or hd['C'] != Tn or hd['D'] != D:
            return False, f'header fields at chunk {idx}'
        hin = handle(req, layer, idx, pos, S0, Hin); hout = handle(req, layer, idx + 1, pos + Tn, Sout, Hout)
        if hin != hd['hin'] or hout != hd['hout']: return False, f'header handles do not match words at chunk {idx}'
        if hin != prev: return False, f'boundary {idx}: carried handle mismatch'
        if not verify_chunk(outdir / ch['fixture'], outdir / ch['header'], outdir / ch['proof']): return False, f'chunk {idx} proof rejected'
        prev = hout; pos += Tn
    if pos != man['T']: return False, 'token ranges do not cover T'
    return True, 'ok'
