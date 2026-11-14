"""Strict admission of a frozen-run receipt, before comparison targets are opened.

This checks schema, provenance claims and internal consistency, not authenticity
or a new aggregation of raw records. It does not change reader arithmetic.
"""
import re
import recomp181_reader as R

LEGS = ('stock', 'abl')
STAT_FIELDS = ('n', 'min', 'median', 'max', 'sample_sd', 'p99_nearest_rank')
CELL_FIELDS = ('prompts', 'positions', 'agree', 'agreement_fraction', 'flips',
               'kl', 'negative_kl', 'negative_kl_tolerance', 'per_prompt', 'bars', 'verdict')


def boolean(value, where):
    R.require(type(value) is bool, where + ': expected boolean')


def number(value, where, minimum=None):
    R.require(type(value) in (int, float), where + ': expected number, got ' + type(value).__name__)
    R.number(value, where, minimum)


def exact_int(value, expected, where):
    R.integer(value, where)
    R.require(value == expected, where + ': expected ' + str(expected))


def stats(value, n, where):
    R.keys(value, STAT_FIELDS, where)
    exact_int(value['n'], n, where + '.n')
    for key in STAT_FIELDS[1:]:
        number(value[key], where + '.' + key, 0 if key == 'sample_sd' else -R.NEG_TOL)
    R.require(value['min'] <= value['median'] <= value['p99_nearest_rank'] <= value['max'],
              where + ': inconsistent statistic ordering')


def counts(value, n, where):
    exact_int(value['positions'], n, where + '.positions')
    R.integer(value['agree'], where + '.agree', high=n+1)
    number(value['agreement_fraction'], where + '.agreement_fraction', 0)
    R.require(value['agreement_fraction'] == value['agree']/n,
              where + ': inconsistent agreement_fraction')
    stats(value['kl'], n, where + '.kl')


