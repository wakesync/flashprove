# Summary (integer M3 MLP (DESIGN 5.5, r2) in every layer for FM, XM18; DeltaNet heads XS18 in XM18, float64 in REF and FM; in_proj, out_proj, attention, every RMSNorm (incl. the MLP pre-norm), final norm and lm_head float64; no proof)

Bars: top-1 >= 99%, KL median <= 0.0001 nats, KL max <= 0.1 nats, no guard error.

## abl
logits not finished; layers done 0..30; XM18#2 bit-equal every layer: True

Residual relative L2 vs REF after the last layer done, per prompt:

| prompt | XM18 | FM |
|---|---|---|
| p01-ordinary-short | 0.0059 | 0.00587 |
| p07-chat-ordinary | 0.00522 | 0.00496 |
| p08-chat-refusal | 0.00601 | 0.00576 |
| p09-multilingual | 0.00596 | 0.0056 |
| p02-ordinary-paragraph | 0.00753 | 0.00698 |
| p04-repeat-punct | 0.00515 | 0.00517 |
| p05-code | 0.00724 | 0.00688 |
| p03-repeat-word | 0.0878 | 0.0858 |
| p06a-digits-256 | 0.00835 | 0.00813 |
| p11-chat-long | 0.00603 | 0.00593 |


### ranges (abl leg, layers in ranges-abl.jsonl); verdict OUT-OF-BOUND, XM18 class events 25123078
weight exponents 11..15, all in 1..24: True, all |W| <= 4095: True

| path | quantity | max abs | log2 | layer | prompt | bound | counts |
|---|---|---|---|---|---|---|---|
| XM18 | m | 148536 | 17.18 | 30 | p03-repeat-word | |m| <= 2,047 (DESIGN 3.2, A_PUB) | n_m_over_2047 25123072 (layers [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]) |
| XM18 | gw | 38091 | 15.22 | 26 | p03-repeat-word | honest < 2^18, rng < 2^23; SiLU domain [-2^15, 2^15) | n_gw_ge_2e18 0 (layers []), n_gw_ge_2e23 0 (layers []), n_silu_sat_lo 2 (layers [22]), n_silu_sat_hi 4 (layers [21, 24, 26]) |
| XM18 | u | 37178 | 15.18 | 22 | p08-chat-refusal | honest < 2^18, rng < 2^23 | n_u_ge_2e18 0 (layers []), n_u_ge_2e23 0 (layers []) |
| XM18 | s | 32741 | 15 | 21 | p06a-digits-256 | |s| <= 32,741 (table image) |  |
| XM18 | h | 145770 | 17.15 | 22 | p05-code | honest < 2^18, rng < 2^23 | n_h_ge_2e18 0 (layers []), n_h_ge_2e23 0 (layers []) |
| XM18 | acc_down | 5.06228e+08 | 28.92 | 26 | p11-chat-long | ledger 2^55.02 (bounds-r3 'M3a-MLP down (r2)'); float guard 2^53 | n_acc_down_ge_ledger 0 (layers []) |
| XM18 | out | 123590 | 16.92 | 26 | p11-chat-long | |out| < 2^31 (DESIGN 3.2, OUT_PUB) | n_out_ge_2e31 0 (layers []) |
| FM | m | 148534 | 17.18 | 30 | p03-repeat-word | |m| <= 2,047 (DESIGN 3.2, A_PUB) | n_m_over_2047 25060897 (layers [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]) |
| FM | gw | 38109 | 15.22 | 26 | p03-repeat-word | honest < 2^18, rng < 2^23; SiLU domain [-2^15, 2^15) | n_gw_ge_2e18 0 (layers []), n_gw_ge_2e23 0 (layers []), n_silu_sat_lo 2 (layers [22]), n_silu_sat_hi 5 (layers [21, 22, 24, 26]) |
| FM | u | 37194 | 15.18 | 22 | p08-chat-refusal | honest < 2^18, rng < 2^23 | n_u_ge_2e18 0 (layers []), n_u_ge_2e23 0 (layers []) |
| FM | s | 32741 | 15 | 21 | p06a-digits-256 | |s| <= 32,741 (table image) |  |
| FM | h | 145981 | 17.16 | 22 | p05-code | honest < 2^18, rng < 2^23 | n_h_ge_2e18 0 (layers []), n_h_ge_2e23 0 (layers []) |
| FM | acc_down | 5.06221e+08 | 28.92 | 26 | p11-chat-long | ledger 2^55.02 (bounds-r3 'M3a-MLP down (r2)'); float guard 2^53 | n_acc_down_ge_ledger 0 (layers []) |
| FM | out | 123589 | 16.92 | 26 | p11-chat-long | |out| < 2^31 (DESIGN 3.2, OUT_PUB) | n_out_ge_2e31 0 (layers []) |

## stock
logits not finished


