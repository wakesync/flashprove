#!/usr/bin/env python3
"""CPU integer-model scores and separate stored-proof binding controls, NOT fresh proofs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'integrations/vllm/integer_model'))
import numpy as np
import torch
from integer_model import IntegerModel, Parameters, RangeConditionFailed
from integer_model.block_weights import BlockWeights, all_tensors, tensor_shape
from integer_model.weights import WeightsInMemory

SEEDS = [1103, 1104, 1105, 1106, 1107]
DOSES = [0.0] + [s * d for d in [.05, .1, .2, .5, .8, 1.] for s in [-1, 1]]
POLICIES = {'strict': {'C': 256, 'theta': 256, 'cap': 0},
            'lenient': {'C': 9244130, 'theta': 323343, 'cap': 1}}
CONFIG = ROOT / 'examples/accepted-proof/config'
BASE = '29907e5fbe648b9ec246cebf9d757511a751fca2'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stats(values):
    return dict(n=len(values), median=statistics.median(values),
                sd=statistics.stdev(values) if len(values) > 1 else 0,
                min=min(values), max=max(values))


def make_weights(p):
    """Cache decoded integers, exactly the same source as the stored small proof."""
    source = BlockWeights(p, 'cpu', blocks='synthetic')
    matrices = {}
    for name, layer in all_tensors(p):
        if name == 'Emb':
            continue
        experts = range(p.NE) if name in ('Wgr', 'Wur', 'Wdr') else [None]
        for expert in experts:
            matrices[name, layer, expert] = source.matrix(name, layer, expert).clone()
    embedding = source.embedding_rows(torch.arange(p.V))
    stock = WeightsInMemory(matrices, embedding)
    ablated = {}
    for key, matrix in matrices.items():
        if key[0] in ('Wo', 'Wd', 'Wdr'):
            matrix = matrix.clone()
            matrix[0, :] = 0  # (I - e_0 e_0^T) W, exact integer arithmetic.
        ablated[key] = matrix
    ablated_embedding = embedding.clone()
    ablated_embedding[:, 0] = 0
    column = dict(matrices)
    key = ('Wd', 0, None)
    column[key] = column[key].clone()
    doubled = 2 * column[key][:, 0].to(torch.int32)
    clipped = int(((doubled < -4096) | (doubled > 4095)).sum())
    column[key][:, 0] = doubled.clamp(-4096, 4095).to(torch.int16)
    return {'stock': stock, 'direction_projected': WeightsInMemory(ablated, ablated_embedding),
            'column_doubled_surrogate': WeightsInMemory(column, embedding)}, clipped


def fingerprint(weights):
    """Canonical artifact hash, explicitly NOT the FlashProve commitment algorithm."""
    h = hashlib.sha256(b'flashprove-cpu-artifact-v1\0')
    for file in ('policy.txt', 'KL.bin', 'layout.txt'):
        data = (CONFIG / file).read_bytes()
        h.update(file.encode() + b'\0' + len(data).to_bytes(8, 'little') + data)
    tensors = [('Emb', weights._embedding)]
    tensors += [(json.dumps(key, separators=(',', ':')), value)
                for key, value in sorted(weights._matrices.items(), key=lambda kv: str(kv[0]))]
    manifest = []
    for name, tensor in tensors:
        data = tensor.numpy().astype('<i8').tobytes(order='C')
        header = json.dumps([name, list(tensor.shape)], separators=(',', ':')).encode()
        h.update(len(header).to_bytes(8, 'little') + header)
        h.update(len(data).to_bytes(8, 'little') + data)
        manifest.append({'name': name, 'shape': list(tensor.shape), 'sha256_i64le': digest(data)})
    return {'artifact_sha256': h.hexdigest(), 'commitment_id': None, 'tensors': manifest}


class RuntimeSteered(IntegerModel):
    """Subclass only the inference experiment. Neither verifier nor proof source is patched."""
    vector = None
    capture = False
    residuals = None

    def _feed_forward(self, layer, x, checks, note):
        result = super()._feed_forward(layer, x, checks, note)
        if layer == 0:
            if self.capture:
                self.residuals = result.clone()
            if self.vector is not None:
                result = result + self.vector
        return result


def generate(model, prompt):
    seq = model.new_sequence()
    try:
        reply = [int(model.extend(seq, prompt)[-1])]
        for _ in range(3):
            reply.append(int(model.extend(seq, [reply[-1]])[-1]))
        return reply
    finally:
        model.free(seq)


def score(model, prompt, reply):
    """Pad/check the whole window, score just covered reply tokens, as try_limits.py does."""
    window = prompt + reply + [0] * (model.parameters.T - len(prompt) - len(reply))
    seq = model.new_sequence()
    try:
        choices, gaps = model.extend(seq, window, gap_for=window[1:] + [0])
    finally:
        model.free(seq)
    first = len(prompt) - 1
    gaps = gaps[first:first + len(reply)].tolist()
    costs = [int(g) + 256 for g in gaps]
    result = {'gaps': gaps, 'costs': costs,
              'stock_choices_on_reply_prefix': choices[first:first + len(reply)].tolist()}
    for name, policy in POLICIES.items():
        total = sum(min(c, policy['C']) for c in costs)
        above = sum(c > policy['C'] for c in costs)
        result[name] = {'accept': total <= policy['theta'] * len(costs) and above <= policy['cap'],
                        'mean_clipped_cost': total / len(costs), 'above_clip': above}
    assert result['strict']['accept'] == all(g == 0 for g in gaps)
    return result


def verifier_controls():
    """Actual cp_verify calls; never labeled as fresh steered-reply proof verdicts."""
    rows = []
    logs = HERE / 'verifier-logs'
    logs.mkdir(exist_ok=True)
    for kind, folder, policy in [
        ('strict', 'accepted-proof', 'exact-match,256,256,0,16,8'),
        ('lenient', 'accepted-proof-clipped-gap', 'clipped-gap,9244130,323343,1,16,8')]:
        source = Path('examples') / folder
        cid = (ROOT / source / 'ID.txt').read_text().strip()
        req = (ROOT / source / 'example.req').read_bytes()
        words = list(struct.unpack('<' + 'I' * (len(req) // 4), req))
        cases = [('unaltered', None, cid, req)]
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            # ID changes are intentionally arbitrary, not IDs of other weight variants.
            wrong_id = digest(f'wrong-id-control:{seed}'.encode())
            cases.append(('wrong_id', seed, wrong_id, req))
            changed = words.copy()
            pos = words[-2] + 1
            changed[pos] = (changed[pos] + int(rng.integers(1, 512))) % 512
            cases.append(('covered_token_changed_reused_proof', seed, cid,
                          struct.pack('<' + 'I' * len(changed), *changed)))
        with tempfile.TemporaryDirectory(prefix='flashprove-binding-') as temp:
            for case, seed, used_id, request in cases:
                request_file = Path(temp) / 'control.req'
                request_file.write_bytes(request)
                cmd = [str(ROOT / 'bin/cp_verify'), str(source / 'config'), str(source / 'ivk'),
                       str(request_file), str(source / 'example.y'), str(source / 'example.proof'),
                       '-id', used_id, '-policy', policy, '-q']
                done = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=120)
                output = (done.stdout + done.stderr).replace(str(ROOT), '<REPO>').replace(temp, '<TMP>')
                log_name = f'{kind}-{case}-{seed}.log'
                (logs / log_name).write_text(output)
                lines = output.strip().splitlines()
                rows.append({'policy': kind, 'case': case, 'seed': seed, 'id_passed': used_id,
                             'exit_code': done.returncode, 'last_line': lines[-1] if lines else '',
                             'log': 'verifier-logs/' + log_name,
                             'receipt': [line for line in lines if line.startswith(
                                 ('covered:', 'commitment:', 'proof of work:', 'result-v1'))]})
                expected = 0 if case == 'unaltered' else 1
                # Fail loudly on unexpected acceptance, retain complete receipts.
                assert (done.returncode == 0) == (expected == 0), rows[-1]
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fingerprints-only', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    p = Parameters.read(CONFIG / 'policy.txt')
    weights, saturated = make_weights(p)
    fingerprints = {name: fingerprint(value) for name, value in weights.items()}
    assert len({f['artifact_sha256'] for f in fingerprints.values()}) == 3
    if args.fingerprints_only:
        print(json.dumps(fingerprints, sort_keys=True))
        return
    (HERE / 'artifact-fingerprints.json').write_text(json.dumps(fingerprints, indent=2) + '\n')
    # Reconstruction in a separate process, not independent-author replication.
    repeat = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--fingerprints-only'],
                            capture_output=True, text=True, check=True)
    assert json.loads(repeat.stdout) == fingerprints
    models = {name: IntegerModel(p, w, 'cpu') for name, w in weights.items()}
    stock = models['stock']
    steering = RuntimeSteered(p, weights['stock'], 'cpu')
    direction = weights['stock'].matrix('Wd', 0)[:, 0].to(torch.float64)
    direction = direction / torch.linalg.vector_norm(direction)
    rows, variants = [], []
    for seed in SEEDS:
        prompt = np.random.default_rng(seed).integers(0, p.V, 8).tolist()
        stock_reply = generate(stock, prompt)
        for name, model in models.items():
            try:
                reply = generate(model, prompt)
                variants.append({'seed': seed, 'variant': name, 'prompt': prompt, 'reply': reply,
                                 'changed_tokens': sum(a != b for a, b in zip(stock_reply, reply)),
                                 'own_model_score': score(model, prompt, reply),
                                 'stock_model_score': score(stock, prompt, reply)})
            except RangeConditionFailed as error:
                variants.append({'seed': seed, 'variant': name, 'error': str(error)})
        steering.vector = None
        steering.capture = True
        seq = steering.new_sequence()
        steering.extend(seq, prompt)
        steering.free(seq)
        steering.capture = False
        norms = torch.linalg.vector_norm(steering.residuals.to(torch.float64), dim=1).numpy()
        norm = float(np.median(norms))
        for dose in DOSES:
            vector = torch.round(direction * dose * norm).to(torch.int64)
            steering.vector = vector
            row = dict(seed=seed, dose=dose, prompt=prompt, stock_reply=stock_reply,
                       residual_norm_median=norm,
                       realized_dose=float(torch.linalg.vector_norm(vector.to(torch.float64))) / norm,
                       intervention_sha256=digest(vector.numpy().astype('<i8').tobytes()))
            try:
                reply = generate(steering, prompt)
                row.update(reply=reply, changed_tokens=sum(a != b for a, b in zip(stock_reply, reply)),
                           score=score(stock, prompt, reply))
                if dose == 0:
                    assert reply == stock_reply
                    assert row['score']['strict']['accept'] and row['score']['lenient']['accept']
            except RangeConditionFailed as error:
                row['error'] = str(error)
            rows.append(row)
        print(f'prompt seed {seed} completed', flush=True)
    assert fingerprint(weights['stock']) == fingerprints['stock'], 'Runtime steering changed weights'
    (HERE / 'raw-scores.json').write_text(json.dumps({'dose_rows': rows, 'variant_rows': variants}, indent=2) + '\n')
    controls = verifier_controls()
    summaries = []
    for dose in DOSES:
        group = [r for r in rows if r['dose'] == dose]
        scored = [r for r in group if 'score' in r]
        item = {'dose': dose, 'n_attempted': len(group), 'n_scored': len(scored),
                'errors': len(group) - len(scored)}
        if scored:
            item['changed_tokens'] = stats([r['changed_tokens'] for r in scored])
            for policy in POLICIES:
                item[policy + '_rejection'] = stats([int(not r['score'][policy]['accept']) for r in scored])
                item[policy + '_accepted_changed_replies'] = sum(
                    r['changed_tokens'] > 0 and r['score'][policy]['accept'] for r in scored)
        summaries.append(item)
    smallest = []
    for seed in SEEDS:
        for sign in [-1, 1]:
            item = {'seed': seed, 'sign': sign}
            for policy in POLICIES:
                rejected = [abs(r['dose']) for r in rows if r['seed'] == seed and r['dose'] * sign > 0
                            and 'score' in r and not r['score'][policy]['accept']]
                item[policy] = min(rejected) if rejected else None
            smallest.append(item)
    numbers = {'verdict': 'KILLED', 'reason': 'Fresh commitments and proofs require CUDA/H100; CPU-only authority.',
               'fresh_commitments': 0, 'fresh_proofs': 0, 'fresh_steering_cp_verify_calls': 0,
               'artifact_recompute_equal': True, 'weight_seed': 31, 'prompt_seeds': SEEDS,
               'saturated_weight_column_entries': saturated, 'policies': POLICIES,
               'dose_rows': rows, 'variant_rows': variants, 'dose_summary': summaries,
               'smallest_score_rejected_dose': smallest, 'stored_proof_controls': controls}
    (HERE / 'numbers.json').write_text(json.dumps(numbers, indent=2) + '\n')
    cpu = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                if line.startswith('model name')), 'unknown')
    env = {'commits': {'base': BASE, 'prereg': subprocess.check_output(
        ['git', 'log', '--format=%H', '--reverse', BASE + '..HEAD'], cwd=ROOT, text=True).splitlines()[0]},
        'toolchain': {'python': platform.python_version(), 'torch': torch.__version__, 'numpy': np.__version__,
                      'compiler': subprocess.check_output(['g++-13', '--version'], text=True).splitlines()[0]},
        'hardware': {'cpu': cpu, 'logical_cpus': os.cpu_count(), 'device': 'cpu', 'torch_threads': 2,
                     'gpu_used': False}, 'seeds': {'weights': 31, 'prompts': SEEDS, 'commitment_seed': None},
        'hashes': {'cp_verify': digest((ROOT / 'bin/cp_verify').read_bytes()),
                   'run_py': digest(Path(__file__).read_bytes())},
        'fixture_hashes': {folder: {str(file.relative_to(ROOT / 'examples' / folder)): digest(file.read_bytes())
                                   for file in sorted((ROOT / 'examples' / folder).rglob('*')) if file.is_file()}
                          for folder in ['accepted-proof', 'accepted-proof-clipped-gap']}}
    (HERE / 'ENV.json').write_text(json.dumps(env, indent=2) + '\n')
    print('Completed CPU scores and stored-proof controls. Fresh-proof study KILLED.', flush=True)


if __name__ == '__main__':
    main()
