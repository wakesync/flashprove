#!/usr/bin/env python3
"""Frozen prompt set for 20261111-8-qwen-e2e-agreement (PREREG "Prompt set"). Writes prompts-e2e.json.

Nine prompts come from PR #68's prompts.json by id (token ids as committed; p06a is the first 256 ids of p06-digits).
One new prompt, p11-chat-long, is tokenised with the pinned tokenizer.json (sha256 0997f410..., the file PR #68 used),
without special tokens, the special tokens of the hand-written chat template parsed as such (as PR #68's prompts.py).
Usage: make_prompts_e2e.py <tokenizer.json> <out.json>   (needs `tokenizers`; only for p11)
"""
import hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "20261109-8-qwen-real-weights" / "prompts.json"
TOK_SHA = "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3"
P11_SHA = "06b69c88e68d19735155435454e066422da4db842b361298dee2b68b220a23d9"   # registered in PREREG
P06A_SHA_PREFIX = "a32cbab1be6fdf70"                                                   # registered in PREREG

U = ("I keep a small notebook about the lighthouse on the north point, and I would like your help turning it into "
     "something readable. Here are my notes, in the order I wrote them. The tower was built in 1871 from granite "
     "quarried two valleys over, carried down on sledges in the winter when the ground was hard. The first keeper "
     "was a widower named Aldous Penn, who kept the log in a careful hand and recorded the weather four times a day. "
     "In 1893 a storm broke three panes of the lantern room and Penn sat up all night holding a canvas sheet over the "
     "gap so the light would not go out. The lens was replaced in 1910 with a larger one that had to be assembled "
     "inside the tower, piece by piece, by two engineers who complained about the stairs in every letter home. "
     "During the war the light was dimmed, and the keeper's daughter learned Morse code from the coastguard signaller "
     "who lodged with them. The station was automated in 1964, and the last keeper left with a clock, a kettle and "
     "the logbooks, which are now in the town library. Please write a short history of the lighthouse in four "
     "paragraphs, keep the tone plain, and end with one sentence about why the place still matters to the town.")
P11_TEXT = f"<|im_start|>user\n{U}<|im_end|>\n<|im_start|>assistant\n<think>\n"
ORDER = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p02-ordinary-paragraph",
         "p04-repeat-punct", "p05-code", "p03-repeat-word", "p06a-digits-256", "p11-chat-long"]

def sha(ids): return hashlib.sha256(json.dumps(ids).encode()).hexdigest()

def main():
    from tokenizers import Tokenizer
    tp = Path(sys.argv[1]); assert hashlib.sha256(tp.read_bytes()).hexdigest() == TOK_SHA, "tokenizer sha mismatch"
    src = {p["id"]: p for p in json.load(open(SRC))["prompts"]}
    rows = []
    for pid in ORDER:
        if pid == "p06a-digits-256":
            ids = src["p06-digits"]["token_ids"][:256]; text = None; origin = "PR #68 p06-digits, first 256 token ids"
            assert sha(ids).startswith(P06A_SHA_PREFIX)
        elif pid == "p11-chat-long":
            ids = Tokenizer.from_file(str(tp)).encode(P11_TEXT, add_special_tokens=False).ids; text = P11_TEXT
            origin = "new (this experiment), tokenised with the pinned tokenizer.json"
            assert sha(ids) == P11_SHA, sha(ids)
        else:
            p = src[pid]; ids = p["token_ids"]; text = p["text"]; origin = "PR #68 prompts.json"
            assert sha(ids) == p["ids_sha256"]
        rows.append(dict(id=pid, origin=origin, text=text, n_tokens=len(ids), token_ids=ids, ids_sha256=sha(ids)))
    out = dict(tokenizer_sha256=TOK_SHA, n_prompts=len(rows), total_tokens=sum(r["n_tokens"] for r in rows),
               bf16h_subset=["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p03-repeat-word"],
               determinism_subset=["p01-ordinary-short", "p04-repeat-punct", "p09-multilingual"], prompts=rows)
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(out["n_prompts"], out["total_tokens"], [r["n_tokens"] for r in rows])

if __name__ == "__main__": main()
