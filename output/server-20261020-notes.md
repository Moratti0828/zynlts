# Server recovery 2026-10-20

Scope: only `/home/jmy/reading-bench` project services, GPU 0 if healthy and unused. No global driver/network changes, no foreign process termination, no weight downloads by this worker.

- [x] Read current user guide and project SSH/startup scripts.
- [x] Confirm SSH route and current GPU usage: four RTX 3090 GPUs, each 1 MiB used; no compute processes. `/home` has about 1.7 TiB free.
- [x] Capture reproducible CUDA and service probe: `server-readiness-before-20261020.json`, `server-readiness-after-20261020.json`. Physical GPU 0 has `cuInit=0`, count 1, no initialization error.
- [x] Restore own Ollama 11435 and app 8787, confirm actual GPU inference: Qwen returns `20`, `/api/ps size_vram=5341542400`, physical GPU 0 runner PID 66202, all 29 layers on GPU.
- [x] Restore local 8877 SSH tunnel and hand off evidence: foreground SSH exec session 36373; HTTP health 1.2.0 and both model registrations available.

Initial errors: services and tmux were absent after server restart; no project jobs could be active in the absent services.

Files: `scripts/server_probe_20261020.py` is read-only; `deploy/server-gpu-smoke-20261020.py` issues exactly one short engineering request, not a reading benchmark result. Both were executed successfully on the server. The project Ollama start script rechecked free memory and absence of compute processes immediately before launch. No other user's process or service was changed.

Single-card policy remains `CUDA_VISIBLE_DEVICES=0`, Ollama 11435 loopback, one loaded model, one inference request, model directory `/home/jmy/reading-bench/runtime/models`. App 8787 loopback is in `reading-bench-app` tmux; model service in `reading-bench-ollama` tmux. Existing models: Qwen2.5 7B (metadata 7.6B), Llama3.1 8B; both Q4_K_M. Disk available at probe: 1,815,755,644,928 bytes. No additional weights downloaded by this worker.

The first Qwen request took 32.12 seconds, of which 32.03 seconds was initial model loading. Its 67 prompt tokens took 0.0376 seconds and 3 output tokens took 0.0161 seconds; this tiny engineering prompt does not estimate realistic reading-test latency. Full raw timing and response are retained in `server-gpu-smoke-20261020.json`.

SSH route: the project `connect-server.ps1` derives current WLAN address/interface and uses the bundled Python with a temporary relay. At this check WLAN was 10.147.102.3 / interface 22. No static route or SSH configuration changes. Keep the foreground tunnel running for `http://127.0.0.1:8877`.
