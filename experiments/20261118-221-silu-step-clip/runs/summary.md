# Summary: SiLU table step vs domain clip, abliterated layers 31-63 (measured, unreplicated)

Prompt set: all10 (1461 positions); timing probe t_lin 35.62 s, t_full 38.74 s, projected (10 prompts) 3584.1 s, available 5882.8 s.

Layers done: 31..63 (33); logits finished: True; M31-C#2 residual bit-equal every layer: True; guard errors: 0

Gates: G1 REF top-1 = PR #173 on every prompt: True; G2 M31-C#2 bit-equal to M31-C (residual + logits): True; G3 no guard error in M31-C/M31-T: True. Valid: True. Sanity p01 Tokyo: True

| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | flips | bar (descriptive) |
|---|---|---|---|---|---|---|---|---|
| M31-C | 1461 | 1459 (0.9986) | 2.06e-06 | 0.000329 | 0.00215 | 0.000129 | 2 | top1 True, KLmed True, KLmax True |
| M31-T | 1461 | 1424 (0.9747) | 0.00146 | 0.104 | 1.93 | 0.0699 | 37 | top1 False, KLmed False, KLmax False |
| M31, PR #202 (cited) | 1461 | 1423 | 0.00147 | - | 1.93 | - | - | - |
| M31-S, PR #202 (cited) | 1461 | 1460 | 1.83e-06 | - | 0.00157 | - | - | - |

