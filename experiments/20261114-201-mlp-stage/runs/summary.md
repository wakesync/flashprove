# Summary: MLP stage attribution, abliterated layers 31-63 (measured, unreplicated)

Prompt set: all10 (1461 positions); timing probe t_lin 53.0 s, t_full 54.16 s, projected (10 prompts) 5170.8 s, available 5850.6 s.

Layers done: 31..63 (33); logits finished: True; M31#2 residual bit-equal every layer: True; guard errors: 0

Gates: G1 REF top-1 = PR #173 on every prompt: True; G2 M31#2 bit-equal (residual + logits): True; G3 no guard error in M31/M31-S: True. Valid: True. Sanity p01 Tokyo: True

| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | flips | bar (descriptive) |
|---|---|---|---|---|---|---|---|---|
| M31 | 1461 | 1423 (0.9740) | 0.00147 | 0.103 | 1.93 | 0.0706 | 38 | top1 False, KLmed False, KLmax False |
| M31-S | 1461 | 1460 (0.9993) | 1.83e-06 | 0.000354 | 0.00157 | 8.47e-05 | 1 | top1 True, KLmed True, KLmax True |
| M31-W | 1461 | 1422 (0.9733) | 0.00145 | 0.0998 | 1.94 | 0.0699 | 39 | top1 False, KLmed False, KLmax False |
| FM, PR #173 (layers 0-63, cited) | 1461 | 1422 | 0.0016 | - | 1.92 | - | - | - |

| hypothesis | path | KL median | M31 KL median | ratio | threshold | verdict |
|---|---|---|---|---|---|---|
| H-S | M31-S | 1.831e-06 | 0.001466 | 0.001249 | <= 0.5 | HOLDS |
| H-W | M31-W | 0.001454 | 0.001466 | 0.9917 | <= 0.5 | DOES NOT HOLD |

| prompt | T | M31 agree | M31 KL med | M31 KL max | M31-S agree | M31-S KL med | M31-S KL max | M31-W agree | M31-W KL med | M31-W KL max |
|---|---|---|---|---|---|---|---|---|---|---|
| p01-ordinary-short | 13 | 12 | 0.0267 | 0.354 | 13 | 1.77e-05 | 3.72e-05 | 12 | 0.0265 | 0.355 |
| p07-chat-ordinary | 23 | 22 | 0.000275 | 0.106 | 23 | 1.51e-07 | 0.000754 | 22 | 0.000271 | 0.0926 |
| p08-chat-refusal | 39 | 37 | 0.00036 | 1.63 | 39 | 2.21e-06 | 0.000339 | 37 | 0.000392 | 1.58 |
| p09-multilingual | 21 | 19 | 0.0173 | 0.133 | 21 | 3.23e-05 | 0.00012 | 19 | 0.0165 | 0.134 |
| p02-ordinary-paragraph | 107 | 96 | 0.00597 | 0.0809 | 107 | 1.82e-05 | 0.000142 | 96 | 0.0059 | 0.0816 |
| p04-repeat-punct | 64 | 64 | 0.0111 | 0.236 | 64 | 3.54e-06 | 3.61e-05 | 64 | 0.011 | 0.236 |
| p05-code | 144 | 142 | 0.000474 | 0.101 | 144 | 3.11e-07 | 3.44e-05 | 142 | 0.00047 | 0.0998 |
| p03-repeat-word | 512 | 511 | 0.000412 | 0.274 | 512 | 1.09e-07 | 3.94e-05 | 511 | 0.000407 | 0.276 |
| p06a-digits-256 | 256 | 246 | 0.00839 | 0.0831 | 256 | 6.07e-06 | 0.000187 | 246 | 0.00845 | 0.0817 |
| p11-chat-long | 282 | 274 | 0.00235 | 1.93 | 281 | 3e-05 | 0.00157 | 273 | 0.00226 | 1.94 |

