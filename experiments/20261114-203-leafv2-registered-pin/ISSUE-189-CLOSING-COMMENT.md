Proposed closing comment for issue #189. Text only: not posted. Whether to close #189 is the coordinator's and the maintainer's call, after PR review.

---

The stop-rule finding recorded by PR #191 is answered for the registered runs by a reader-side change registered as issue #203 (`experiments/20261114-203-leafv2-registered-pin`). It is answered only in that scope.

What changed (opt-in, default mode unchanged):
- A committed pin, `experiments/20261112-149-leaf-v2/runs/registered-pins.json`, holds the SHA-256 of every file the leaf-v2 readers consume in run 1, run 2 and run 3, plus both compare files.
- `wb_leafv2.py compare ... --registered` and `summarise.py --registered` refuse a registered run whose files do not match the pin.
- The registered summary separates `PASS` (basis `single-run`) from `PASS-UNION` (a union that reaches 78 blocks with no single run doing so).

Measured, unreplicated:
- In registered mode all 23 stop-rule cases of #191 are refused. None gives `PASS`.
- The committed runs give H3 `PASS` with basis `single-run`.
- 213 of 213 existing expectations that were not switches keep their outcome.
- Suite 346 of 346, run twice, byte-identical receipts.

What stays open, and why this comment does not say the stop rule is resolved in general:
- **The default (non-registered) mode is unchanged.** It still gives a full `PASS` to the 13 altered inputs of #191. Anything that reads leaf-v2 run files without `--registered` has the old behaviour.
- **The pin is not authentication.** It binds "registered run" to what the repository holds. Whoever can change the repository can change the pin together with a run, and registered mode then accepts it (defeat case D2).
- Files the readers do not consume are not checked (D4). The 23 + 12 cases do not exhaust the inputs.
- Requiring `run-meta.json` was not added, because #191 showed it is not sufficient. Cryptographic run authentication remains out of scope.

Suggested: close #189 as "answered for registered evidence via #203", with the open items above recorded as known limits. Alternatively keep it open if the default mode should also refuse, or label union results; that needs its own registration.
