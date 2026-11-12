"""Bounded requests to the serving route. Endpoint, key and model come from env (never logged).
Usage: route.py probe <out_dir>            1 attestation check + 1 chat request (template probe, not measured)
       route.py collect <prompts.json> <out_dir>   attestation + each prompt x3, sequential
Keeps only: verified flag + own timestamp; per reply: content, reasoning, finish_reason, usage, wall time, sha256 of content.
Caps: max_tokens 64, temperature 0, seed 123, hard cap on request count. 429/503: wait 30 s, retry once, then stop."""
import datetime, hashlib, json, os, pathlib, sys, time, urllib.error, urllib.request

CAP_TOTAL = 60
base = os.environ["BRIDGE_URL"]; model = os.environ["BRIDGE_MODEL"]
key = pathlib.Path(os.environ["BRIDGE_KEY_FILE"]).read_text().strip()
sent = 0

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def request(path, body=None):
    global sent
    if sent >= CAP_TOTAL: raise RuntimeError("request_cap")
    data = None if body is None else json.dumps(body).encode()
    for attempt in (1, 2):
        sent += 1
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
                                             "temperature": 0, "seed": 123, "max_tokens": 64})
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
    rows = []; err = None; t0 = time.monotonic()
    try:
        attest(out)
        if mode == "probe":
            r = chat("Reply with just the capital of Japan."); r.update(id="probe-1", rep=0, role="template probe, not measured"); rows.append(r)
        else:
            P = json.load(open(sys.argv[2]))["prompts"]
            for rep in (1, 2, 3):
                for p in P:
                    r = chat(p["message"]); r.update(id=p["id"], rep=rep); rows.append(r)
                    with open(out / "replies.jsonl", "a") as f: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except Exception as e:
        err = f"{type(e).__name__}: {e}" if isinstance(e, RuntimeError) else type(e).__name__
    if mode == "probe":
        (out / "probe.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    s = dict(mode=mode, requests_sent_incl_attestation=sent, replies=len(rows), error=err, wall_seconds=round(time.monotonic() - t0, 2), end_utc=now())
    (out / "batch-summary.json").write_text(json.dumps(s, indent=1) + "\n"); print(json.dumps(s))
    for r in rows: print(r["id"], r["rep"], r["usage"], r["finish_reason"], repr(r["content"][:80]), repr(r["reasoning"][:40]))

if __name__ == "__main__": main()
