# Release outcome matrix

Each cell shows the observed category and process exit. All five repetitions have identical categories and exits. `parse:` means admission was not run. Other reader refusals follow successful parsing. The first series is retained, including its layout-generation and invocation mistakes. The supplementary series is descriptive, not a replacement for the first series.

| Case | Before reader | Patched reader | First verifier | Supplementary verifier |
|---|---|---|---|---|
| dense-changed-exp | `policy-tables` (2) | `ok` (0) | `table-digest-exp` (1) | `table-digest-exp` (1) |
| dense-changed-rope | `policy-tables` (2) | `ok` (0) | `table-digest-rope` (1) | `table-digest-rope` (1) |
| dense-changed-silu | `policy-tables` (2) | `ok` (0) | `table-digest-silu` (1) | `table-digest-silu` (1) |
| dense-duplicate | `parse:policy-tables` (1) | `parse:policy-tables` (1) | `policy-tables` (1) | `policy-tables` (1) |
| dense-gcl | `policy-gcl` (2) | `policy-gcl` (2) | `policy-gcl` (1) | `policy-gcl` (1) |
| dense-header-absent-class | `header-absent-class` (2) | `header-absent-class` (2) | `header-absent-class` (1) | `header-absent-class` (1) |
| dense-header-absent-kind | `policy-tables` (2) | `header-absent-kind` (2) | `header-absent-kind` (1) | `header-absent-kind` (1) |
| dense-invalid | `parse:policy-line-form` (1) | `parse:policy-line-form` (1) | `policy-tables` (1) | `policy-tables` (1) |
| dense-no-digests | `ok` (0) | `ok` (0) | `plan-layout` (1) | `not-met:table-digests` (4) |
| dense-partial | `parse:policy-tables` (1) | `parse:policy-tables` (1) | `policy-tables` (1) | `policy-tables` (1) |
| dense-rcl | `policy-rcl` (2) | `policy-rcl` (2) | `policy-rcl` (1) | `policy-rcl` (1) |
| dense-reordered | `parse:policy-tables` (1) | `parse:policy-tables` (1) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-0 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-1 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-2 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-3 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-4 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-5 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-6 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-sigmoid-7 | `policy-tables` (2) | `policy-tables` (2) | `policy-tables` (1) | `policy-tables` (1) |
| dense-valid | `policy-tables` (2) | `ok` (0) | `plan-layout` (1) | `met` (4) |
| experts-changed-exp | `ok` (0) | `ok` (0) | `table-digest-exp` (1) | `table-digest-exp` (1) |
| experts-changed-rope | `ok` (0) | `ok` (0) | `table-digest-rope` (1) | `table-digest-rope` (1) |
| experts-changed-sigmoid | `ok` (0) | `ok` (0) | `table-digest-sigmoid` (1) | `table-digest-sigmoid` (1) |
| experts-changed-silu | `ok` (0) | `ok` (0) | `table-digest-silu` (1) | `table-digest-silu` (1) |
| experts-duplicate | `parse:policy-tables` (1) | `parse:policy-tables` (1) | `policy-tables` (1) | `policy-tables` (1) |
| experts-gcl-zero | `policy-gcl` (2) | `policy-gcl` (2) | `policy-gcl` (1) | `policy-gcl` (1) |
| experts-invalid | `parse:policy-line-form` (1) | `parse:policy-line-form` (1) | `policy-tables` (1) | `policy-tables` (1) |
| experts-no-digests | `ok` (0) | `ok` (0) | `not-met:table-digests` (4) | `not-met:table-digests` (4) |
| experts-partial | `parse:policy-tables` (1) | `parse:policy-tables` (1) | `policy-tables` (1) | `policy-tables` (1) |
| experts-rcl-zero | `policy-rcl` (2) | `policy-rcl` (2) | `policy-rcl` (1) | `policy-rcl` (1) |
| experts-reordered | `parse:policy-tables` (1) | `parse:policy-tables` (1) | `policy-tables` (1) | `policy-tables` (1) |
| experts-valid | `ok` (0) | `ok` (0) | `met` (4) | `met` (4) |
