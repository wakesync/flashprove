#!/usr/bin/env python3
"""Held-out evaluation prompt manifest for 20261114-204-int-attn-heldout (PREREG "Prompts"). Writes prompts-heldout.json
and runs/prompt-check.json.

Eight prompts written by this lane for this experiment (none taken from PR #124's ten calibration prompts). Tokenised with
the pinned tokenizer.json (sha256 0997f410..., PR #68's file), no added special tokens; the chat-template special tokens
are written by hand and parsed as such, as PR #124's make_prompts_e2e.py does.

Checks (written to runs/prompt-check.json and asserted): each prompt <= 128 tokens, total <= 768; no prompt equals a
calibration prompt in text, token ids or id-list sha256; per prompt, the longest run of consecutive token ids shared with
any calibration prompt, and the shared families (chat template, repetition, multilingual) disclosed.

Usage: make_prompts.py <tokenizer.json>   (needs `tokenizers` 0.23.3; reads no weights)
"""
import hashlib, json, sys, tokenizers
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAL = HERE.parent / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"
TOK_SHA = "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3"
MAX_T, MAX_TOTAL = 128, 768

def chat(u): return f"<|im_start|>user\n{u}<|im_end|>\n<|im_start|>assistant\n<think>\n"

PROMPTS = [
    ("h01-prose-short", "ordinary prose",
     "The bakery on the corner opens at six, and by seven the line for rye bread already reaches"),
    ("h02-prose-paragraph", "ordinary prose",
     "Every autumn the orchard owners hire pickers from the valley towns. The work starts before sunrise, when the "
     "apples are still cold and the ladders are wet with dew. By noon the crates are stacked along the gravel lane, "
     "and a tractor hauls them to the barn where the sorting belt rattles all afternoon. Bruised fruit goes to the "
     "cider press, small fruit to the school, and the best of it is wrapped in paper and sent to the city markets."),
    ("h03-code-js", "code",
     "function countWords(text) {\n  const counts = new Map();\n  for (const raw of text.toLowerCase().split(/\\s+/)) {\n"
     "    const w = raw.replace(/[^a-z0-9]/g, \"\");\n    if (!w) continue;\n    counts.set(w, (counts.get(w) || 0) + 1);\n"
     "  }\n  return [...counts.entries()].sort((a, b) => b[1] - a[1]);\n}\n\nconsole.log(countWords(\"a b a c b a\"));\n"),
    ("h04-multilingual", "multilingual",
     "El tren sale a las ocho de la mañana. 東京の駅はとても広いです。 Поезд прибывает в полдень. "
     "मुझे चाय पसंद है। O mercado abre cedo aos sábados."),
    ("h05-chat-ordinary", "chat template, ordinary request",
     chat("How do I keep a sourdough starter healthy while I am travelling for two weeks?")),
    ("h06-repeat-count", "bounded repetition",
     " ".join(f"step {i}," for i in range(1, 25))),
    ("h07-code-sql", "code",
     "SELECT c.name, COUNT(o.id) AS orders, SUM(o.total) AS spent\nFROM customers c\n"
     "LEFT JOIN orders o ON o.customer_id = c.id AND o.created_at >= DATE '2024-01-01'\n"
     "WHERE c.country = 'NO'\nGROUP BY c.name\nHAVING COUNT(o.id) > 2\nORDER BY spent DESC\nLIMIT 10;\n"),
    ("h08-chat-multilingual", "chat template, multilingual",
     chat("Traduis en anglais, s'il te plaît : « Le musée ferme à dix-huit heures le dimanche, mais la librairie reste ouverte. »")),
]
DET = ["h01-prose-short", "h05-chat-ordinary"]   # PREREG V2: first and fifth prompt of the manifest order

def sha(ids): return hashlib.sha256(json.dumps(ids).encode()).hexdigest()

