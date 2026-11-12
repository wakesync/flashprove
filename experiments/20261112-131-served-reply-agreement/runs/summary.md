| prompt | reply tokens | served = REF | served = XS18 | served = XS20 | REF = XS18 | REF = XS20 | whole reply REF / XS18 / XS20 | 3 reps identical |
|---|---|---|---|---|---|---|---|---|
| q01 | 2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | yes / yes / yes | yes |
| q02 | 36 | 34/36 | 34/36 | 34/36 | 36/36 | 36/36 | no / no / no | yes |
| q03 | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | yes / yes / yes | yes |
| q04 | 10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | yes / yes / yes | yes |
| q05 | 23 | 23/23 | 23/23 | 23/23 | 23/23 | 23/23 | yes / yes / yes | yes |
| q06 | 4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | yes / yes / yes | yes |
| q07 | 27 | 27/27 | 27/27 | 27/27 | 27/27 | 27/27 | yes / yes / yes | yes |
| q08 | 53 | 53/53 | 53/53 | 53/53 | 53/53 | 53/53 | yes / yes / yes | yes |
| q09 | 64 | 62/64 | 62/64 | 62/64 | 64/64 | 64/64 | no / no / no | yes |
| q10 | 64 | 64/64 | 64/64 | 64/64 | 64/64 | 64/64 | yes / yes / yes | yes |
| all | 291 | 287/291 | 287/291 | 287/291 | 291/291 | 291/291 | | |

Disagreements (any path vs served, or XS vs REF):

| prompt | reply pos | served id | REF | XS18 | XS20 | REF top-2 margin |
|---|---|---|---|---|---|---|
| q02 | 30 | 1040 | 11 | 11 | 11 | 0.2125 |
| q02 | 32 | 466 | 321 | 321 | 321 | 1.386 |
| q09 | 10 | 303 | 6121 | 6121 | 6121 | 0.07367 |
| q09 | 45 | 20359 | 310 | 310 | 310 | 1.066 |

Verdict: {"H0": "PASS", "H1_XS18": "PASS", "H2_XS20": "PASS"}
Deterministic (REF#2, XS18#2 top-1 equal): True