def admit(receipt, manifest):
    """Reject malformed receipts, including inconsistent NEGATIVE status.

    A consistent NEGATIVE receipt is valid evidence and remains comparable.
    There is intentionally no requirement that a cell's measured bars pass.
    """
    R.keys(receipt, ('scope', 'source_main', 'cells', 'layer_coverage', 'checks',
                    'global_recorded_determinism', 'guard', 'bf16h_context_positions',
                    'input_sha256', 'status'), 'independent receipt')
    R.require(type(receipt['scope']) is str and receipt['scope'] ==
              'independent aggregation of supplied measurements, not a model rerun', 'receipt.scope: unexpected scope')
    R.require(type(receipt['guard']) is str and receipt['guard'] ==
              'complete finite records and no recorded error; not a re-execution of guards', 'receipt.guard: unexpected scope')
    R.require(receipt['source_main'] == R.SOURCE_SHA, 'receipt.source_main: not the frozen source')
    R.keys(receipt['input_sha256'], manifest, 'receipt.input_sha256')
    for path, expected in manifest.items():
        digest = receipt['input_sha256'][path]
        if expected is None:
            R.require(path in ('runs/errors-stock.jsonl', 'runs/errors-abl.jsonl') and digest is None,
                      'receipt.input_sha256.' + path + ': expected absent error log')
        else:
            R.require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest) is not None,
                      'receipt.input_sha256.' + path + ': expected SHA-256 string')
            R.require(digest == expected, 'receipt.input_sha256.' + path + ': frozen digest mismatch')
    R.keys(receipt['checks'], LEGS, 'receipt.checks')
    R.keys(receipt['layer_coverage'], LEGS, 'receipt.layer_coverage')
    for leg in LEGS:
        check = receipt['checks'][leg]
        R.keys(check, ('sanity', 'logit_determinism'), leg + '.checks')
        for key, value in check.items():
            boolean(value, leg + '.checks.' + key)
        layer = receipt['layer_coverage'][leg]
        R.keys(layer, ('physical_layers', 'physical_head_rows', 'recorded_residual_determinism',
                       'recorded_bit_flags'), leg + '.layer_coverage')
        layers = range(17, 64) if leg == 'stock' else range(64)
        exact_int(layer['physical_layers'], len(layers), leg + '.physical_layers')
        head_rows = sum(i % 4 != 3 for i in layers) * (2*len(R.COUNTS) + len(R.DET))
        exact_int(layer['physical_head_rows'], head_rows, leg + '.physical_head_rows')
        exact_int(layer['recorded_bit_flags'], len(layers)*2*len(R.DET), leg + '.recorded_bit_flags')
        boolean(layer['recorded_residual_determinism'], leg + '.recorded_residual_determinism')
    boolean(receipt['global_recorded_determinism'], 'receipt.global_recorded_determinism')
    deterministic = all(receipt['checks'][leg]['logit_determinism'] and
                        receipt['layer_coverage'][leg]['recorded_residual_determinism'] for leg in LEGS)
    R.require(receipt['global_recorded_determinism'] == deterministic,
              'receipt.global_recorded_determinism: inconsistent with checks')
    sane = all(receipt['checks'][leg]['sanity'] for leg in LEGS)
    exact_int(receipt['bf16h_context_positions'], sum(R.COUNTS[p] for p in R.BF), 'receipt.bf16h_context_positions')
    R.keys(receipt['cells'], (leg+'/'+arm for leg in LEGS for arm in R.ARMS), 'receipt.cells')
    for name, cell in receipt['cells'].items():
        leg, arm = name.split('/')
        R.keys(cell, CELL_FIELDS, name)
        exact_int(cell['prompts'], len(R.COUNTS), name + '.prompts')
        counts(cell, sum(R.COUNTS.values()), name)
        R.keys(cell['per_prompt'], R.COUNTS, name + '.per_prompt')
        for pid, n in R.COUNTS.items():
            prompt = cell['per_prompt'][pid]
            R.keys(prompt, ('positions', 'agree', 'agreement_fraction', 'kl'), name + '.' + pid)
            counts(prompt, n, name + '.' + pid)
        R.require(cell['agree'] == sum(p['agree'] for p in cell['per_prompt'].values()),
                  name + ': pooled/per-prompt agreement mismatch')
        for key, fn in (('min', min), ('max', max)):
            R.require(cell['kl'][key] == fn(p['kl'][key] for p in cell['per_prompt'].values()),
                      name + ': pooled/per-prompt KL ' + key + ' mismatch')
        R.require(type(cell['flips']) is list, name + '.flips: expected list')
        seen, flip_counts = set(), dict.fromkeys(R.COUNTS, 0)
        for flip in cell['flips']:
            where = name + '.flip'
            R.keys(flip, ('checkpoint', 'arm', 'prompt', 'position', 'ref_token', 'path_token', 'ref_margin'), where)
            R.require(flip['checkpoint'] == leg and flip['arm'] == arm, where + ': checkpoint/arm inconsistent with cell')
            pid = flip['prompt']
            R.require(type(pid) is str and pid in R.COUNTS, where + ': unknown prompt')
            R.integer(flip['position'], where + '.position', high=R.COUNTS[pid])
            identity = (pid, flip['position'])
            R.require(identity not in seen, where + ': duplicate identity')
            seen.add(identity)
            flip_counts[pid] += 1
            for key in ('ref_token', 'path_token'):
                R.integer(flip[key], where + '.' + key, high=248320)
            R.require(flip['ref_token'] != flip['path_token'], where + ': equal token IDs')
            number(flip['ref_margin'], where + '.ref_margin', 0)
        for pid, n in R.COUNTS.items():
            R.require(flip_counts[pid] == n-cell['per_prompt'][pid]['agree'], name + '.' + pid + ': flip count mismatch')
        number(cell['negative_kl_tolerance'], name + '.negative_kl_tolerance')
        R.require(cell['negative_kl_tolerance'] == R.NEG_TOL, name + ': changed negative KL tolerance')
        R.require(type(cell['negative_kl']) is list, name + '.negative_kl: expected list')
        seen = set()
        negatives = {pid: [] for pid in R.COUNTS}
        for item in cell['negative_kl']:
            where = name + '.negative_kl'
            R.keys(item, ('prompt', 'position', 'kl'), where)
            pid = item['prompt']
            R.require(type(pid) is str and pid in R.COUNTS, where + ': unknown prompt')
            R.integer(item['position'], where + '.position', high=R.COUNTS[pid])
            identity = (pid, item['position'])
            R.require(identity not in seen, where + ': duplicate identity')
            seen.add(identity)
            number(item['kl'], where + '.kl', -R.NEG_TOL)
            R.require(item['kl'] < 0, where + ': expected negative KL')
            negatives[pid].append(item['kl'])
        for pid, values in negatives.items():
            minimum = cell['per_prompt'][pid]['kl']['min']
            R.require((min(values) == minimum) if values else minimum >= 0,
                      name + '.' + pid + ': negative KL list/minimum mismatch')
        expected_bars = R.bars(cell['agree'], cell['positions'], cell['kl']['median'], cell['kl']['max'])
        R.keys(cell['bars'], expected_bars, name + '.bars')
        for key, value in cell['bars'].items():
            boolean(value, name + '.bars.' + key)
        R.require(cell['bars'] == expected_bars, name + ': inconsistent bars')
        verdict = 'PASS' if all(expected_bars.values()) and deterministic and sane else 'FAIL'
        R.require(type(cell['verdict']) is str and cell['verdict'] == verdict, name + ': inconsistent verdict')
    status = 'AGGREGATED' if all(c['verdict'] == 'PASS' for c in receipt['cells'].values()) else 'NEGATIVE'
    R.require(type(receipt['status']) is str and receipt['status'] == status, 'receipt.status: inconsistent with cell verdicts')
