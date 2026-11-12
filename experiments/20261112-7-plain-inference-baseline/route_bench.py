"""Pre-registered route-level plain inference benchmark (issue #7). See PREREG.md.

Endpoint, key file and model name come from the environment (BRIDGE_URL, BRIDGE_KEY_FILE, BRIDGE_MODEL).
Nothing here logs the endpoint, the key, or any attestation field other than `verified`.

Usage (each mode under the shared route lock):
  python3 route_bench.py debug     # 1 chat request + 1 attestation check -> runs/debug.jsonl
  python3 route_bench.py probe     # exactly 1 admission probe          -> runs/probe.jsonl
  python3 route_bench.py batch     # registered batch                    -> runs/batch.jsonl
  python3 route_bench.py analyze   # statistics                          -> runs/summary.json
"""
import collections, datetime, hashlib, inspect, json, os, pathlib, random, re, statistics, sys, time
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).parent
RUNS = HERE / 'runs'
RUNS.mkdir(exist_ok=True)
SEED = 1112
TIMEOUT = 120
CAP_REQUESTS = 150
CAP_REQ_SECONDS = 1140.0
MAX_TOKENS_CAP = 256
DECODE_PROMPT = 'Count upward from 1, writing every number in words, separated by commas. Do not stop.'
PREFILL_TARGETS = [128, 1024, 2048, 4096, 8192]
DECODE_MAX = [16, 64, 128, 256]
REPEAT_TARGET = 4096
PROBE_WORDS = 8192


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def vocab():
    """Fixed 512-word vocabulary: the 512 most frequent lowercase alphabetic words (3-9 letters) in the
    standard library's argparse source, ties broken alphabetically. Written to runs/vocab.txt for the record."""
    import argparse
    words = re.findall(r'\b[a-z]{3,9}\b', inspect.getsource(argparse))
    c = collections.Counter(words)
    v = [w for w, _ in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))][:512]
    assert len(v) == 512, len(v)
    p = RUNS / 'vocab.txt'
    if not p.exists():
        p.write_text('\n'.join(v) + '\n')
    return v


def unique_prompt(n_words, seed):
    r = random.Random(seed)
    v = vocab()
    tag = '%016x' % r.getrandbits(64)
    return tag + ' ' + ' '.join(r.choice(v) for _ in range(n_words))


# ---------------------------------------------------------------- transport

def _cfg():
    return (os.environ['BRIDGE_URL'], pathlib.Path(os.environ['BRIDGE_KEY_FILE']).read_text().strip(),
            os.environ['BRIDGE_MODEL'])


def http(path, body=None):
    base, key, _ = _cfg()
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data,
                                 headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            dt = time.monotonic() - t0
            return r.status, json.loads(raw), dt, None
    except urllib.error.HTTPError as e:
        dt = time.monotonic() - t0
        try:
            txt = e.read().decode('utf-8', 'replace')[:2000]
        except Exception:
            txt = ''
        return e.code, None, dt, txt
    except Exception as e:  # transport error / timeout; never log endpoint
        return None, None, time.monotonic() - t0, type(e).__name__


def attest():
    st, j, dt, err = http('/attestation')
    return {'kind': 'attestation', 'http_status': st, 'verified': bool(j and j.get('verified') is True),
            'checked_utc': now(), 'wall_seconds': dt, 'error': (None if j else (err or '')[:200])}


