"""Independent, fail-closed aggregation of committed PR #124 records. Stdlib only.

No producer imports, no model execution, no summary input. See PREREG.md.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

SOURCE = 'experiments/20261111-8-qwen-e2e-agreement'
SOURCE_SHA = '59bff9a4608e0cc720d58d7c30823a8838fa43e4'
COUNTS = {'p01-ordinary-short': 13, 'p07-chat-ordinary': 23,
          'p08-chat-refusal': 39, 'p09-multilingual': 21,
          'p02-ordinary-paragraph': 107, 'p04-repeat-punct': 64,
          'p05-code': 144, 'p03-repeat-word': 512,
          'p06a-digits-256': 256, 'p11-chat-long': 282}
BF = {'p01-ordinary-short', 'p07-chat-ordinary', 'p08-chat-refusal',
      'p09-multilingual', 'p03-repeat-word'}
DET = {'p01-ordinary-short', 'p04-repeat-punct', 'p09-multilingual'}
ARMS = ('XS18', 'XS20')
NEG_TOL = 1e-12

class InvalidEvidence(ValueError):
    """Invalid or incomplete evidence must not produce a PASS receipt."""

def require(ok, message):
    if not ok:
        raise InvalidEvidence(message)

def keys(obj, expected, where):
    require(type(obj) is dict, where + ': expected object')
    require(set(obj) == set(expected), where + ': missing/extra fields or identities')

def no_duplicates(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, 'duplicate JSON key: ' + k)
        result[k] = v
    return result

def constant(s):
    raise InvalidEvidence('nonfinite JSON constant: ' + s)

def finite_tree(x):
    if type(x) is float:
        require(math.isfinite(x), 'nonfinite numeric value')
    elif type(x) is dict:
        for v in x.values():
            finite_tree(v)
    elif type(x) is list:
        for v in x:
            finite_tree(v)

def loads(text):
    x = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=constant)
    finite_tree(x)
    return x

def number(x, where, minimum=None):
    require(type(x) in (int, float), where + ': expected number, not bool')
    require(math.isfinite(x), where + ': nonfinite')
    if minimum is not None:
        require(x >= minimum, where + ': below minimum')

def integer(x, where, low=0, high=None):
    require(type(x) is int and x >= low, where + ': invalid integer')
    if high is not None:
        require(x < high, where + ': integer out of range')

def array(x, n, where, kind='number', minimum=None):
    require(type(x) is list and len(x) == n, where + ': truncated/extra array')
    for v in x:
        if kind == 'token':
            integer(v, where, high=248320)
        elif kind == 'bool':
            require(type(v) is bool, where + ': expected boolean')
        else:
            number(v, where, minimum)

def unique_list(x, expected, where):
    require(type(x) is list and all(type(v) is str for v in x), where + ': expected string list')
    require(len(x) == len(set(x)) and set(x) == set(expected), where + ': wrong/duplicate identities')

def path_ids(pid, bf, det):
    return set(ARMS) | ({'BF16H'} if pid in bf else set()) | ({'REF#2', 'XS18#2'} if pid in det else set())

def path_prompts(counts, bf, det):
    return {'XS18': set(counts), 'XS20': set(counts), 'BF16H': set(bf),
            'REF#2': set(det), 'XS18#2': set(det)}

def prompt_manifest(doc, counts, bf, det):
    keys(doc, ['tokenizer_sha256', 'n_prompts', 'total_tokens', 'bf16h_subset', 'determinism_subset', 'prompts'], 'prompt manifest')
    require(type(doc['tokenizer_sha256']) is str and re.fullmatch('[0-9a-f]{64}', doc['tokenizer_sha256']), 'tokenizer hash')
    integer(doc['n_prompts'], 'n_prompts', 1)
    integer(doc['total_tokens'], 'total_tokens', 1)
    require(doc['n_prompts'] == len(counts) and doc['total_tokens'] == sum(counts.values()), 'manifest denominator')
    unique_list(doc['bf16h_subset'], bf, 'BF16H subset')
    unique_list(doc['determinism_subset'], det, 'determinism subset')
    require(type(doc['prompts']) is list, 'prompts not list')
    seen = set()
    for p in doc['prompts']:
        keys(p, ['id','origin','text','n_tokens','token_ids','ids_sha256'], 'prompt')
        pid = p['id']
        require(type(pid) is str and pid in counts and pid not in seen, 'unknown/duplicate prompt')
        seen.add(pid)
        integer(p['n_tokens'], pid + ' n_tokens', 1)
        require(p['n_tokens'] == counts[pid], pid + ': n_tokens mismatch')
        array(p['token_ids'], counts[pid], pid, 'token')
        digest = hashlib.sha256(json.dumps(p['token_ids']).encode()).hexdigest()
        require(p['ids_sha256'] == digest, pid + ': token hash mismatch')
        require(type(p['origin']) is str and type(p['text']) is str, pid + ': invalid metadata')
    require(seen == set(counts), 'missing prompt')

def stats(values):
    n = len(values)
    require(n >= 2, 'at least two values needed for sample SD')
    s = sorted(values)
    return {'n': n, 'median': statistics.median(s), 'max': s[-1], 'min': s[0],
            'sample_sd': statistics.stdev(s), 'p99_nearest_rank': s[(99*n + 99)//100 - 1]}

def bars(agree, n, median, maximum):
    integer(n, 'bar n', 1)
    integer(agree, 'bar agree')
    require(agree <= n, 'agree exceeds n')
    number(median, 'bar median', -NEG_TOL)
    number(maximum, 'bar max', -NEG_TOL)
    require(median <= maximum, 'bar median exceeds max')
    return {'top1_ge_99pct': 100*agree >= 99*n,
            'kl_median_le_1e_4': median <= 1e-4,
            'kl_max_le_0_1': maximum <= 0.1}

def read_e2e(doc, leg, counts, bf, det):
    keys(doc, ['leg','checkpoint','note','prompts','seconds','sanity_p01_last_top1','sanity_pass'], leg)
    require(doc['leg'] == leg and doc['checkpoint'] == leg, 'checkpoint/leg mismatch')
    require(type(doc['note']) is str, 'missing scope note')
    number(doc['seconds'], 'seconds', 0)
    keys(doc['prompts'], counts, 'e2e prompts')
    deterministic = True
    for pid, n in counts.items():
        p = doc['prompts'][pid]
        keys(p, ['T','ref_top1','ref_margin','paths'], pid)
        integer(p['T'], pid + ' T', 1)
        require(p['T'] == n, pid + ': inconsistent T')
        array(p['ref_top1'], n, pid + ' REF', 'token')
        array(p['ref_margin'], n, pid + ' margin', minimum=0)
        keys(p['paths'], path_ids(pid, bf, det), pid + ' paths')
        for name, q in p['paths'].items():
            keys(q, ['top1_agree','kl','maxdiff_over_std','top1_path'], pid + '/' + name)
            array(q['top1_agree'], n, 'agreement flags', 'bool')
            array(q['top1_path'], n, 'path tokens', 'token')
            array(q['kl'], n, 'KL', minimum=-NEG_TOL)
            array(q['maxdiff_over_std'], n, 'maxdiff', minimum=0)
            require(q['top1_agree'] == [a == b for a,b in zip(p['ref_top1'],q['top1_path'])], pid + '/' + name + ': token/flag disagreement')
        if pid in det:
            ref2 = p['paths']['REF#2']
            deterministic &= ref2['top1_path'] == p['ref_top1'] and all(x == 0 for x in ref2['maxdiff_over_std'])
            deterministic &= all(abs(x) <= NEG_TOL for x in ref2['kl'])
            deterministic &= p['paths']['XS18#2'] == p['paths']['XS18']
    integer(doc['sanity_p01_last_top1'], 'sanity token', high=248320)
    require(type(doc['sanity_pass']) is bool, 'sanity_pass must be boolean')
    last = doc['prompts']['p01-ordinary-short']['ref_top1'][-1]
    require(doc['sanity_p01_last_top1'] == last and doc['sanity_pass'] == (last == 25358), 'stored sanity inconsistent with tokens')
    return last == 25358, bool(deterministic)

def read_layers(rows, heads, leg, layers, counts, bf, det):
    paths = path_prompts(counts, bf, det)
    dk = {a+'|'+p for a in ('REF#2','XS18#2') for p in det}
    seen = set()
    deterministic = True
    for row in rows:
        require(type(row) is dict, 'layer must be object')
        layer = row.get('layer')
        integer(layer, 'layer', high=64)
        require(layer in layers and layer not in seen, 'duplicate/extra layer')
        seen.add(layer)
        linear = layer % 4 != 3
        fields = {'leg','layer','type','seconds','det_bit_equal'} | set(paths)
        if linear:
            fields.add('inputs_s')
        keys(row, fields, 'layer record')
        require(row['leg'] == leg, 'layer leg mismatch')
        require(row['type'] == ('linear_attention' if linear else 'full_attention'), 'wrong layer type')
        number(row['seconds'], 'layer seconds', 0)
        if linear:
            number(row['inputs_s'], 'inputs_s', 0)
        for name, ids in paths.items():
            keys(row[name], ids, 'layer ' + name + ' prompts')
            for value in row[name].values():
                number(value, 'divergence', 0)
        keys(row['det_bit_equal'], dk, 'determinism layer coverage')
        for value in row['det_bit_equal'].values():
            require(type(value) is bool, 'determinism flag not bool')
            deterministic &= value
        for pid in det:
            deterministic &= row['REF#2'][pid] == 0
            deterministic &= row['XS18#2'][pid] == row['XS18'][pid]
    require(seen == set(layers), 'missing layer')
    expected = {(l,a,p) for l in layers if l % 4 != 3 for a in ('XS18','XS20','XS18#2') for p in paths[a]}
    found = set()
    for row in heads:
        keys(row, ['leg','layer','path','prompt','rel_y'], 'head record')
        integer(row['layer'], 'head layer', high=64)
        require(type(row['path']) is str and type(row['prompt']) is str, 'head identity')
        key = (row['layer'],row['path'],row['prompt'])
        require(row['leg'] == leg and key in expected and key not in found, 'extra/duplicate head record')
        found.add(key)
        array(row['rel_y'], 48, 'head errors', minimum=0)
    require(found == expected, 'missing head record')
    return {'physical_layers': len(seen), 'physical_head_rows': len(found),
            'recorded_residual_determinism': bool(deterministic),
            'recorded_bit_flags': len(seen)*len(dk)}

def aggregate(bundle, counts=None, bf=None, det=None, layer_sets=None):
    """Pure API permits small, wholly synthetic fixtures. CLI uses frozen constants."""
    counts = COUNTS if counts is None else counts
    bf = BF if bf is None else bf
    det = DET if det is None else det
    layer_sets = {'stock': set(range(64)), 'abl': set(range(17,64))} if layer_sets is None else layer_sets
    keys(bundle, ['prompts','e2e','divergence','heads','errors'], 'bundle')
    prompt_manifest(bundle['prompts'], counts, bf, det)
    for field in ('e2e','divergence','heads','errors'):
        keys(bundle[field], ['stock','abl'], field)
    require(all(bundle['errors'][leg] == [] for leg in ('stock','abl')), 'recorded guard error')
    layers = {}
    checks = {}
    for leg in ('stock','abl'):
        layers[leg] = read_layers(bundle['divergence'][leg],bundle['heads'][leg],leg,layer_sets[leg],counts,bf,det)
        sanity, logit_det = read_e2e(bundle['e2e'][leg],leg,counts,bf,det)
        checks[leg] = {'sanity': sanity, 'logit_determinism': logit_det}
    # Every cell is invalidated by any duplicate-path failure, per original prereg.
    all_det = all(layers[x]['recorded_residual_determinism'] and checks[x]['logit_determinism'] for x in checks)
    all_sanity = all(c['sanity'] for c in checks.values())
    result = {'scope': 'independent aggregation of supplied measurements, not a model rerun',
              'source_main': SOURCE_SHA, 'cells': {}, 'layer_coverage': layers,
              'checks': checks, 'global_recorded_determinism': all_det,
              'guard': 'complete finite records and no recorded error; not a re-execution of guards',
              'bf16h_context_positions': sum(counts[p] for p in bf)}
    for leg in ('stock','abl'):
        for arm in ARMS:
            kl, flips, negatives, per_prompt = [], [], [], {}
            for pid, n in counts.items():
                p = bundle['e2e'][leg]['prompts'][pid]
                q = p['paths'][arm]
                agreed = 0
                for i in range(n):
                    if p['ref_top1'][i] == q['top1_path'][i]:
                        agreed += 1
                    else:
                        flips.append({'checkpoint': leg, 'arm': arm, 'prompt': pid, 'position': i,
                                      'ref_token': p['ref_top1'][i], 'path_token': q['top1_path'][i], 'ref_margin': p['ref_margin'][i]})
                    if q['kl'][i] < 0:
                        negatives.append({'prompt':pid,'position':i,'kl':q['kl'][i]})
                kl.extend(q['kl'])
                per_prompt[pid] = {'positions': n, 'agree': agreed, 'agreement_fraction': agreed/n, 'kl': stats(q['kl'])}
            n = sum(counts.values())
            require(len(kl) == n, 'pooled denominator')
            ks = stats(kl)
            decisions = bars(n-len(flips), n, ks['median'], ks['max'])
            result['cells'][leg+'/'+arm] = {'prompts':len(counts), 'positions': n, 'agree':n-len(flips),
                'agreement_fraction': (n-len(flips))/n, 'flips':flips, 'kl':ks,
                'negative_kl':negatives, 'negative_kl_tolerance':NEG_TOL,
                'per_prompt':per_prompt, 'bars':decisions,
                'verdict':'PASS' if all(decisions.values()) and all_det and all_sanity else 'FAIL'}
    return result

def registered_manifest(prereg):
    blocks = re.findall(r'```json\n(.*?)\n```', prereg.read_text(), re.S)
    require(len(blocks) == 2, 'prereg manifests absent')
    return loads(blocks[0])

def read_bundle(source, manifest):
    observed = {}
    # Fixed allowlist avoids allowing a caller to omit evidence from the manifest.
    mandatory = {'PREREG.md','prompts-e2e.json','e2e.py'} | {
        'runs/'+name+'-'+leg+ext for leg in ('stock','abl')
        for name, ext in [('e2e','.json'),('divergence','.jsonl'),('heads','.jsonl'),('errors','.jsonl')]}
    keys(manifest, mandatory, 'input manifest')
    raw = {}
    for name, digest in manifest.items():
        path = source/name
        if digest is None:
            require(name.startswith('runs/errors-') and not path.exists(), 'unexpected error log: '+name)
            observed[name] = None
            continue
        require(type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest), 'bad hash')
        data = path.read_bytes()
        observed[name] = hashlib.sha256(data).hexdigest()
        require(observed[name] == digest, 'input hash mismatch: '+name)
        raw[name] = data.decode('utf-8')
    bundle = {'prompts':loads(raw['prompts-e2e.json']), 'e2e':{}, 'divergence':{}, 'heads':{}, 'errors':{}}
    for leg in ('stock','abl'):
        bundle['e2e'][leg] = loads(raw['runs/e2e-'+leg+'.json'])
        for name in ('divergence','heads'):
            lines = raw['runs/'+name+'-'+leg+'.jsonl'].splitlines()
            require(all(line.strip() for line in lines), 'blank JSONL record')
            bundle[name][leg] = [loads(line) for line in lines]
        bundle['errors'][leg] = []
    return bundle, observed

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--prereg', type=Path, default=Path(__file__).with_name('PREREG.md'))
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv)
    # Never leave a stale successful receipt looking like the result of a failed run.
    if args.output.exists():
        print('INVALID EVIDENCE: output exists; use a fresh output name', file=sys.stderr)
        return 2
    try:
        manifest = registered_manifest(args.prereg)
        bundle, observed = read_bundle(args.source, manifest)
        result = aggregate(bundle)
        result['input_sha256'] = observed
        if any(c['verdict'] != 'PASS' for c in result['cells'].values()):
            result['status'] = 'NEGATIVE'
        else:
            result['status'] = 'AGGREGATED'
        text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n'
        # Open only after complete validation, exclusive creation, no partial PASS on rejection.
        with args.output.open('x') as f:
            f.write(text)
        print(result['status'] + ': four cells written')
        return 0 if result['status'] == 'AGGREGATED' else 1
    except (InvalidEvidence, OSError, UnicodeError, json.JSONDecodeError, OverflowError) as e:
        print('INVALID EVIDENCE: ' + str(e), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
