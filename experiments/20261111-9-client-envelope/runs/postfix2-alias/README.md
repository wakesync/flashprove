# runs/postfix2-alias: second post-registration fix (state file aliases)

Post-registration checks, no pre-registered threshold, not part of the registered result and not a
replication. Written 2026-11-12 after the second review round of PR #122 (at head c715045e) found
that a symlink or hard-link alias of the state file released one nonce twice.

Client under test: `research/envelope/client_verify.py` as committed in 6836843 (lock and rename
on the real path, state files with more than one hard link refused). Test file:
`research/envelope/test_aliases.py` as committed in 6836843. cp_verify: `bin/cp_verify` built by
`verifier/build.sh`, binary sha256 `98931b82...a4d0`, build `ea191b01...bd66` (as ENV.json).
Every run under the host's heavy-job gate, `taskset -c 14-15`, shared loaded host, one local
filesystem.

| file | command | started / finished (UTC) |
|---|---|---|
| `fixed-client.json` | `test_aliases.py --repeats 20` | 01:30:17 / 01:35:16 |
| `prefix2-client-c715045.json` | `test_aliases.py --repeats 20 --client <copy of c715045e:research/envelope/client_verify.py>` | 01:35:26 / 01:41:44 |
| `concurrency-fixed-client.json` | `test_concurrency.py --repeats 20` (the first fix's tests, rerun on the second-fix client) | 01:37:59 / 01:41:18 |

The copy of the c715045e client was put next to the real one under another name for the run and
removed afterwards; its file name is in the `client` field. The relative-path cases pass on both
clients: the same directory entry gives the same lock file whether or not the path is resolved,
so those two cases are regression guards, not a demonstration of the defect.
