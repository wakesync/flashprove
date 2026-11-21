#!/usr/bin/env python3
"""Tokenise the 10 frozen prompt texts of 20261109-8-qwen-real-weights with Inkling 2 Mini's tokenizer.json.
Usage: prompts.py <qwen prompts.json> <inkling tokenizer.json> <out.json>
Texts are read unchanged; add_special_tokens=False (as the Qwen experiment)."""
import hashlib, json, sys
from tokenizers import Tokenizer


def main():
    src = json.load(open(sys.argv[1]))
    tk = Tokenizer.from_file(sys.argv[2])
    sha = hashlib.sha256(open(sys.argv[2], "rb").read()).hexdigest()
    rows = []
    for p in src["prompts"]:
        ids = tk.encode(p["text"], add_special_tokens=False).ids
        rows.append(dict(id=p["id"], kind=p["kind"], text_sha256=hashlib.sha256(p["text"].encode()).hexdigest(),
                         n_tokens=len(ids), token_ids=ids,
                         ids_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest()))
    uniq = sorted({t for r in rows for t in r["token_ids"]})
    out = dict(source="experiments/20261109-8-qwen-real-weights/prompts.json", tokenizer_sha256=sha,
               n_prompts=len(rows), total_tokens=sum(r["n_tokens"] for r in rows), unique_tokens=len(uniq),
               prompts=rows)
    json.dump(out, open(sys.argv[3], "w"), indent=1)
    for r in rows:
        print(r["id"], r["n_tokens"])
    print("total", out["total_tokens"], "unique", len(uniq))


if __name__ == "__main__":
    main()
