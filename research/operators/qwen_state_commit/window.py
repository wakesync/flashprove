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
all as little-endian i64. Chain verifier: every chunk proof verifies under its derived statement
(chunk.bin verify), the handle of chunk c's (S_out, H_out) at boundary c+1 equals the handle of chunk
c+1's (S_in, H_in) at boundary c+1, chunk 0 starts from the registered initial handle, chunk indices
are 0..n-1, token starts are c*C and the lengths sum to T.
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

def chunk_fixture(S0, toks):
    arr = [np.array([len(toks), D, F], dtype=np.int64), S0.reshape(-1)]
    rec = []; S = S0
    for tok in toks:
        M, delta, S, o = R.step(S, tok, F); rec.append((M, delta, S.copy(), o))
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
    for c in range(T // C):
        Sin = S; Hin = Hw(c * C)
        fx, S = chunk_fixture(Sin, toks[c * C:(c + 1) * C])
        Hout = Hw((c + 1) * C)
        hin = handle(req, layer, c, c * C, Sin, Hin); hout = handle(req, layer, c + 1, (c + 1) * C, S, Hout)
        hd = header_bytes(req, layer, c, c * C, C, hin, hout)
        (outdir / f'c{c}.fx').write_bytes(fx); (outdir / f'c{c}.hdr').write_bytes(hd)
        np.save(outdir / f'c{c}.hin.npy', Hin); np.save(outdir / f'c{c}.hout.npy', Hout)
        chunks.append(dict(c=c, start=c * C, len=C, fixture=f'c{c}.fx', header=f'c{c}.hdr', proof=f'c{c}.proof',
                           h_in=f'c{c}.hin.npy', h_out=f'c{c}.hout.npy', handle_in=hin, handle_out=hout))
    man = dict(seed=seed, C=C, T=T, D=D, F=F, request=req, layer=layer, initial_handle=init, chunks=chunks)
    (outdir / 'manifest.json').write_text(json.dumps(man, indent=1) + '\n')
    return man

def read_fixture(path):
    w = np.frombuffer(pathlib.Path(path).read_bytes(), dtype='<i8')
    Tn, Dn, Fn = (int(x) for x in w[:3]); p = 3
    S0 = w[p:p + Dn * Dn].reshape(Dn, Dn); p += Dn * Dn
    p += Tn * (2 + 3 * Dn)
    for _ in range(Tn - 1): p += 3 * Dn + Dn * Dn
    p += 2 * Dn; Sout = w[p:p + Dn * Dn].reshape(Dn, Dn); p += Dn * Dn + Dn
    assert p == len(w)
    return Tn, S0, Sout

def parse_header(b):
    assert b[:len(HDR)] == HDR
    vals = struct.unpack('<6q', b[len(HDR):len(HDR) + 48]); rest = b[len(HDR) + 48:]
    return dict(req=vals[0], layer=vals[1], c=vals[2], start=vals[3], C=vals[4], D=vals[5], hin=rest[:32].hex(), hout=rest[32:64].hex())

def chain_check(outdir, man, verify_chunk):
    """The chain verifier. verify_chunk(fixture_path, header_path, proof_path) -> bool (chunk.bin verify).
    Reads ONLY the public files (fixtures = public words, headers, history words, proofs) and the
    registered initial handle; recomputes every handle from the words."""
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
