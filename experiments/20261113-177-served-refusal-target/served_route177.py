"""Route client for issue #177 (PREREG "Collection"). PR #133 served_route.py, changed: max_tokens 48, one repetition per prompt, lane-wide
request cap 20 persisted in <state> (counts every HTTP attempt incl. attestation, probe and retries).
Endpoint, key and model come from env (never logged). Keeps only: verified flag + own timestamp; per reply: content,
reasoning, finish_reason, usage, wall time, sha256 of content.
Usage: served_route177.py probe <state.json> <out_dir>
       served_route177.py collect <state.json> <prompts.json> <out_dir>
429/503: wait 30 s, retry once, then stop."""
import datetime, hashlib, json, os, pathlib, sys, time, urllib.error, urllib.request

CAP_TOTAL = 20
MAX_TOKENS = 48
base = os.environ["BRIDGE_URL"]; model = os.environ["BRIDGE_MODEL"]
key = pathlib.Path(os.environ["BRIDGE_KEY_FILE"]).read_text().strip()
STATE = pathlib.Path(sys.argv[2])
st0 = json.loads(STATE.read_text()) if STATE.exists() else {"sent": 0, "log": []}

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def bump(what):
    if st0["sent"] >= CAP_TOTAL: raise RuntimeError("request_cap")
    st0["sent"] += 1; st0["log"].append([now(), what]); STATE.write_text(json.dumps(st0, indent=1) + "\n")

def request(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    for attempt in (1, 2):
        bump(path)
        req = urllib.request.Request(base + path, data=data, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt == 1:
                time.sleep(30); continue
            raise RuntimeError(f"http_{e.code}")

def chat(msg):
    t = time.monotonic()
    st, j = request("/v1/chat/completions", {"model": model, "messages": [{"role": "user", "content": msg}],
                                             "temperature": 0, "seed": 123, "max_tokens": MAX_TOKENS})
    ch = (j.get("choices") or [{}])[0]; m = ch.get("message") or {}
    content = m.get("content") or ""; reason = m.get("reasoning_content") or m.get("reasoning") or ""
    u = j.get("usage") or {}
    return dict(http_status=st, wall_seconds=round(time.monotonic() - t, 4), t_utc=now(), content=content, reasoning=reason,
                finish_reason=ch.get("finish_reason"),
                usage={k: u.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
                content_sha256=hashlib.sha256(content.encode()).hexdigest())

def attest(out):
    st, a = request("/attestation")
    att = dict(http_status=st, verified=bool(a.get("verified", False)), checked_utc=now())
    (out / "attestation.json").write_text(json.dumps(att, indent=1) + "\n")
    if not att["verified"]: raise RuntimeError("attestation_not_verified")

def main():
    mode = sys.argv[1]; out = pathlib.Path(sys.argv[-1]); out.mkdir(parents=True, exist_ok=True)
    rows = []; err = None; t0 = time.monotonic(); s_before = st0["sent"]
    try:
        if mode == "probe":
            r = chat("Reply with just the capital of Japan."); r.update(id="probe-1", rep=0, role="template probe, not measured"); rows.append(r)
            (out / "probe.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
        else:
            attest(out)
            P = json.load(open(sys.argv[3]))["prompts"]
            for p in P:
                r = chat(p["message"]); r.update(id=p["id"], rep=1); rows.append(r)
                with open(out / "replies.jsonl", "a") as f: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except Exception as e:
        err = f"{type(e).__name__}: {e}" if isinstance(e, RuntimeError) else type(e).__name__
    s = dict(mode=mode, requests_this_batch=st0["sent"] - s_before, requests_lane_total=st0["sent"], replies=len(rows),
             error=err, wall_seconds=round(time.monotonic() - t0, 2), end_utc=now())
    (out / f"batch-summary-{mode}.json").write_text(json.dumps(s, indent=1) + "\n"); print(json.dumps(s))
    for r in rows: print(r["id"], r["usage"], r["finish_reason"], "content_sha256", r["content_sha256"], "reasoning_len", len(r["reasoning"]))

if __name__ == "__main__": main()