M31 top-1 flips: 38 (REF margin median 0.0775, min 0.000767, max 2.9)
- p01-ordinary-short pos 10: ref 9564 -> 279, REF margin 0.302, KL 0.0866
- p07-chat-ordinary pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.022
- p08-chat-refusal pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.022
- p08-chat-refusal pos 35: ref 198 -> 248068, REF margin 0.787, KL 1.63
- p09-multilingual pos 5: ref 112869 -> 97198, REF margin 0.0313, KL 0.0154
- p09-multilingual pos 20: ref 220 -> 271, REF margin 0.278, KL 0.0346
- p02-ordinary-paragraph pos 4: ref 1007 -> 1834, REF margin 0.0991, KL 0.0243
- p02-ordinary-paragraph pos 10: ref 2197 -> 995, REF margin 0.162, KL 0.0169
- p02-ordinary-paragraph pos 12: ref 7548 -> 4688, REF margin 0.205, KL 0.0541
- p02-ordinary-paragraph pos 26: ref 2250 -> 1330, REF margin 0.00459, KL 0.00165
- p02-ordinary-paragraph pos 39: ref 2812 -> 2463, REF margin 0.0413, KL 0.0193
- p02-ordinary-paragraph pos 42: ref 17198 -> 35600, REF margin 0.0711, KL 0.00672
- p02-ordinary-paragraph pos 45: ref 73582 -> 1142, REF margin 0.173, KL 0.012
- p02-ordinary-paragraph pos 62: ref 6695 -> 5307, REF margin 0.202, KL 0.00904
- p02-ordinary-paragraph pos 73: ref 5632 -> 3114, REF margin 0.0703, KL 0.00423
- p02-ordinary-paragraph pos 98: ref 9939 -> 852, REF margin 0.0427, KL 0.0074
- p02-ordinary-paragraph pos 103: ref 998 -> 1467, REF margin 0.119, KL 0.0106
- p05-code pos 1: ref 17885 -> 9927, REF margin 0.43, KL 0.101
- p05-code pos 109: ref 12880 -> 11768, REF margin 0.036, KL 0.000598
- p03-repeat-word pos 1: ref 271 -> 198, REF margin 0.144, KL 0.154
- p06a-digits-256 pos 8: ref 220 -> 15, REF margin 0.478, KL 0.051
- p06a-digits-256 pos 114: ref 15 -> 17, REF margin 0.000767, KL 0.0118
- p06a-digits-256 pos 133: ref 20 -> 23, REF margin 0.017, KL 0.00311
- p06a-digits-256 pos 145: ref 15 -> 16, REF margin 0.016, KL 0.00307
- p06a-digits-256 pos 161: ref 19 -> 17, REF margin 0.00477, KL 0.00417
- p06a-digits-256 pos 168: ref 15 -> 17, REF margin 0.015, KL 0.00557
- p06a-digits-256 pos 172: ref 24 -> 19, REF margin 0.00724, KL 0.00159
- p06a-digits-256 pos 181: ref 220 -> 15, REF margin 0.0643, KL 0.0627
- p06a-digits-256 pos 192: ref 19 -> 17, REF margin 0.0209, KL 0.00262
- p06a-digits-256 pos 207: ref 19 -> 17, REF margin 0.0242, KL 0.0012
- p11-chat-long pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.022
- p11-chat-long pos 9: ref 248046 -> 220, REF margin 2.9, KL 1.93
- p11-chat-long pos 31: ref 8129 -> 6891, REF margin 0.127, KL 0.0106
- p11-chat-long pos 48: ref 20 -> 19, REF margin 0.105, KL 0.00509
- p11-chat-long pos 98: ref 248046 -> 264, REF margin 0.0476, KL 0.00184
- p11-chat-long pos 108: ref 13071 -> 338, REF margin 0.13, KL 0.00926
- p11-chat-long pos 163: ref 6365 -> 248046, REF margin 0.515, KL 0.0485
- p11-chat-long pos 174: ref 248046 -> 264, REF margin 0.217, KL 0.0114

M31-S top-1 flips: 1 (REF margin median 0.0631, min 0.0631, max 0.0631)
- p11-chat-long pos 161: ref 32878 -> 6365, REF margin 0.0631, KL 0.000882

