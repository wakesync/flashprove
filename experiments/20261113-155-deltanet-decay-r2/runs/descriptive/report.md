### Registered arms next to PR #146's T3 (T3 from PR #146's committed summary.json)

| arm | failing cells / 23,040 | reject, e_tok, e_cum | failing heads / 2,304 |
|---|---|---|---|
| T3 (PR #146) | 6391 | 0, 3854, 3253 | 1513 |
| U1 | 3942 | 0, 1175, 2772 | 1336 |
| U2 | 1210 | 0, 850, 378 | 504 |
| U3 | 815 | 0, 815, 0 | 294 |
| U4 | 0 | 0, 0, 0 | 0 |

### Per-head exponent (rule of the PREREG): e_h 4 to 20, cA_h 2051 to 4091 over 2,304 heads; distinct exponents within a layer: median 8, max 10. Under PR #146's per-layer rule 170 heads had cA below 16. Heads whose product floor has a shift above 12 (two remainder limbs under DESIGN 5.0's layout): 1412 with the per-head rule, 192 with PR #146's per-layer rule (counted from the exponents, not built).

### Failing cells per prompt (of 2,304 per prompt; token count in brackets)

| arm | p01-ordinary-short (13) | p02-ordinary-paragraph (107) | p03-repeat-word (512) | p04-repeat-punct (64) | p05-code (144) | p06a-digits-256 (256) | p07-chat-ordinary (23) | p08-chat-refusal (39) | p09-multilingual (21) | p11-chat-long (282) |
|---|---|---|---|---|---|---|---|---|---|---|
| U1 | 63 | 358 | 985 | 140 | 494 | 863 | 71 | 99 | 84 | 785 |
| U2 | 34 | 155 | 247 | 62 | 164 | 159 | 35 | 59 | 52 | 243 |
| U3 | 34 | 140 | 51 | 20 | 139 | 93 | 35 | 58 | 52 | 193 |
| U4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### Failing heads per layer (of 48)

- U1: L0: 27, L1: 39, L2: 39, L4: 44, L5: 36, L6: 28, L8: 36, L9: 26, L10: 30, L12: 35, L13: 31, L14: 27, L16: 30, L17: 24, L18: 30, L20: 29, L21: 25, L22: 21, L24: 28, L25: 27, L26: 29, L28: 34, L29: 24, L30: 25, L32: 30, L33: 25, L34: 27, L36: 29, L37: 26, L38: 15, L40: 26, L41: 29, L42: 29, L44: 33, L45: 25, L46: 25, L48: 29, L49: 28, L50: 30, L52: 32, L53: 22, L54: 18, L56: 26, L57: 20, L58: 17, L60: 24, L61: 23, L62: 24
- U2: L0: 0, L1: 26, L2: 29, L4: 28, L5: 20, L6: 12, L8: 16, L9: 7, L10: 18, L12: 13, L13: 18, L14: 11, L16: 8, L17: 8, L18: 4, L20: 1, L21: 3, L22: 5, L24: 10, L25: 8, L26: 17, L28: 11, L29: 12, L30: 10, L32: 11, L33: 10, L34: 7, L36: 5, L37: 3, L38: 2, L40: 11, L41: 15, L42: 22, L44: 15, L45: 17, L46: 13, L48: 14, L49: 18, L50: 6, L52: 12, L53: 7, L54: 0, L56: 2, L57: 5, L58: 2, L60: 2, L61: 4, L62: 6
- U3: L0: 0, L1: 25, L2: 29, L4: 27, L5: 19, L6: 10, L8: 16, L9: 6, L10: 11, L12: 10, L13: 16, L14: 11, L16: 3, L17: 5, L18: 2, L20: 0, L21: 3, L22: 5, L24: 9, L25: 5, L26: 3, L28: 4, L29: 7, L30: 6, L32: 1, L33: 4, L34: 1, L36: 1, L37: 3, L38: 2, L40: 6, L41: 3, L42: 5, L44: 5, L45: 11, L46: 9, L48: 2, L49: 7, L50: 0, L52: 1, L53: 1, L54: 0, L56: 0, L57: 0, L58: 0, L60: 0, L61: 0, L62: 0

### U4 error split by source (each source alone, the rest float64), over 23,040 cells [registered: best arm]

| source | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max per cell: median (max) | e_cum max per cell: median (max) |
|---|---|---|---|---|
| row_step | 0 | 0 | 0.000161 (0.000712) | 0.000119 (0.000697) |
| output_rounding | 0 | 0 | 4.73e-07 (4.77e-07) | 5.54e-07 (0.000212) |

### U3 error split by source (each source alone, the rest float64), over 23,040 cells [POST HOC, Amendment A3]

| source | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max per cell: median (max) | e_cum max per cell: median (max) |
|---|---|---|---|---|
| cA_rounding | 0 | 0 | 1.5e-05 (8.69e-05) | 2.34e-05 (8.69e-05) |
| softplus_table | 0 | 0 | 0.000325 (0.00143) | 0.00044 (0.00139) |
| g_floor_and_exp_tables | 0 | 0 | 1.3e-06 (0.00143) | 9.65e-06 (0.00139) |
| output_rounding | 0 | 0 | 4.73e-07 (4.77e-07) | 5.54e-07 (0.000212) |

U3 failing heads (294 of 2,304) by which single source alone already fails the bar on that head [POST HOC]: none alone (only the combination): 294

### Per-token error by band of the float64 exponent g, table-chain arms [POST HOC, Amendment A3]

| arm | cells over the e_tok bar | of these, largest error on a token with g >= 1 | cells whose g < 1 tokens alone exceed the bar | largest error on g < 1 tokens | largest error on g >= 1 tokens | smallest g at the worst token of a failing cell |
|---|---|---|---|---|---|---|
| U1 | 1175 | 829 | 441 | 0.00854 | 0.00482 | 0.000152 |
| U2 | 850 | 814 | 36 | 0.00991 | 0.00282 | 0.000135 |
| U3 | 815 | 815 | 0 | 0.00147 | 0.00282 | 1.01 |

(token, head) values with g >= 1: 207656 of 3366144 (6.17%).

### Accumulated-decay failures

- U1: 1023 heads fail e_cum on at least one prompt; 914 of them have a median g below 1/256 and 293 below 2^-12 (median g from PR #146's committed table).
- U2: 208 heads fail e_cum; 208 of them have x below -8 on at least one token (their A: 0.0821 to 17.2, median 0.474). U3 (softplus rows down to -16): 0 cells fail e_cum.

### 15 worst U3 heads by per-token error

| layer | head | A | cA_h (e_h) | dt_bias | g median | g max | e_tok max | prompts failing (of 10) |
|---|---|---|---|---|---|---|---|---|
| 1 | 44 | 16.39 | 2098 (7) | -3.875 | 0.41 | 1.84 | 0.00282 | 4 |
| 14 | 12 | 32.1 | 2054 (6) | -3.766 | 1.45 | 7.16 | 0.00279 | 8 |
| 28 | 27 | 63.83 | 4085 (6) | -3.938 | 0.749 | 16.2 | 0.00279 | 7 |
| 8 | 8 | 12.97 | 3320 (8) | -3.578 | 0.536 | 3.52 | 0.00268 | 4 |
| 13 | 33 | 11.99 | 3070 (8) | -4.375 | 0.136 | 7.01 | 0.00266 | 2 |
| 13 | 24 | 5.891 | 3016 (9) | -3.219 | 0.394 | 4.43 | 0.00265 | 4 |
| 1 | 36 | 16.14 | 2066 (7) | -2.281 | 2.67 | 8.43 | 0.00265 | 3 |
| 4 | 6 | 11.81 | 3023 (8) | -2.547 | 0.956 | 7.18 | 0.00265 | 7 |
| 13 | 30 | 5.937 | 3040 (9) | -2.828 | 0.373 | 3.4 | 0.00265 | 4 |
| 24 | 42 | 4.378 | 2241 (9) | -3.906 | 0.0201 | 2.8 | 0.00264 | 1 |
| 45 | 35 | 10.75 | 2752 (8) | -4.25 | 0.0891 | 9.87 | 0.00263 | 4 |
| 1 | 45 | 8.243 | 2110 (8) | -1.289 | 3.02 | 5.91 | 0.00263 | 5 |
| 9 | 42 | 8.775 | 2246 (8) | -2.281 | 1.81 | 6.76 | 0.00262 | 7 |
| 2 | 44 | 2.827 | 2894 (10) | -1.5 | 0.537 | 4.29 | 0.00262 | 4 |
| 1 | 46 | 5.281 | 2704 (9) | -1.93 | 1.02 | 3.71 | 0.00261 | 4 |

U3 failing heads: 294; all 294 have a g of at least 1 on some token; heads in the model with g >= 1 on some token: 961; A of the failing heads 0.515 to 102 (median 4.61).

### Table sizes (counted from the registered shapes, not built)

| arm | public table rows | per-head table rows | per-head public exponents |
|---|---|---|---|
| T3 (PR #146) | 12,288 (softplus 4,096 + coarse exp 4,096 + fine exp 4,096) | 0 | 0 (one per layer) |
| U1 | 12,288 (as T3) | 0 | 2,304 (48 per layer) |
| U2 | 1,056,768 (softplus 4,096 + coarse exp 4,096 + fine exp 1,048,576) | 0 | 2,304 |
| U3 | 1,058,816 (softplus 6,144 + coarse exp 4,096 + fine exp 1,048,576) | 0 | 2,304 |
| U4 | 0 | 12,288 per head, 589,824 per layer, 28,311,552 for 48 layers | 0 |

U4 rows spanned by the observed x range on these 10 prompts (descriptive, from PR #146's committed per-head x minimum and maximum, not a bound): 5,494,684 of 28,311,552; per head median 2242, max 7622.
