# Model suite source task — 2026-10-24

- [x] Read historical installer/runtime constraints.
- [x] Fetch only small official and registry metadata; pin manifests and all blob identities.
- [x] Create server-only installer and workstation Yi tokenizer-only mode.
- [x] Record 4K Yi context and author-template mismatch; preserve registry runtime by parent decision.
- [x] Pass 5 meaningful local tests; no server or model calls by this task.

Deliverable: docs/model-expansion-sources-20261024.md. Server installs and inference are parent-owned.

Access limitation: Gemma gated HF commit route returned401; no authentication or click-through performed; public Google/HF API/registry metadata retained instead.
