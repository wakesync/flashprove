#!/usr/bin/env python3
"""The registered evaluation suite of PREREG.md, as data, plus the completeness checks that summarise.py and
decay_tables.py run before they produce anything (added after the run, review of PR #146; RESULTS section 6).

Registered (PREREG "Setup", "Prompt set", "Kill criterion"):
- DeltaNet layers: the 48 layers i in 0..63 with i % 4 != 3 (q1_forward.layer_type), 48 V heads each.
- S10: the 10 prompts of PR #124's prompts-e2e.json (sha256 pinned below), token counts as committed.
- S7: the registered reduced set (only under the PREREG's queue rule).
- PARTIAL: the forward stopped at its hard stop; the verdict is computed on the DeltaNet layers completed, which
  are a prefix of the registered layer order. It must be declared explicitly (`--partial-layers N`); a short input
  is never taken as PARTIAL on its own.
- Fixture: the debug fixture only (`--fixture`); internal consistency is checked, the registered identities are not,
  and its output is never a registered verdict.
"""
import hashlib, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTS = HERE.parent / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"   # PR #124, unchanged
PROMPTS_SHA256 = "47aa61b46e142382ffa58b88f918df6ec63f1158629df5938ec00961a5242cfc"   # PREREG "Prompt set"
N_LAYERS_MODEL = 64
DELTANET_LAYERS = [i for i in range(N_LAYERS_MODEL) if i % 4 != 3]   # q1_forward.layer_type
N_HEADS = 48
ARMS = ("T0", "T1", "T2", "T3")
SPLIT_SOURCES = ("cA_rounding", "softplus_table", "g_key_and_exp_table", "output_rounding")
SWEEP_F = ("14", "16", "18")
S7 = ("p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual",
      "p02-ordinary-paragraph", "p04-repeat-punct", "p05-code")
BAR = dict(e_tok=2.0 ** -9, e_cum=0.01, rejects=0)


class Incomplete(Exception):
    """The input is not the complete registered cell set (or a declared, consistent PARTIAL / fixture)."""


def need(cond, msg):
    if not cond: raise Incomplete(msg)


def registered_tokens(which="S10"):
    """{prompt id: token count} of the registered set, from the pinned prompts file."""
    data = PROMPTS.read_bytes()
    need(hashlib.sha256(data).hexdigest() == PROMPTS_SHA256, "prompts-e2e.json sha256 differs from the registered one")
    pr = {p["id"]: len(p["token_ids"]) for p in json.loads(data)["prompts"]}
    need(len(pr) == 10, "registered prompt file does not have 10 prompts")
    if which == "S7": pr = {k: v for k, v in pr.items() if k in S7}
    need(which in ("S10", "S7") and len(pr) == (10 if which == "S10" else 7), f"unknown or malformed set {which!r}")
    return pr


def expected(mode):
    """mode: dict(fixture=bool, set='S10'|'S7', partial_layers=None|int).
    Returns (layers, {prompt: T}) the input must match exactly, or (None, None) for the fixture."""
    if mode.get("fixture"):
        need(mode.get("partial_layers") is None and mode.get("set", "S10") == "S10", "--fixture cannot be combined with --set / --partial-layers")
        return None, None
    toks = registered_tokens(mode.get("set", "S10"))
    n = mode.get("partial_layers")
    if n is None: layers = list(DELTANET_LAYERS)
    else:
        need(isinstance(n, int) and 1 <= n < len(DELTANET_LAYERS), f"--partial-layers must be in 1..{len(DELTANET_LAYERS) - 1}")
        layers = DELTANET_LAYERS[:n]
    return layers, toks


def coverage_label(mode):
    if mode.get("fixture"): return "FIXTURE (debug, not a registered verdict)"
    if mode.get("partial_layers") is not None: return "PARTIAL"
    return "COMPLETE"


def finite(v):
    try: return math.isfinite(float(v))
    except (TypeError, ValueError): return False


def as_int(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise Incomplete(f"{what}: not a number: {v!r}")
    need(math.isfinite(f) and f == int(f), f"{what}: not an integer: {v!r}")
    return int(f)
