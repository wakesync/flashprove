# Summary (integer M3 MLP (DESIGN 5.5, r2) in every layer for FM, XM18; DeltaNet heads XS18 in XM18, float64 in REF and FM; in_proj, out_proj, attention, every RMSNorm (incl. the MLP pre-norm), final norm and lm_head float64; no proof)

Bars: top-1 >= 99%, KL median <= 0.0001 nats, KL max <= 0.1 nats, no guard error.

## abl
prompts 10; sanity p01 -> 25358 pass=True; deterministic=True; errors=0

| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | maxdiff/std median (max) | bar |
|---|---|---|---|---|---|---|---|---|
| XM18 | 1461 | 1423 (0.9740) | 0.00159 | 0.101 | 1.92 | 0.0707 | 1.09 (8.66) | False |
| FM | 1461 | 1422 (0.9733) | 0.0016 | 0.101 | 1.92 | 0.0705 | 1.1 (8.67) | descriptive False |
| XS18 only (PR #124 committed run, same prompts) | 1461 | 1460 | 2.95e-06 | - | 0.00566 | - | - | cited |

REF top-1 equal to PR #124's committed REF on every prompt: True

| prompt | T | XM18 agree | XM18 KL med | XM18 KL max | FM agree | FM KL med | FM KL max | XM18 resid rel (final) |
|---|---|---|---|---|---|---|---|---|
| p01-ordinary-short | 13 | 12 | 0.0268 | 0.353 | 12 | 0.0267 | 0.353 | 0.158 |
| p07-chat-ordinary | 23 | 22 | 0.00033 | 0.035 | 22 | 0.000314 | 0.0297 | 0.242 |
| p08-chat-refusal | 39 | 37 | 0.000357 | 1.66 | 37 | 0.000309 | 1.65 | 0.175 |
| p09-multilingual | 21 | 19 | 0.0177 | 0.128 | 19 | 0.0176 | 0.129 | 0.127 |
| p02-ordinary-paragraph | 107 | 96 | 0.00614 | 0.0808 | 96 | 0.00613 | 0.0808 | 0.14 |
| p04-repeat-punct | 64 | 64 | 0.0111 | 0.238 | 64 | 0.0111 | 0.236 | 0.232 |
| p05-code | 144 | 143 | 0.000479 | 0.101 | 143 | 0.000463 | 0.101 | 0.143 |
| p03-repeat-word | 512 | 511 | 0.000306 | 0.264 | 511 | 0.000335 | 0.263 | 0.182 |
| p06a-digits-256 | 256 | 247 | 0.00836 | 0.0931 | 247 | 0.00834 | 0.0956 | 0.185 |
| p11-chat-long | 282 | 272 | 0.00232 | 1.92 | 271 | 0.00242 | 1.92 | 0.123 |

XM18 top-1 flips: 38
- p01-ordinary-short pos 10: ref 9564 -> 279, ref margin 0.302, KL 0.0877
- p07-chat-ordinary pos 2: ref 2523 -> 1, ref margin 0.0775, KL 0.0219
- p08-chat-refusal pos 2: ref 2523 -> 1, ref margin 0.0775, KL 0.0219
- p08-chat-refusal pos 35: ref 198 -> 248068, ref margin 0.787, KL 1.66
- p09-multilingual pos 5: ref 112869 -> 97198, ref margin 0.0313, KL 0.0157
- p09-multilingual pos 20: ref 220 -> 271, ref margin 0.278, KL 0.0335
- p02-ordinary-paragraph pos 4: ref 1007 -> 1834, ref margin 0.0991, KL 0.0238
- p02-ordinary-paragraph pos 10: ref 2197 -> 995, ref margin 0.162, KL 0.0167
- p02-ordinary-paragraph pos 12: ref 7548 -> 4688, ref margin 0.205, KL 0.0517
- p02-ordinary-paragraph pos 26: ref 2250 -> 1330, ref margin 0.00459, KL 0.00155
- p02-ordinary-paragraph pos 39: ref 2812 -> 2463, ref margin 0.0413, KL 0.0198
- p02-ordinary-paragraph pos 42: ref 17198 -> 35600, ref margin 0.0711, KL 0.00617
- p02-ordinary-paragraph pos 45: ref 73582 -> 1142, ref margin 0.173, KL 0.012
- p02-ordinary-paragraph pos 62: ref 6695 -> 5307, ref margin 0.202, KL 0.00943
- p02-ordinary-paragraph pos 73: ref 5632 -> 3114, ref margin 0.0703, KL 0.0042
- p02-ordinary-paragraph pos 98: ref 9939 -> 852, ref margin 0.0427, KL 0.00867
- p02-ordinary-paragraph pos 103: ref 998 -> 1467, ref margin 0.119, KL 0.0103
- p05-code pos 1: ref 17885 -> 9927, ref margin 0.43, KL 0.101
- p03-repeat-word pos 1: ref 271 -> 198, ref margin 0.144, KL 0.155
- p06a-digits-256 pos 8: ref 220 -> 15, ref margin 0.478, KL 0.051
- p06a-digits-256 pos 114: ref 15 -> 17, ref margin 0.000767, KL 0.0117
- p06a-digits-256 pos 145: ref 15 -> 16, ref margin 0.016, KL 0.00292
- p06a-digits-256 pos 161: ref 19 -> 17, ref margin 0.00477, KL 0.00441
- p06a-digits-256 pos 168: ref 15 -> 17, ref margin 0.015, KL 0.00549
- p06a-digits-256 pos 172: ref 24 -> 19, ref margin 0.00724, KL 0.00157
- p06a-digits-256 pos 181: ref 220 -> 15, ref margin 0.0643, KL 0.06
- p06a-digits-256 pos 192: ref 19 -> 17, ref margin 0.0209, KL 0.00263
- p06a-digits-256 pos 207: ref 19 -> 17, ref margin 0.0242, KL 0.00109
- p11-chat-long pos 2: ref 2523 -> 1, ref margin 0.0775, KL 0.0219
- p11-chat-long pos 9: ref 248046 -> 220, ref margin 2.9, KL 1.92
- p11-chat-long pos 31: ref 8129 -> 6891, ref margin 0.127, KL 0.0104
- p11-chat-long pos 48: ref 20 -> 19, ref margin 0.105, KL 0.00546
- p11-chat-long pos 98: ref 248046 -> 264, ref margin 0.0476, KL 0.00291
- p11-chat-long pos 108: ref 13071 -> 338, ref margin 0.13, KL 0.0111
- p11-chat-long pos 147: ref 17 -> 248046, ref margin 0.133, KL 0.00666
- p11-chat-long pos 161: ref 32878 -> 6365, ref margin 0.0631, KL 0.0505
- p11-chat-long pos 163: ref 6365 -> 248046, ref margin 0.515, KL 0.0459
- p11-chat-long pos 174: ref 248046 -> 264, ref margin 0.217, KL 0.0139

FM top-1 flips: 39
- p01-ordinary-short pos 10: ref 9564 -> 279, ref margin 0.302, KL 0.088
- p07-chat-ordinary pos 2: ref 2523 -> 1, ref margin 0.0775, KL 0.0219
- p08-chat-refusal pos 2: ref 2523 -> 1, ref margin 0.0775, KL 0.0219
- p08-chat-refusal pos 35: ref 198 -> 248068, ref margin 0.787, KL 1.65
- p09-multilingual pos 5: ref 112869 -> 97198, ref margin 0.0313, KL 0.0157
- p09-multilingual pos 20: ref 220 -> 271, ref margin 0.278, KL 0.0334
- p02-ordinary-paragraph pos 4: ref 1007 -> 1834, ref margin 0.0991, KL 0.0243
- p02-ordinary-paragraph pos 10: ref 2197 -> 995, ref margin 0.162, KL 0.0172
- p02-ordinary-paragraph pos 12: ref 7548 -> 4688, ref margin 0.205, KL 0.0514
- p02-ordinary-paragraph pos 26: ref 2250 -> 1330, ref margin 0.00459, KL 0.00161
- p02-ordinary-paragraph pos 39: ref 2812 -> 2463, ref margin 0.0413, KL 0.0204
- p02-ordinary-paragraph pos 42: ref 17198 -> 35600, ref margin 0.0711, KL 0.00647
- p02-ordinary-paragraph pos 45: ref 73582 -> 1142, ref margin 0.173, KL 0.0116
- p02-ordinary-paragraph pos 62: ref 6695 -> 5307, ref margin 0.202, KL 0.00944
- p02-ordinary-paragraph pos 73: ref 5632 -> 3114, ref margin 0.0703, KL 0.00406
- p02-ordinary-paragraph pos 98: ref 9939 -> 852, ref margin 0.0427, KL 0.00855
- p02-ordinary-paragraph pos 103: ref 998 -> 1467, ref margin 0.119, KL 0.0104
- p05-code pos 1: ref 17885 -> 9927, ref margin 0.43, KL 0.101
- p03-repeat-word pos 1: ref 271 -> 198, ref margin 0.144, KL 0.154
- p06a-digits-256 pos 8: ref 220 -> 15, ref margin 0.478, KL 0.0505
- p06a-digits-256 pos 114: ref 15 -> 17, ref margin 0.000767, KL 0.0119
- p06a-digits-256 pos 145: ref 15 -> 16, ref margin 0.016, KL 0.00291
- p06a-digits-256 pos 161: ref 19 -> 17, ref margin 0.00477, KL 0.00423
- p06a-digits-256 pos 168: ref 15 -> 17, ref margin 0.015, KL 0.00552
- p06a-digits-256 pos 172: ref 24 -> 19, ref margin 0.00724, KL 0.00158
- p06a-digits-256 pos 181: ref 220 -> 15, ref margin 0.0643, KL 0.0605
- p06a-digits-256 pos 192: ref 19 -> 17, ref margin 0.0209, KL 0.00257
- p06a-digits-256 pos 207: ref 19 -> 17, ref margin 0.0242, KL 0.00112
- p11-chat-long pos 2: ref 2523 -> 1, ref margin 0.0775, KL 0.0219
- p11-chat-long pos 9: ref 248046 -> 220, ref margin 2.9, KL 1.92
- p11-chat-long pos 31: ref 8129 -> 6891, ref margin 0.127, KL 0.00992
- p11-chat-long pos 48: ref 20 -> 19, ref margin 0.105, KL 0.00529
- p11-chat-long pos 98: ref 248046 -> 264, ref margin 0.0476, KL 0.00235
- p11-chat-long pos 108: ref 13071 -> 338, ref margin 0.13, KL 0.0106
- p11-chat-long pos 147: ref 17 -> 248046, ref margin 0.133, KL 0.00758
- p11-chat-long pos 161: ref 32878 -> 6365, ref margin 0.0631, KL 0.0483
- p11-chat-long pos 163: ref 6365 -> 248046, ref margin 0.515, KL 0.0476
- p11-chat-long pos 165: ref 1521 -> 248046, ref margin 0.0483, KL 0.00917
- p11-chat-long pos 174: ref 248046 -> 264, ref margin 0.217, KL 0.0133

### ranges (abl leg, layers in ranges-abl.jsonl); verdict OUT-OF-BOUND, XM18 class events 101748516
weight exponents 11..14, all in 1..24: True, all |W| <= 4095: True

| path | quantity | max abs | log2 | layer | prompt | bound | counts |
|---|---|---|---|---|---|---|---|
| XM18 | m | 235253 | 17.84 | 63 | p03-repeat-word | |m| <= 2,047 (DESIGN 3.2, A_PUB) | n_m_over_2047 101566552 (layers [31, 32, 33, 34, 35, 36, 37, 38, 39, 40]) |
| XM18 | gw | 236620 | 17.85 | 62 | p11-chat-long | honest < 2^18, rng < 2^23; SiLU domain [-2^15, 2^15) | n_gw_ge_2e18 0 (layers []), n_gw_ge_2e23 0 (layers []), n_silu_sat_lo 28771 (layers [34, 36, 43, 44, 45, 48, 49, 50, 51, 52]), n_silu_sat_hi 153193 (layers [36, 37, 38, 39, 40, 42, 43, 44, 45, 46]) |
| XM18 | u | 248495 | 17.92 | 63 | p06a-digits-256 | honest < 2^18, rng < 2^23 | n_u_ge_2e18 0 (layers []), n_u_ge_2e23 0 (layers []) |
| XM18 | s | 32741 | 15 | 36 | p05-code | |s| <= 32,741 (table image) |  |
| XM18 | h | 1.16775e+06 | 20.16 | 62 | p11-chat-long | honest < 2^18, rng < 2^23 | n_h_ge_2e18 622 (layers [52, 53, 54, 56, 57, 58, 59, 60, 61, 62]), n_h_ge_2e23 0 (layers []) |
| XM18 | acc_down | 8.75169e+09 | 33.03 | 63 | p06a-digits-256 | ledger 2^55.02 (bounds-r3 'M3a-MLP down (r2)'); float guard 2^53 | n_acc_down_ge_ledger 0 (layers []) |
| XM18 | out | 2.13664e+06 | 21.03 | 63 | p06a-digits-256 | |out| < 2^31 (DESIGN 3.2, OUT_PUB) | n_out_ge_2e31 0 (layers []) |
| FM | m | 235668 | 17.85 | 63 | p03-repeat-word | |m| <= 2,047 (DESIGN 3.2, A_PUB) | n_m_over_2047 101560960 (layers [31, 32, 33, 34, 35, 36, 37, 38, 39, 40]) |
| FM | gw | 236631 | 17.85 | 62 | p11-chat-long | honest < 2^18, rng < 2^23; SiLU domain [-2^15, 2^15) | n_gw_ge_2e18 0 (layers []), n_gw_ge_2e23 0 (layers []), n_silu_sat_lo 28912 (layers [34, 36, 43, 44, 45, 48, 49, 50, 51, 52]), n_silu_sat_hi 152921 (layers [36, 37, 38, 39, 40, 42, 43, 44, 45, 46]) |
| FM | u | 248857 | 17.92 | 63 | p06a-digits-256 | honest < 2^18, rng < 2^23 | n_u_ge_2e18 0 (layers []), n_u_ge_2e23 0 (layers []) |
| FM | s | 32741 | 15 | 36 | p05-code | |s| <= 32,741 (table image) |  |
| FM | h | 1.16771e+06 | 20.16 | 62 | p11-chat-long | honest < 2^18, rng < 2^23 | n_h_ge_2e18 634 (layers [52, 53, 54, 56, 57, 58, 59, 60, 61, 62]), n_h_ge_2e23 0 (layers []) |
| FM | acc_down | 8.75834e+09 | 33.03 | 63 | p06a-digits-256 | ledger 2^55.02 (bounds-r3 'M3a-MLP down (r2)'); float guard 2^53 | n_acc_down_ge_ledger 0 (layers []) |
| FM | out | 2.13827e+06 | 21.03 | 63 | p06a-digits-256 | |out| < 2^31 (DESIGN 3.2, OUT_PUB) | n_out_ge_2e31 0 (layers []) |

## stock
logits not finished