| hypothesis | path | KL median | M31 KL median (PR #202, committed) | ratio | threshold | verdict |
|---|---|---|---|---|---|---|
| H-C | M31-C | 2.064e-06 | 0.001466 | 0.001408 | <= 0.5 | HOLDS |
| H-T | M31-T | 0.001458 | 0.001466 | 0.9948 | <= 0.5 | DOES NOT HOLD |

Registered outcome: H-C only: the clip carries the token error; the step alone does not halve it.

| prompt | T | M31-C agree | M31-C KL med | M31-C KL max | M31-T agree | M31-T KL med | M31-T KL max |
|---|---|---|---|---|---|---|---|
| p01-ordinary-short | 13 | 13 | 1.68e-05 | 4.01e-05 | 12 | 0.0264 | 0.354 |
| p07-chat-ordinary | 23 | 23 | 8.59e-08 | 0.000114 | 22 | 0.000324 | 0.111 |
| p08-chat-refusal | 39 | 39 | 2.47e-06 | 0.00212 | 37 | 0.000351 | 1.59 |
| p09-multilingual | 21 | 21 | 4.05e-05 | 0.000196 | 19 | 0.0173 | 0.132 |
| p02-ordinary-paragraph | 107 | 107 | 3.11e-05 | 0.000161 | 96 | 0.00606 | 0.0808 |
| p04-repeat-punct | 64 | 64 | 3.12e-06 | 4.16e-05 | 64 | 0.011 | 0.236 |
| p05-code | 144 | 144 | 4.74e-07 | 4.55e-05 | 142 | 0.000462 | 0.1 |
| p03-repeat-word | 512 | 512 | 1.04e-07 | 4.53e-05 | 511 | 0.000406 | 0.271 |
| p06a-digits-256 | 256 | 255 | 7.33e-06 | 0.000201 | 247 | 0.00854 | 0.0818 |
| p11-chat-long | 282 | 281 | 3.15e-05 | 0.00215 | 274 | 0.00226 | 1.93 |

M31-C top-1 flips: 2 (REF margin median 0.0363, min 0.00954, max 0.0631)
- p06a-digits-256 pos 101: ref 23 -> 21, REF margin 0.00954, KL 6.07e-05
- p11-chat-long pos 161: ref 32878 -> 6365, REF margin 0.0631, KL 0.00113

M31-T top-1 flips: 37 (REF margin median 0.0775, min 0.000767, max 2.9)
- p01-ordinary-short pos 10: ref 9564 -> 279, REF margin 0.302, KL 0.0863
- p07-chat-ordinary pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.0219
- p08-chat-refusal pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.0219
- p08-chat-refusal pos 35: ref 198 -> 248068, REF margin 0.787, KL 1.59
- p09-multilingual pos 5: ref 112869 -> 97198, REF margin 0.0313, KL 0.0156
- p09-multilingual pos 20: ref 220 -> 271, REF margin 0.278, KL 0.0342
- p02-ordinary-paragraph pos 4: ref 1007 -> 1834, REF margin 0.0991, KL 0.0243
- p02-ordinary-paragraph pos 10: ref 2197 -> 995, REF margin 0.162, KL 0.0172
- p02-ordinary-paragraph pos 12: ref 7548 -> 4688, REF margin 0.205, KL 0.055
- p02-ordinary-paragraph pos 26: ref 2250 -> 1330, REF margin 0.00459, KL 0.00157
- p02-ordinary-paragraph pos 39: ref 2812 -> 2463, REF margin 0.0413, KL 0.0192
- p02-ordinary-paragraph pos 42: ref 17198 -> 35600, REF margin 0.0711, KL 0.00682
- p02-ordinary-paragraph pos 45: ref 73582 -> 1142, REF margin 0.173, KL 0.0126
- p02-ordinary-paragraph pos 62: ref 6695 -> 5307, REF margin 0.202, KL 0.00892
- p02-ordinary-paragraph pos 73: ref 5632 -> 3114, REF margin 0.0703, KL 0.00419
- p02-ordinary-paragraph pos 98: ref 9939 -> 852, REF margin 0.0427, KL 0.00769
- p02-ordinary-paragraph pos 103: ref 998 -> 1467, REF margin 0.119, KL 0.00954
- p05-code pos 1: ref 17885 -> 9927, REF margin 0.43, KL 0.1
- p05-code pos 109: ref 12880 -> 11768, REF margin 0.036, KL 0.000638
- p03-repeat-word pos 1: ref 271 -> 198, REF margin 0.144, KL 0.154
- p06a-digits-256 pos 8: ref 220 -> 15, REF margin 0.478, KL 0.0503
- p06a-digits-256 pos 114: ref 15 -> 17, REF margin 0.000767, KL 0.0118
- p06a-digits-256 pos 145: ref 15 -> 16, REF margin 0.016, KL 0.00305
- p06a-digits-256 pos 161: ref 19 -> 17, REF margin 0.00477, KL 0.00417
- p06a-digits-256 pos 168: ref 15 -> 17, REF margin 0.015, KL 0.00557
- p06a-digits-256 pos 172: ref 24 -> 19, REF margin 0.00724, KL 0.00158
- p06a-digits-256 pos 181: ref 220 -> 15, REF margin 0.0643, KL 0.0624
- p06a-digits-256 pos 192: ref 19 -> 17, REF margin 0.0209, KL 0.00262
- p06a-digits-256 pos 207: ref 19 -> 17, REF margin 0.0242, KL 0.0012
- p11-chat-long pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.0219
- p11-chat-long pos 9: ref 248046 -> 220, REF margin 2.9, KL 1.93
- p11-chat-long pos 31: ref 8129 -> 6891, REF margin 0.127, KL 0.0106
- p11-chat-long pos 48: ref 20 -> 19, REF margin 0.105, KL 0.00547
- p11-chat-long pos 98: ref 248046 -> 264, REF margin 0.0476, KL 0.00169
- p11-chat-long pos 108: ref 13071 -> 338, REF margin 0.13, KL 0.00912
- p11-chat-long pos 163: ref 6365 -> 248046, REF margin 0.515, KL 0.0478
- p11-chat-long pos 174: ref 248046 -> 264, REF margin 0.217, KL 0.0125

## Range counters, layers done (totals over prompts and layers)

| path | SiLU exits lo | SiLU exits hi | h >= 2^18 | h >= 2^23 | m > 2047 | gw >= 2^18 | u >= 2^18 | max h (log2) | max acc_down (log2) | max out (log2) |
|---|---|---|---|---|---|---|---|---|---|---|
| M31-C | 27734 | 152988 | 2543 | 0 | 101561117 | 0 | 0 | 20.77 | 33.59 | 21.59 |
| M31-T | 28997 | 153385 | 635 | 0 | 101734806 | 0 | 0 | 20.15 | 33.03 | 21.03 |
| M31-C#2 | 521 | 3733 | 41 | 0 | 2564268 | 0 | 0 | 20.54 | 32.74 | 20.74 |
| M31, PR #202 (cited) | 28918 | 153356 | 632 | - | - | - | - | - | - | - |
| M31-S, PR #202 (cited) | 27801 | 152997 | 2541 | - | - | - | - | - | - | - |

(Domain exits are counted on each arm's own trajectory. M31-C replaces them by exact SiLU; M31-T holds them at the domain edge.)

## Per layer: seconds, median residual rel L2 vs REF over prompts, domain exits (lo/hi) and h >= 2^18 per arm

| layer | s | M31-C rel | M31-C exits lo/hi | M31-C h>=2^18 | M31-T rel | M31-T exits lo/hi | M31-T h>=2^18 |
|---|---|---|---|---|---|---|---|
| 31 | 125.3 | 0.00118 | 0/0 | 0 | 0.000952 | 0/0 | 0 |
| 32 | 183.1 | 0.00176 | 0/0 | 0 | 0.00143 | 0/0 | 0 |
| 33 | 173.3 | 0.00198 | 0/0 | 0 | 0.00157 | 0/0 | 0 |
| 34 | 182.9 | 0.00235 | 55/0 | 0 | 0.00196 | 55/0 | 0 |
| 35 | 173.8 | 0.00277 | 0/0 | 0 | 0.00234 | 0/0 | 0 |
| 36 | 151.4 | 0.00286 | 4/1 | 0 | 0.00236 | 4/1 | 0 |
| 37 | 166.3 | 0.00294 | 0/1 | 0 | 0.00235 | 0/1 | 0 |
| 38 | 163.9 | 0.00297 | 0/1 | 0 | 0.00244 | 0/1 | 0 |
| 39 | 164.0 | 0.00323 | 0/1 | 0 | 0.00261 | 0/1 | 0 |
| 40 | 158.8 | 0.0034 | 0/1 | 0 | 0.00272 | 0/1 | 0 |
| 41 | 156.8 | 0.00352 | 0/0 | 0 | 0.0029 | 0/0 | 0 |
| 42 | 151.0 | 0.00366 | 0/36 | 0 | 0.00448 | 0/36 | 0 |
| 43 | 168.6 | 0.00379 | 48/4 | 0 | 0.00459 | 48/4 | 0 |
| 44 | 150.5 | 0.00382 | 40/24 | 0 | 0.00479 | 40/22 | 0 |
| 45 | 144.1 | 0.00392 | 3/2 | 0 | 0.00468 | 3/2 | 0 |
| 46 | 116.6 | 0.00406 | 0/26 | 0 | 0.00575 | 0/26 | 0 |
| 47 | 119.6 | 0.00447 | 0/0 | 0 | 0.0055 | 0/0 | 0 |
| 48 | 121.5 | 0.0048 | 3/85 | 0 | 0.00523 | 4/86 | 0 |
| 49 | 134.5 | 0.00507 | 10/4 | 0 | 0.00537 | 10/4 | 0 |
| 50 | 132.3 | 0.00484 | 323/146 | 0 | 0.00793 | 324/145 | 0 |
| 51 | 137.7 | 0.00541 | 48/45 | 0 | 0.00802 | 49/42 | 0 |
| 52 | 133.4 | 0.00549 | 260/141 | 1 | 0.00872 | 264/141 | 1 |
| 53 | 127.5 | 0.00565 | 392/118 | 33 | 0.0104 | 394/118 | 1 |
| 54 | 134.5 | 0.00525 | 1552/624 | 80 | 0.0827 | 1567/621 | 54 |
| 55 | 129.9 | 0.00569 | 235/175 | 5 | 0.0672 | 239/174 | 0 |
| 56 | 134.2 | 0.00575 | 173/150 | 7 | 0.0562 | 192/144 | 1 |
| 57 | 135.9 | 0.00585 | 182/222 | 14 | 0.0572 | 179/225 | 9 |
| 58 | 131.7 | 0.00567 | 486/1912 | 135 | 0.122 | 483/1898 | 62 |
| 59 | 134.7 | 0.0061 | 808/1738 | 52 | 0.0731 | 858/1756 | 27 |
| 60 | 128.5 | 0.00653 | 2589/806 | 17 | 0.0696 | 2689/842 | 13 |
| 61 | 127.1 | 0.00668 | 3937/2838 | 23 | 0.071 | 4066/2754 | 14 |
| 62 | 125.7 | 0.00712 | 7419/9887 | 123 | 0.0824 | 7927/10059 | 93 |
| 63 | 139.6 | 0.00623 | 9167/134000 | 2053 | 0.151 | 9602/134281 | 360 |
