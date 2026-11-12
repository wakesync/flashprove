#!/usr/bin/env python3
"""Rebuild token ids for served replies and apply the registered exclusion rule (PREREG "Rebuild rule and exclusion rule").

Prompt ids: pinned chat_template.jinja rendered with jinja2 (messages = one user turn, add_generation_prompt=True,
enable_thinking=False), tokenised with the pinned tokenizer.json (add_special_tokens=False, special tokens parsed).
Reply ids: tokenised served content, plus <|im_end|> (248046) if finish_reason == "stop".
A prompt is included iff its rep-1 reply has empty reasoning, rebuilt prompt count == usage.prompt_tokens, rebuilt reply
count == usage.completion_tokens and finish_reason in {stop, length}.
Usage: rebuild_ids.py <tokenizer_dir> <runs/replies.jsonl> <prompts-served.json> <out served-ids.json>
<tokenizer_dir> holds tokenizer.json and chat_template.jinja of the pinned revision (sha256 asserted)."""
import hashlib, json, sys
from pathlib import Path
import jinja2
from tokenizers import Tokenizer

TOK_SHA = "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3"
TPL_SHA = "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041"
IM_END, ENDOFTEXT = 248046, 248044

def sha(b): return hashlib.sha256(b).hexdigest()

def load(tdir):
    tdir = Path(tdir)
    tb = (tdir / "tokenizer.json").read_bytes(); assert sha(tb) == TOK_SHA, "tokenizer sha"
    jb = (tdir / "chat_template.jinja").read_bytes(); assert sha(jb) == TPL_SHA, "template sha"
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, extensions=["jinja2.ext.loopcontrols"])
    def rx(m): raise Exception(m)
    env.globals["raise_exception"] = rx
    return Tokenizer.from_file(str(tdir / "tokenizer.json")), env.from_string(jb.decode())

def prompt_ids(tk, tpl, message):
    s = tpl.render(messages=[{"role": "user", "content": message}], add_generation_prompt=True, enable_thinking=False)
    return s, tk.encode(s, add_special_tokens=False).ids

def reply_ids(tk, content, finish):
    ids = tk.encode(content, add_special_tokens=False).ids
    return ids + [IM_END] if finish == "stop" else ids

def main():
    tk, tpl = load(sys.argv[1])
    rows = [json.loads(l) for l in open(sys.argv[2])]
    P = json.load(open(sys.argv[3]))["prompts"]
    out = dict(tokenizer_sha256=TOK_SHA, template_sha256=TPL_SHA, rule="PREREG", prompts=[])
    for p in P:
        reps = sorted([r for r in rows if r["id"] == p["id"]], key=lambda r: r["rep"])
        if not reps:
            out["prompts"].append(dict(id=p["id"], included=False, reasons=["no reply collected"])); continue
        r1 = reps[0]; text, pids = prompt_ids(tk, tpl, p["message"]); rids = reply_ids(tk, r1["content"], r1["finish_reason"])
        u = r1["usage"]; reasons = []
        if r1["reasoning"]: reasons.append("reasoning field not empty")
        if len(pids) != u["prompt_tokens"]: reasons.append(f"prompt count {len(pids)} != served {u['prompt_tokens']}")
        if len(rids) != u["completion_tokens"]: reasons.append(f"reply count {len(rids)} != served {u['completion_tokens']}")
        if r1["finish_reason"] not in ("stop", "length"): reasons.append(f"finish_reason {r1['finish_reason']}")
        # round trip: decoding the rebuilt reply ids must give back the served text (descriptive)
        dec = tk.decode([t for t in rids if t != IM_END], skip_special_tokens=False)
        reps_txt = [r["content"] for r in reps]
        out["prompts"].append(dict(
            id=p["id"], message=p["message"], included=not reasons, reasons=reasons, rendered_prompt=text,
            prompt_ids=pids, reply_ids=rids, served_usage=u, finish_reason=r1["finish_reason"], served_content=r1["content"],
            decode_roundtrip_equal=dec == r1["content"], n_reps=len(reps),
            reps_text_identical=len(set(reps_txt)) == 1 and len(reps) == 3,
            reps_usage=[r["usage"] for r in reps], reps_content_sha256=[r["content_sha256"] for r in reps]))
    inc = [q for q in out["prompts"] if q["included"]]
    out.update(n_included=len(inc), n_excluded=len(out["prompts"]) - len(inc),
               kill_exclusions=len(out["prompts"]) - len(inc) >= 5,
               measured_positions=sum(len(q["reply_ids"]) for q in inc))
    Path(sys.argv[4]).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for q in out["prompts"]:
        print(q["id"], "IN" if q["included"] else "OUT", q.get("reasons"), len(q.get("prompt_ids", [])), len(q.get("reply_ids", [])),
              q.get("reps_text_identical"), q.get("decode_roundtrip_equal"))
    print("included", out["n_included"], "measured positions", out["measured_positions"], "kill", out["kill_exclusions"])

if __name__ == "__main__": main()
