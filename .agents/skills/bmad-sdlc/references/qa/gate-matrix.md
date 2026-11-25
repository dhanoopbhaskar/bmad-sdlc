# QA Gate Matrix (Role Overlay)

QA delta only. Base `gate-matrix.md` owns levels, evidence, and override effects.

- `verify.trace`: required where the base table says required; override only with a documented reason, and the gap stays visible in the close summary.
- `verify.nfr` and `verify.test_review`: conditional. Override with a reason when the condition does not apply.
- `build.review` / `build.done`: QA's decisions on every track. `build.done` refuses unless `build.review` passed; an overridden review is not enough.
- `close.retro` / `close.walkthrough`: optional. `skipped` without a reason is normal.

When `verify.trace` is blocked, name the missing matrix or evidence and stop. The conductor records the blocked gate and pointer; the handed-off role never writes the ledger. The handoff shape and rollback rule are in `handoff-protocol.md` §Role transitions.
