# Runner implementation notes

- Platform v2 saves one row per planned item, including errors; /resume only
  runs unfinished items, never retries already recorded failures.
- POST /api/v2/runs has no idempotency key or run-list endpoint. A lost creation
  response cannot safely be retried automatically. The manifest must preserve
  an ambiguous creation state for explicit run-ID reconciliation.
- Actual run snapshots freeze model identity, selected bank, source-bank hash,
  output schema and runner/prompt/grader versions. Client checks these before
  continuing and exports full raw JSON and CSV.
- No-context evidence/joint metrics are N/A. Answer gain is reported by language
  and question kind, with paired source-cluster resampling inside fixed domain
  and length strata; tiny strata cannot establish population rankings.
