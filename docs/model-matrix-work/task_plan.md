# Model matrix runner task

- [x] Read the v2 HTTP runner, scoring exports, resume contract and comparison plan.
- [x] Implement a sequential HTTP matrix runner with atomic manifest and crash recovery.
- [x] Implement bilingual, task-specific summaries and paired source-cluster diagnostics.
- [x] Verify with mocked HTTP behavior tests and document usage.

Scope: scripts/run_model_matrix.py, scripts/summarize_model_matrix.py,
tests/test_model_matrix.py and docs/model-matrix-usage.md. Other agents own
the server, bank generation, backend and project-level task plan.

Status: completed by parent after worker handoff. The project now has 53 passing Python tests and a fully audited 8-configuration, 2064-call development delivery. This delegated task itself made no model calls; see ../../task_plan.md and ../2026-10-20--reading-ability--r01--development-comparison.md for the final project state.
