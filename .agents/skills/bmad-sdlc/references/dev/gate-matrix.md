# DEV Gate Matrix (Role Overlay)

DEV delta only. Base `gate-matrix.md` owns levels, evidence, and override effects.

- `build.ticket`: override only when an evidence pointer exists; never close a ticket on an override alone.
- `build.tests`: override with a reason when no test baseline exists or the run is unavailable.
- `build.review` and `build.done`: QA's decisions. An overridden review is not enough for `build.done`; DEV never self-approves.

When `build.ticket` is blocked, report the missing build plan or acceptance criteria and stop. The conductor records it; DEV never writes the ledger.