def chat(prompt, max_tokens):
    assert max_tokens <= MAX_TOKENS_CAP
    _, _, model = _cfg()
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0, 'seed': SEED,
            'max_tokens': max_tokens}
    st, j, dt, err = http('/v1/chat/completions', body)
    row = {'kind': 'chat', 'utc': now(), 'http_status': st, 'wall_seconds': dt, 'max_tokens': max_tokens,
           'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'prompt_chars': len(prompt)}
    if j is not None:
        ch = (j.get('choices') or [{}])[0]
        msg = ch.get('message') or {}
        reason = msg.get('reasoning_content') or msg.get('reasoning') or ''
        row.update({'finish_reason': ch.get('finish_reason'), 'usage': j.get('usage'),
                    'content': msg.get('content') or '', 'reasoning_present': bool(reason),
                    'reasoning_chars': len(reason), 'response_sha256':
                        hashlib.sha256(json.dumps(j, sort_keys=True).encode()).hexdigest()})
    else:
        row['error'] = (err or '')[:2000]
    return row


def count_requests():
    n, secs = 0, 0.0
    for f in ('debug.jsonl', 'probe.jsonl', 'batch.jsonl'):
        p = RUNS / f
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    n += 1
                    secs += r.get('wall_seconds') or 0.0
    return n, secs


def append(name, row):
    with (RUNS / name).open('a') as f:
        f.write(json.dumps(row) + '\n')


# ---------------------------------------------------------------- modes

def mode_debug():
    a = attest(); append('debug.jsonl', a); print(json.dumps({k: a[k] for k in ('http_status', 'verified')}))
    r = chat('Name one prime number.', 8); append('debug.jsonl', r)
    print(json.dumps({k: r.get(k) for k in ('http_status', 'wall_seconds', 'finish_reason', 'usage', 'content',
                                             'reasoning_present', 'error')}))


def mode_probe():
    if (RUNS / 'probe.jsonl').exists():
        sys.exit('probe already sent once; PREREG allows exactly one')
    prompt = unique_prompt(PROBE_WORDS, 1111999)
    r = chat(prompt, 1); r['role'] = 'admission_probe'; r['words'] = PROBE_WORDS
    append('probe.jsonl', r)
    print(json.dumps({k: r.get(k) for k in ('http_status', 'wall_seconds', 'finish_reason', 'usage', 'error')}))


def plan_cells(tok_per_word, limit_tokens=None):
    cells = []
    for t in PREFILL_TARGETS:
        if limit_tokens and t > 0.9 * limit_tokens:
            continue
        cells.append({'cell': 'prefill_%d' % t, 'arm': 'prefill', 'target': t,
                      'words': max(1, round((t - 20) / tok_per_word)), 'max_tokens': 1})
    for m in DECODE_MAX:
        cells.append({'cell': 'decode_%d' % m, 'arm': 'decode', 'max_tokens': m})
    if not (limit_tokens and REPEAT_TARGET > 0.9 * limit_tokens):
        cells.append({'cell': 'repeat_%d' % REPEAT_TARGET, 'arm': 'repeat', 'target': REPEAT_TARGET,
                      'words': max(1, round((REPEAT_TARGET - 20) / tok_per_word)), 'max_tokens': 1})
    return cells


def mode_batch():
    probe = [json.loads(l) for l in (RUNS / 'probe.jsonl').read_text().splitlines() if l.strip()][0]
    limit = None
    mchar = re.search(r'prompt over (\d+) chars', probe.get('error') or '')
    if mchar:  # Amendment 1: bridge-side character limit; cells sized by words under 90% of it
        return mode_batch_cells(char_cells(int(mchar.group(1))))
    if probe.get('usage'):
        tpw = (probe['usage']['prompt_tokens'] - 20) / PROBE_WORDS
    else:
        err = probe.get('error') or ''
        m = re.search(r'maximum context length is (\d+)', err)
        limit = int(m.group(1)) if m else None
        m2 = re.search(r'\((\d+) in the messages', err) or re.search(r'(\d+) input tokens', err)
        if not m2:
            sys.exit('probe rejected without a usable token count; see probe.jsonl')
        tpw = (int(m2.group(1)) - 20) / PROBE_WORDS
    cells = plan_cells(tpw, limit)
    (RUNS / 'plan.json').write_text(json.dumps({'tokens_per_word': tpw, 'limit_tokens': limit, 'cells': cells},
                                               indent=2) + '\n')
    return mode_batch_cells(cells)


CHAR_WORDS = [16, 256, 512, 1024, 2048]
REPEAT_WORDS = 1024


def char_cells(limit_chars):
    cap = int(0.9 * limit_chars)
    cells = [{'cell': 'prefill_w%d' % w, 'arm': 'prefill', 'words': w, 'max_tokens': 1, 'max_chars': cap}
             for w in CHAR_WORDS]
    cells += [{'cell': 'decode_%d' % m, 'arm': 'decode', 'max_tokens': m} for m in DECODE_MAX]
    cells.append({'cell': 'repeat_w%d' % REPEAT_WORDS, 'arm': 'repeat', 'words': REPEAT_WORDS, 'max_tokens': 1,
                  'max_chars': cap})
    (RUNS / 'plan.json').write_text(json.dumps({'amendment': 1, 'limit_chars': limit_chars, 'max_chars': cap,
                                               'cells': cells}, indent=2) + '\n')
    return cells


def fit_prompt(words, seed, max_chars=None):
    p = unique_prompt(words, seed)
    if max_chars and len(p) > max_chars:
        p = p[:max_chars].rsplit(' ', 1)[0]
    return p


def mode_batch_cells(cells):
    repeat_prompt = None
    for c in cells:
        if c['arm'] == 'repeat':
            repeat_prompt = fit_prompt(c['words'], 1113000, c.get('max_chars'))
    used, secs = count_requests()
    need = len(cells) * 11 + 2
    if used + need > CAP_REQUESTS:
        sys.exit('request cap would be exceeded: used %d need %d' % (used, need))
    a = attest(); a['role'] = 'start'; append('batch.jsonl', a); used += 1; secs += a['wall_seconds']
    if not a['verified']:
        print('attestation not verified; stopping'); return
    idx = 0; consec_err = 0; stop = None
    for rnd in range(11):
        order = list(range(len(cells))); random.Random(SEED + rnd).shuffle(order)
        for ci in order:
            c = cells[ci]
            if secs > CAP_REQ_SECONDS:
                stop = 'request_time_cap'; break
            if used >= CAP_REQUESTS - 1:
                stop = 'request_cap'; break
            if c['arm'] == 'prefill':
                prompt = fit_prompt(c['words'], 1112000 + idx, c.get('max_chars'))
            elif c['arm'] == 'repeat':
                prompt = repeat_prompt
            else:
                prompt = DECODE_PROMPT
            r = chat(prompt, c['max_tokens']); used += 1; secs += r['wall_seconds']
            r.update({'cell': c['cell'], 'arm': c['arm'], 'round': rnd, 'warmup': rnd == 0, 'index': idx,
                      'prompt': prompt if c['arm'] != 'decode' else DECODE_PROMPT})
            if r['http_status'] in (429, 503):
                time.sleep(30)
                r2 = chat(prompt, c['max_tokens']); used += 1; secs += r2['wall_seconds']
                r['retried'] = True; append('batch.jsonl', r)
                r2.update({'cell': c['cell'], 'arm': c['arm'], 'round': rnd, 'warmup': rnd == 0, 'index': idx,
                           'retry_of': idx, 'prompt': r['prompt']})
                r = r2
                if r['http_status'] in (429, 503):
                    append('batch.jsonl', r); stop = 'second_429_503'; break
            append('batch.jsonl', r)
            print('%s r%d %s %.2fs %s %s' % (r['utc'][11:19], rnd, c['cell'], r['wall_seconds'], r['http_status'],
                                             (r.get('usage') or {}).get('completion_tokens')), flush=True)
            idx += 1
            if r['http_status'] != 200:
                consec_err += 1
                if consec_err >= 2:
                    stop = 'two_errors_in_a_row'; break
            else:
                consec_err = 0
        if stop:
            break
    a = attest(); a['role'] = 'end'; append('batch.jsonl', a)
    print(json.dumps({'stop': stop, 'requests_used_incl_end_attest': used + 1, 'request_seconds': secs}))
    (RUNS / 'batch_meta.json').write_text(json.dumps({'stop': stop, 'requests_used': used + 1,
                                                      'request_seconds': secs, 'finished_utc': now()}, indent=2) + '\n')


# ---------------------------------------------------------------- analysis

def ols(xs, ys):
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs); sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx; a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in res) / (n - 2)
    se_b = (s2 / sxx) ** 0.5
    ss_tot = sum((y - my) ** 2 for y in ys)
    return {'intercept_s': a, 'slope_s_per_token': b, 'slope_se': se_b, 'n': n,
            'r2': 1 - sum(r * r for r in res) / ss_tot if ss_tot else None}