M31-W top-1 flips: 39 (REF margin median 0.0775, min 0.000767, max 2.9)
- p01-ordinary-short pos 10: ref 9564 -> 279, REF margin 0.302, KL 0.0888
- p07-chat-ordinary pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.0218
- p08-chat-refusal pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.0218
- p08-chat-refusal pos 35: ref 198 -> 248068, REF margin 0.787, KL 1.58
- p09-multilingual pos 5: ref 112869 -> 97198, REF margin 0.0313, KL 0.0154
- p09-multilingual pos 20: ref 220 -> 271, REF margin 0.278, KL 0.0343
- p02-ordinary-paragraph pos 4: ref 1007 -> 1834, REF margin 0.0991, KL 0.0242
- p02-ordinary-paragraph pos 10: ref 2197 -> 995, REF margin 0.162, KL 0.0172
- p02-ordinary-paragraph pos 12: ref 7548 -> 4688, REF margin 0.205, KL 0.0536
- p02-ordinary-paragraph pos 26: ref 2250 -> 1330, REF margin 0.00459, KL 0.00169
- p02-ordinary-paragraph pos 39: ref 2812 -> 2463, REF margin 0.0413, KL 0.019
- p02-ordinary-paragraph pos 42: ref 17198 -> 35600, REF margin 0.0711, KL 0.00735
- p02-ordinary-paragraph pos 45: ref 73582 -> 1142, REF margin 0.173, KL 0.0129
- p02-ordinary-paragraph pos 62: ref 6695 -> 5307, REF margin 0.202, KL 0.00835
- p02-ordinary-paragraph pos 73: ref 5632 -> 3114, REF margin 0.0703, KL 0.00438
- p02-ordinary-paragraph pos 98: ref 9939 -> 852, REF margin 0.0427, KL 0.00791
- p02-ordinary-paragraph pos 103: ref 998 -> 1467, REF margin 0.119, KL 0.0102
- p05-code pos 1: ref 17885 -> 9927, REF margin 0.43, KL 0.0998
- p05-code pos 109: ref 12880 -> 11768, REF margin 0.036, KL 0.000664
- p03-repeat-word pos 1: ref 271 -> 198, REF margin 0.144, KL 0.154
- p06a-digits-256 pos 8: ref 220 -> 15, REF margin 0.478, KL 0.0517
- p06a-digits-256 pos 114: ref 15 -> 17, REF margin 0.000767, KL 0.0119
- p06a-digits-256 pos 133: ref 20 -> 23, REF margin 0.017, KL 0.00287
- p06a-digits-256 pos 145: ref 15 -> 16, REF margin 0.016, KL 0.00317
- p06a-digits-256 pos 161: ref 19 -> 17, REF margin 0.00477, KL 0.00428
- p06a-digits-256 pos 168: ref 15 -> 17, REF margin 0.015, KL 0.00574
- p06a-digits-256 pos 172: ref 24 -> 19, REF margin 0.00724, KL 0.00162
- p06a-digits-256 pos 181: ref 220 -> 15, REF margin 0.0643, KL 0.0637
- p06a-digits-256 pos 192: ref 19 -> 17, REF margin 0.0209, KL 0.00268
- p06a-digits-256 pos 207: ref 19 -> 17, REF margin 0.0242, KL 0.00123
- p11-chat-long pos 2: ref 2523 -> 1, REF margin 0.0775, KL 0.0218
- p11-chat-long pos 9: ref 248046 -> 220, REF margin 2.9, KL 1.94
- p11-chat-long pos 31: ref 8129 -> 6891, REF margin 0.127, KL 0.0105
- p11-chat-long pos 48: ref 20 -> 19, REF margin 0.105, KL 0.00544
- p11-chat-long pos 98: ref 248046 -> 264, REF margin 0.0476, KL 0.00129
- p11-chat-long pos 108: ref 13071 -> 338, REF margin 0.13, KL 0.00934
- p11-chat-long pos 163: ref 6365 -> 248046, REF margin 0.515, KL 0.05
- p11-chat-long pos 165: ref 1521 -> 248046, REF margin 0.0483, KL 0.00281
- p11-chat-long pos 174: ref 248046 -> 264, REF margin 0.217, KL 0.0116

## Range counters, layers done (totals over prompts and layers)

| path | SiLU exits lo | SiLU exits hi | h >= 2^18 | h >= 2^23 | m > 2047 | gw >= 2^18 | u >= 2^18 | max h (log2) | max acc_down (log2) | max out (log2) |
|---|---|---|---|---|---|---|---|---|---|---|
| M31 | 28918 | 153356 | 632 | 0 | 101635217 | 0 | 0 | 20.15 | 33.03 | 21.03 |
| M31-S | 27801 | 152997 | 2541 | 0 | 101661026 | 0 | 0 | 20.77 | 33.59 | 21.59 |
| M31-W | 28946 | 153357 | 631 | 0 | 101630159 | 0 | 0 | 20.15 | 33.03 | 21.03 |
| M31#2 | 567 | 3764 | 15 | 0 | 2570869 | 0 | 0 | 18.91 | 31.77 | 19.77 |

(M31-S counts SiLU domain exits but does not saturate them; M31 and M31-W saturate.)

## Per layer: seconds, median residual rel L2 vs REF over prompts, SiLU exits and h >= 2^18 per path

