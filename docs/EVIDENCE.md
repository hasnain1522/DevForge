# DevForge evidence

DevForge evidence is a persisted record of observations produced by the product. It is scoped to the authenticated user and linked to the repository and execution where applicable. It is not a claim that an action succeeded: status and payloads reflect the values returned by the corresponding operation.

## Generation

Analysis and mission creation record their inputs/results. An execution captures objective repository metrics before work, stores agent activity and actual changed-file hashes/diff counts, then captures metrics after work. Evidence records are generated from these database rows and execution results; the report endpoint reads them back rather than inventing values.

## Verification evidence

`VerificationRunner` invokes pytest, Ruff, and a TODO/FIXME scan as subprocesses in the selected repository. Exit codes and observed output determine the verification result. A completed run stores a `VerificationResult`, including pass/fail counts and sanitized command output; a missing verification result is not treated as success. Execution-related evidence is persisted with its execution identifier and timestamp.

## IBM Bob development evidence

IBM Bob was used as a development-time assistant during earlier implementation. DevForge does not call Bob at runtime or require Bob to build. Genuine Bob screenshots or records belong under `docs/evidence/bob/`, separate from product evidence stored in DevForge's database. No Bob records are fabricated or implied by an empty directory.
