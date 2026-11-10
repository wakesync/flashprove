# Partial rotary, 64 of 256 dimensions, theta 10^7

Optional arm registered in PREREG Amendment A1 before rotary code. Implementation: `../proof.cpp`, `rotary()`. Shared protocol limitations: `../README.md`.

## What is proved

At verifier-admitted **public position** t in [0,1024), 256 input words X at scale S=2^F, X_j in [-S,S). For j=0..31:

```
omega_j = theta^(-j/32)
Y[j]    = floor((X[j]*C[t,j] - X[j+32]*U[t,j])/S)
Y[j+32] = floor((X[j+32]*C[t,j] + X[j]*U[t,j])/S)
```

C and U are pinned integer approximations to S*cos(t*omega_j) and S*sin(t*omega_j). Y[64..255] equals X[64..255] exactly. Pairing is rotate-half over the 64-dimensional prefix, not adjacent pairs over all 256 dimensions. Every rotated output has an exact F-bit remainder and signed [-4*S,4*S) range. The public position, operator type and F are bound in the configuration string as well as the position-dependent coefficients.

The verifier looks up fixed public-position constants, builds linear relations and checks the proof. It does not see the input vector or evaluate trigonometric functions. With public C/U the two products per output are public-coefficient linear terms, not unnecessary committed multiplication gates. |C|,|U|<=S implies numerator magnitude<=2*S^2<=2^33 at F16, so exact remainders and output bounds rule out field wrapping.

## What is public, committed and prover-chosen

- Public: operator, F, position t, the 256 outputs.
- Fixed by the verifier from the public position: the C/U coefficients.
- Committed and chosen freely by the prover: all 256 inputs X and the remainders.

A proof therefore shows only: **there exist inputs in [-S,S) whose partial rotation at position t gives these outputs.** It says nothing about which q/k projection, model weights or token produced X. Because the rotation is nearly a bijection on the integer grid, **almost any in-range output vector can be proved.** The opus reviewer built a complete proof at position 517 for a random 256-word target, with the unmodified prover, after moving 3 of the 256 target words by 1 (29 of 32 pairs were hit exactly before that), and the unchanged verifier accepted it (https://github.com/wakesync/flashprove/pull/67#issuecomment-6757161440; the reviewer's run, not a committed run file of this PR). Binding X to committed weights and earlier layers is the job of the M3 statement (PR #70, draft), not of this PR.

## Separate table format and deterministic generator

`tables/rotary-manifest.json`, format `flashprove-qwen-rotary-v1`, leaves the previously published nonlinear manifest unchanged. Each `rotary-f<F>.i64le` contains 65536 headerless signed little-endian i64 words, flattened [position=1024][pair=32][cos,sin=2]. Output scale 2^F. The manifest pins each file's SHA-256; `rotary-pinned.h` is a generated C++ copy.

`rotary_tables.py` uses Q256 integer arithmetic only. Pi is Machin's formula 16*atan(1/5)-4*atan(1/239), each atan from 256 alternating terms with integer floors. Frequency is floor(Q256*theta^(-j/32)), computed by integer division of Q256^32 by theta^j, followed by five exact integer square roots. Phase is range-reduced by the pinned integer pi and evaluated with 128 signed Taylor recurrence steps for sin and cos. Final integers use nearest ties-to-even of the Q256 approximation. This is a deterministic specified approximation, not a theorem of correctly rounded transcendental arithmetic.

## Not covered

No private position lookup, multimodal unequal M-RoPE streams, YaRN, contexts above 1024, model weight/input provenance or composition with the q/k norm. No change to upstream's rotary served form. Text-only equal position streams are the scoped interpretation.

## Reproduce

Prefix proof batches with the shared heavy-job gate and <=6-core affinity:

```
python3 research/operators/qwen_ops/rotary_tables.py --check
python3 research/operators/qwen_ops/record.py all rotary
python3 research/operators/qwen_ops/record.py smoke rotary
python3 research/operators/qwen_ops/record.py ubsan rotary
python3 research/operators/qwen_ops/fidelity.py rotary
```

Fidelity compares 10 seeded positions/vectors per F against float trigonometry on dequantized identical inputs. The registered threshold (<=2*2^-F) nearly cannot fail, because each floor keeps the error under 2^-F by construction; it checks the implementation, not a fidelity margin. These are synthetic quantized-input measurements, not model fidelity. The reported error distribution covers only the 640 rotated output coordinates. The other 1920 coordinates are checked exactly unchanged and are not used to dilute the error quantiles. Receipts are in the experiment's `runs/rotary-*`.