def longest_common_run(a, b):
    best, prev = 0, [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b):
            if x == y: cur[j + 1] = prev[j] + 1; best = max(best, cur[j + 1])
        prev = cur
    return best

def main():
    tp = Path(sys.argv[1]); assert hashlib.sha256(tp.read_bytes()).hexdigest() == TOK_SHA, "tokenizer sha mismatch"
    assert tokenizers.__version__ == "0.23.3", tokenizers.__version__
    tok = tokenizers.Tokenizer.from_file(str(tp))
    cal = json.load(open(CAL))["prompts"]
    cal_ids = {p["id"]: p["token_ids"] for p in cal}; cal_text = {p["text"] for p in cal if p["text"]}
    cal_sha = {sha(p["token_ids"]) for p in cal}
    rows, checks = [], []
    for pid, family, text in PROMPTS:
        ids = tok.encode(text, add_special_tokens=False).ids
        h = sha(ids)
        runs = {cid: longest_common_run(ids, cids) for cid, cids in cal_ids.items()}
        top = max(runs, key=runs.get)
        c = dict(id=pid, n_tokens=len(ids), ids_sha256=h, family=family,
                 exact_text_match=text in cal_text, exact_ids_match=any(ids == v for v in cal_ids.values()),
                 exact_sha_match=h in cal_sha, longest_shared_token_run=runs[top], longest_shared_with=top,
                 shared_runs=runs)
        assert len(ids) <= MAX_T, (pid, len(ids))
        assert not (c["exact_text_match"] or c["exact_ids_match"] or c["exact_sha_match"]), pid
        checks.append(c)
        rows.append(dict(id=pid, family=family, origin="new (this experiment), tokenised with the pinned tokenizer.json",
                         text=text, n_tokens=len(ids), token_ids=ids, ids_sha256=h))
    total = sum(r["n_tokens"] for r in rows); assert total <= MAX_TOTAL, total
    assert len({r["ids_sha256"] for r in rows}) == len(rows), "duplicate held-out prompt"
    split = hashlib.sha256(json.dumps([r["ids_sha256"] for r in rows]).encode()).hexdigest()
    cal_split = hashlib.sha256(json.dumps([sha(p["token_ids"]) for p in cal]).encode()).hexdigest()
    out = dict(tokenizer_sha256=TOK_SHA, tokenizers_version=tokenizers.__version__, n_prompts=len(rows), total_tokens=total,
               split_sha256=split, determinism_subset=DET, prompts=rows)
    (HERE / "prompts-heldout.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    families = {
        "chat_template": "h05 and h08 use the same hand-written Qwen chat template (<|im_start|>user ... <think>) as calibration "
                         "prompts p07, p08 and p11; the template tokens are shared by construction.",
        "repetition": "h06 is bounded repetition (counting 'step i,' 1..24), a different pattern from calibration p03 "
                      "(one word repeated) and p04 (one punctuation mark repeated).",
        "multilingual": "h04 and h08 are multilingual like calibration p09 (zh/fr/de); h04 uses es/ja/ru/hi/pt, h08 fr inside a chat template.",
        "code": "h03 (JavaScript) and h07 (SQL) are code like calibration p05 (Python)."}
    chk = dict(calibration_file=str(CAL.relative_to(HERE.parent.parent)), calibration_sha256=hashlib.sha256(CAL.read_bytes()).hexdigest(),
               calibration_split_sha256=cal_split, heldout_split_sha256=split, total_tokens=total, max_tokens=max(r["n_tokens"] for r in rows),
               any_exact_match=False, per_prompt=checks, near_duplicate_families=families)
    (HERE / "runs").mkdir(exist_ok=True)
    (HERE / "runs" / "prompt-check.json").write_text(json.dumps(chk, indent=1) + "\n")
    print(total, [r["n_tokens"] for r in rows], split[:16], [(c["id"], c["longest_shared_token_run"], c["longest_shared_with"]) for c in checks])

if __name__ == "__main__": main()