def mode_analyze():
    rows = [json.loads(l) for l in (RUNS / 'batch.jsonl').read_text().splitlines() if l.strip()]
    chats = [r for r in rows if r.get('kind') == 'chat']
    ok = [r for r in chats if r['http_status'] == 200 and not r.get('retried')]
    timed = [r for r in ok if not r['warmup']]
    cells = collections.OrderedDict()
    for r in timed:
        cells.setdefault(r['cell'], []).append(r)
    out = {'cells': {}, 'errors': [{k: r.get(k) for k in ('index', 'cell', 'http_status', 'error')}
                                   for r in chats if r['http_status'] != 200]}
    for name, rs in cells.items():
        w = [r['wall_seconds'] for r in rs]
        out['cells'][name] = {
            'arm': rs[0]['arm'], 'n': len(w), 'median_s': statistics.median(w),
            'sd_s': statistics.stdev(w) if len(w) > 1 else None, 'min_s': min(w), 'max_s': max(w),
            'median_prompt_tokens': statistics.median(r['usage']['prompt_tokens'] for r in rs),
            'median_completion_tokens': statistics.median(r['usage']['completion_tokens'] for r in rs),
            'finish_length': sum(r['finish_reason'] == 'length' for r in rs),
            'reasoning_present': sum(r['reasoning_present'] for r in rs)}
    for arm, key, cellnames in (('prefill', 'prompt_tokens', sorted([c for c in cells if c.startswith('prefill_')],
                                                     key=lambda c: out['cells'][c]['median_prompt_tokens'])),
                                ('decode', 'completion_tokens', sorted([c for c in cells if c.startswith('decode_')],
                                                         key=lambda c: int(c.split('_')[1])))):
        rs = [r for c in cellnames for r in cells[c]]
        if len(cellnames) < 2:
            out[arm] = {'resolved': False, 'reason': 'fewer than 2 cells'}; continue
        fit = ols([r['usage'][key] for r in rs], [r['wall_seconds'] for r in rs])
        lo, hi = out['cells'][cellnames[0]], out['cells'][cellnames[-1]]
        two_pt = (hi['median_s'] - lo['median_s']) / (hi['median_' + key] - lo['median_' + key])
        nonoverlap = lo['max_s'] < hi['min_s']
        full = all(out['cells'][c]['n'] >= 10 for c in cellnames)
        length_ok = all(out['cells'][c]['finish_length'] >= 8 for c in cellnames) if arm == 'decode' else True
        passed = nonoverlap and full and length_ok and fit['slope_s_per_token'] > 0
        out[arm] = {'fit': fit, 'tokens_per_second_fit': 1 / fit['slope_s_per_token'] if fit['slope_s_per_token'] > 0 else None,
                    'two_point_slope_s_per_token': two_pt, 'tokens_per_second_two_point': 1 / two_pt if two_pt > 0 else None,
                    'extreme_cells_nonoverlap': nonoverlap, 'all_cells_n_ge_10': full, 'decode_length_rule': length_ok,
                    'PASS': passed}
    for rp, up in (('repeat_4096', 'prefill_4096'), ('repeat_w1024', 'prefill_w1024')):
        if rp in out['cells'] and up in out['cells']:
            R, U = out['cells'][rp], out['cells'][up]
            out['repeat_vs_unique'] = {'repeat_cell': rp, 'unique_cell': up, 'repeat_median_s': R['median_s'],
                                       'unique_median_s': U['median_s'], 'repeat_prompt_tokens': R['median_prompt_tokens'],
                                       'unique_prompt_tokens': U['median_prompt_tokens'],
                                       'nonoverlap': R['max_s'] < U['min_s'] or U['max_s'] < R['min_s']}
    att = [r for r in rows if r.get('kind') == 'attestation']
    out['attestation'] = [{'role': r.get('role'), 'verified': r['verified'], 'checked_utc': r['checked_utc']} for r in att]
    out['requests_total_all_files'], out['request_seconds_all_files'] = count_requests()
    out['reasoning_rows_any'] = sum(r.get('reasoning_present', False) for r in ok)
    (RUNS / 'summary.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    {'debug': mode_debug, 'probe': mode_probe, 'batch': mode_batch, 'analyze': mode_analyze}[sys.argv[1]]()
