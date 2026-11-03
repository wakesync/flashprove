#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed research adapter. Metadata validation is NOT proof verification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = '9e2bdd8ff5bf9c62f18263d7dac189b0400b260c'
DOMAIN = b'flashprove-extension-manifest/v1\0'
OPERATORS = ['embedding', 'integer-matmul', 'isqrt-rmsnorm', 'causal-gqa-softmax-lut',
             'rope-lut', 'silu-lut', 'top1-first-index-router-input-scale',
             'shared-expert', 'residual-add', 'greedy-first-index']
# Reviewed trust anchor, not loaded from a provider's manifest.
CONFIG_HASHES = {'policy.txt': '8d9ae1dda2e503550cafade93c54c1b8ecc8eb4b6dab3b843c72a478bb892d2f', 'KL.bin': 'b8fb55ed7c70c4cdc7bac01e804dd0dc79349022ba7972957c7e50a29dc974a2', 'layout.txt': 'a0cce649d992c6f17d1e27c68ac4b900b828ff6ef0bfe8da7c2491fed9f02225'}


class Unsupported(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def profile():
    return {
        'schema': 'flashprove-extension/v1',
        'adapter': 'stored-maverick-integer-v1',
        'upstream_commit': UPSTREAM,
        'architecture': 'maverick-integer-synthetic-accepted-proof',
        'operators': OPERATORS.copy(),
        'shape': {'T': 64, 'L': 8, 'd': 512, 'H': 4, 'G': 2, 'dh': 128,
                  'f': 1024, 'fe': 512, 'NE': 4, 'V': 512},
        'arithmetic': {'spec': 'docs/model.md@' + UPSTREAM,
                       'sum_product': 'exact-integer-with-upstream-range-checks',
                       'rounding': 'floor((a+2^(k-1))/2^k)',
                       'activation_clamp': [-2047, 2047],
                       'quantization': 'upstream-KL.bin-fixed-power-of-two-scales'},
        'proof_policy': 'upstream-exact-match-v1',
        'protocol': 'upstream-H821-unchanged',
        'manifest_domain': DOMAIN[:-1].decode(),
        'state': 'single-request-no-external-state',
        'model': {'kind': 'upstream-synthetic-fixture',
                  'commitment_id': '79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183'},
        'tokenizer': {'kind': 'token-ids-only', 'commitment': None},
        'config_sha256': CONFIG_HASHES.copy(),
        'tee': 'not-implemented-not-required-for-proof',
    }


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Unsupported('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(path):
    raw = Path(path).read_bytes()
    if len(raw) > 65536:
        raise Unsupported('manifest exceeds 64 KiB')
    return json.loads(raw, object_pairs_hook=no_duplicates,
                      parse_constant=lambda x: (_ for _ in ()).throw(Unsupported(x)))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def validate(manifest):
    # Byte equality of canonical JSON also rejects bool-as-int and float-as-int.
    # No dynamic plugin imports, provider-specified commands or permissive fallback.
    if canonical(manifest) != canonical(profile()):
        raise Unsupported('unsupported manifest: only the pinned synthetic baseline is admitted')
    return sha(DOMAIN + canonical(manifest))


def verify(manifest, config, public_key, response, request, start, end, next_token,
           verifier=None):
    """Inputs are client-owned. Returns raw upstream result; never invents a verdict."""
    validate(manifest)
    if any(type(v) is not int for v in (start, end, next_token)):
        raise Unsupported('coverage and next token must be integers')
    if not 0 <= start < end <= 64 or not 0 <= next_token < 512:
        raise Unsupported('coverage or next token outside baseline bounds')
    # Snapshot precisely the bytes that were hashed. Upstream checker makes its own
    # private snapshots of these plus request/response. Keys remain upstream's duty.
    with tempfile.TemporaryDirectory(prefix='fp-extension-') as tmp:
        snapshot = Path(tmp)
        for name, digest in CONFIG_HASHES.items():
            data = (Path(config) / name).read_bytes()
            if sha(data) != digest:
                raise Unsupported('configuration digest mismatch: ' + name)
            (snapshot / name).write_bytes(data)
        command = [sys.executable, '-I', str(ROOT / 'integrations/check_proof.py'),
                   str(Path(response).resolve()), str(Path(request).resolve()),
                   '--commitment-id', manifest['model']['commitment_id'],
                   '--public-key-dir', str(Path(public_key).resolve()),
                   '--parameter-file', str(snapshot / 'policy.txt'),
                   '--scales-file', str(snapshot / 'KL.bin'),
                   '--layout-file', str(snapshot / 'layout.txt'),
                   '--range', f'{start}:{end}', '--end-token', 'none',
                   '--next-token', str(next_token) if end == 64 else 'none',
                   '--policy', 'exact', '--show-all',
                   '--verifier', str(Path(verifier or ROOT / 'bin/cp_verify').resolve())]
        return subprocess.run(command, capture_output=True, text=True, timeout=120)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--baseline', action='store_true', help='verify bundled synthetic example only')
    args = p.parse_args()
    try:
        m = load(args.manifest)
        digest = validate(m)
        print('manifest-valid (NOT a proof): sha256=' + digest, flush=True)
        if not args.baseline:
            return 0
        fixture = ROOT / 'examples/accepted-proof'
        result = verify(m, fixture / 'config', fixture / 'ivk', fixture / 'example.proof',
                        fixture / 'example.req', 60, 64, 199)
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        # Exit zero alone is insufficient: check the upstream machine outcome too.
        if result.returncode == 0 and not any(
            line.startswith('result: outcome=verified ') for line in result.stdout.splitlines()
        ):
            return 2
        return result.returncode
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('extension rejected: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