| layer | s | M31 rel | M31 exits | M31 h>=2^18 | M31-S rel | M31-S exits | M31-S h>=2^18 | M31-W rel | M31-W exits | M31-W h>=2^18 |
|---|---|---|---|---|---|---|---|---|---|---|
| 31 | 195.2 | 0.00118 | 0 | 0 | 0.000952 | 0 | 0 | 0.000709 | 0 | 0 |
| 32 | 179.9 | 0.00176 | 0 | 0 | 0.00143 | 0 | 0 | 0.00104 | 0 | 0 |
| 33 | 158.2 | 0.00198 | 0 | 0 | 0.00157 | 0 | 0 | 0.00125 | 0 | 0 |
| 34 | 139.2 | 0.00235 | 55 | 0 | 0.00196 | 55 | 0 | 0.00139 | 55 | 0 |
| 35 | 170.3 | 0.00277 | 0 | 0 | 0.00234 | 0 | 0 | 0.00158 | 0 | 0 |
| 36 | 171.6 | 0.00286 | 5 | 0 | 0.00236 | 5 | 0 | 0.00172 | 5 | 0 |
| 37 | 166.3 | 0.00296 | 1 | 0 | 0.00233 | 1 | 0 | 0.00186 | 1 | 0 |
| 38 | 157.6 | 0.00298 | 1 | 0 | 0.00242 | 1 | 0 | 0.00182 | 1 | 0 |
| 39 | 161.9 | 0.00324 | 1 | 0 | 0.00259 | 1 | 0 | 0.00197 | 1 | 0 |
| 40 | 177.4 | 0.0034 | 1 | 0 | 0.00272 | 1 | 0 | 0.00204 | 1 | 0 |
| 41 | 163.5 | 0.00359 | 0 | 0 | 0.0029 | 0 | 0 | 0.00213 | 0 | 0 |
| 42 | 171.3 | 0.00493 | 36 | 0 | 0.00296 | 36 | 0 | 0.00402 | 36 | 0 |
| 43 | 181.6 | 0.00509 | 52 | 0 | 0.00316 | 52 | 0 | 0.00409 | 53 | 0 |
| 44 | 137.2 | 0.00529 | 62 | 0 | 0.00313 | 64 | 0 | 0.00435 | 63 | 0 |
| 45 | 123.8 | 0.00523 | 5 | 0 | 0.00312 | 5 | 0 | 0.0043 | 5 | 0 |
| 46 | 120.7 | 0.00634 | 26 | 0 | 0.00314 | 26 | 0 | 0.00543 | 26 | 0 |
| 47 | 147.1 | 0.00613 | 0 | 0 | 0.00343 | 0 | 0 | 0.00503 | 0 | 0 |
| 48 | 159.0 | 0.00587 | 88 | 0 | 0.00371 | 88 | 0 | 0.00447 | 88 | 0 |
| 49 | 157.1 | 0.006 | 14 | 0 | 0.00395 | 14 | 0 | 0.00444 | 14 | 0 |
| 50 | 151.3 | 0.00839 | 468 | 0 | 0.00408 | 471 | 0 | 0.00723 | 468 | 0 |
| 51 | 156.8 | 0.00877 | 90 | 0 | 0.00456 | 94 | 0 | 0.00758 | 90 | 0 |
| 52 | 153.2 | 0.00927 | 403 | 1 | 0.00465 | 402 | 1 | 0.00817 | 403 | 1 |
| 53 | 157.5 | 0.011 | 511 | 1 | 0.00482 | 512 | 33 | 0.00978 | 508 | 1 |
| 54 | 151.1 | 0.0828 | 2178 | 54 | 0.00452 | 2185 | 80 | 0.0827 | 2182 | 54 |
| 55 | 148.4 | 0.0672 | 414 | 0 | 0.00501 | 411 | 5 | 0.0671 | 412 | 0 |
| 56 | 157.6 | 0.0565 | 337 | 1 | 0.00508 | 323 | 7 | 0.0561 | 337 | 1 |
| 57 | 154.0 | 0.0574 | 405 | 9 | 0.00518 | 407 | 14 | 0.057 | 407 | 9 |
| 58 | 157.7 | 0.122 | 2378 | 62 | 0.00501 | 2400 | 136 | 0.122 | 2373 | 62 |
| 59 | 165.8 | 0.073 | 2612 | 27 | 0.00551 | 2546 | 52 | 0.073 | 2608 | 27 |
| 60 | 141.3 | 0.0696 | 3523 | 13 | 0.0061 | 3405 | 17 | 0.0693 | 3520 | 13 |
| 61 | 156.2 | 0.071 | 6818 | 14 | 0.00624 | 6786 | 23 | 0.0708 | 6832 | 14 |
| 62 | 155.9 | 0.0824 | 17957 | 92 | 0.00634 | 17326 | 123 | 0.0823 | 17981 | 92 |
| 63 | 90.3 | 0.151 | 143833 | 358 | 0.0054 | 143181 | 2050 | 0.151 | 143833 | 357 |
