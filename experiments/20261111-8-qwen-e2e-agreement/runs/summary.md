# Summary (only the DeltaNet head computation is lowered; in_proj, out_proj, full attention, MLP, norms, final norm and lm_head are float64; no proof; arms are numerical lowerings, not sound relations)

Bars: top-1 >= 99%, KL median <= 0.0001 nats, KL max <= 0.1 nats, no guard error.
H1 (XS18 both): True | H2 (XS20 both): True

## stock
sanity p01 -> 25358 pass=True; deterministic=True; errors=0

| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | maxdiff/std median (max) | pass |
|---|---|---|---|---|---|---|---|---|
| XS18 | 1461 | 1460 (0.9993) | 3.16e-06 | 0.000426 | 0.00279 | 0.000149 | 0.0191 (3.56) | True |
| XS20 | 1461 | 1461 (1.0000) | 1.99e-06 | 0.000136 | 0.0024 | 0.000117 | 0.013 (3.45) | True |
| BF16H | 608 | 608 (1.0000) | 2.72e-05 | 0.0022 | 0.0057 | 0.00044 | 0.236 (3.76) | context only |

Per prompt (top-1 agree / T, KL median, KL max; local per-head rel_y > 0.05 count [layers]):

| prompt | T | XS18 agree | XS18 KL med | XS18 KL max | XS18 heads>0.05 | XS20 agree | XS20 KL med | XS20 KL max | XS20 heads>0.05 | BF16H KL max |
|---|---|---|---|---|---|---|---|---|---|---|
| p01-ordinary-short | 13 | 13 | 4.2e-07 | 4.87e-06 | 0 [] | 13 | 5.55e-07 | 3.43e-06 | 0 [] | 8.23e-06 |
| p07-chat-ordinary | 23 | 23 | 2.47e-09 | 0.00251 | 0 [] | 23 | 3.94e-09 | 0.000114 | 0 [] | 0.00141 |
| p08-chat-refusal | 39 | 39 | 3.23e-08 | 0.000268 | 0 [] | 39 | 4.38e-08 | 5.79e-05 | 0 [] | 0.00298 |
| p09-multilingual | 21 | 21 | 6.43e-07 | 5.56e-06 | 0 [] | 21 | 9.45e-07 | 3.61e-06 | 0 [] | 2.93e-05 |
| p02-ordinary-paragraph | 107 | 107 | 3.58e-06 | 0.000155 | 0 [] | 107 | 2.86e-06 | 0.000184 | 0 [] | - |
| p04-repeat-punct | 64 | 64 | 2.68e-07 | 0.002 | 11 [17, 25, 26] | 64 | 9.52e-08 | 9.71e-05 | 1 [17] | - |
| p05-code | 144 | 144 | 3.35e-08 | 5.66e-06 | 0 [] | 144 | 2.76e-08 | 5.28e-06 | 0 [] | - |
| p03-repeat-word | 512 | 512 | 4.35e-06 | 0.00279 | 138 [17, 18, 20, 21, 22, 24, 25, 26] | 512 | 2.91e-06 | 0.0024 | 20 [17, 18, 20, 22, 25, 26, 28, 29] | 0.0057 |
| p06a-digits-256 | 256 | 255 | 3.18e-06 | 0.000347 | 1 [17] | 256 | 1.39e-06 | 0.000112 | 0 [] | - |
| p11-chat-long | 282 | 282 | 9.67e-06 | 0.00107 | 0 [] | 282 | 4.2e-06 | 0.000346 | 0 [] | - |

XS18 top-1 flips: 1
- p06a-digits-256 pos 109: ref 19 -> 17, ref margin 0.00882, KL 5.84e-05

XS20 top-1 flips: 0

## abl
sanity p01 -> 25358 pass=True; deterministic=True; errors=0

| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | maxdiff/std median (max) | pass |
|---|---|---|---|---|---|---|---|---|
| XS18 | 1461 | 1460 (0.9993) | 2.95e-06 | 0.000347 | 0.00566 | 0.000215 | 0.0193 (3.17) | True |
| XS20 | 1461 | 1460 (0.9993) | 1.95e-06 | 0.000153 | 0.00294 | 0.000139 | 0.0128 (3.9) | True |
| BF16H | 608 | 608 (1.0000) | 1.86e-05 | 0.00221 | 0.00834 | 0.000597 | 0.238 (4.08) | context only |

Per prompt (top-1 agree / T, KL median, KL max; local per-head rel_y > 0.05 count [layers]):

| prompt | T | XS18 agree | XS18 KL med | XS18 KL max | XS18 heads>0.05 | XS20 agree | XS20 KL med | XS20 KL max | XS20 heads>0.05 | BF16H KL max |
|---|---|---|---|---|---|---|---|---|---|---|
| p01-ordinary-short | 13 | 13 | 4.32e-07 | 4.15e-06 | 0 [] | 13 | 5.63e-07 | 3.61e-06 | 0 [] | 9.68e-06 |
| p07-chat-ordinary | 23 | 23 | 4.75e-09 | 0.00133 | 0 [] | 23 | 2.39e-09 | 6.02e-05 | 0 [] | 0.000732 |
| p08-chat-refusal | 39 | 39 | 1.02e-07 | 4.17e-06 | 0 [] | 39 | 5.55e-08 | 0.000129 | 0 [] | 0.000191 |
| p09-multilingual | 21 | 21 | 1.14e-06 | 6.86e-06 | 0 [] | 21 | 7.3e-07 | 5.22e-06 | 0 [] | 3.64e-05 |
| p02-ordinary-paragraph | 107 | 107 | 4.03e-06 | 0.000132 | 0 [] | 107 | 3.48e-06 | 0.000153 | 0 [] | - |
| p04-repeat-punct | 64 | 64 | 2.29e-07 | 1.07e-05 | 46 [0, 2, 4, 5, 6, 9, 10, 12] | 64 | 1.03e-07 | 2.32e-06 | 6 [0, 2, 4, 17] | - |
| p05-code | 144 | 144 | 3.51e-08 | 4.74e-06 | 0 [] | 144 | 2.86e-08 | 4.93e-06 | 0 [] | - |
| p03-repeat-word | 512 | 512 | 4.01e-06 | 0.00566 | 352 [0, 1, 2, 4, 5, 6, 8, 9] | 512 | 3.2e-06 | 0.00294 | 77 [0, 1, 2, 4, 5, 6, 8, 9] | 0.00834 |
| p06a-digits-256 | 256 | 255 | 2.72e-06 | 0.000115 | 6 [0, 17] | 255 | 1.27e-06 | 3.89e-05 | 4 [0] | - |
| p11-chat-long | 282 | 282 | 6.16e-06 | 0.00231 | 0 [] | 282 | 5.68e-06 | 0.000237 | 0 [] | - |

XS18 top-1 flips: 1
- p06a-digits-256 pos 81: ref 16 -> 18, ref margin 0.00181, KL 8.78e-06

XS20 top-1 flips: 1
- p06a-digits-256 pos 81: ref 16 -> 18, ref margin 0.00181, KL 7.02e-06

