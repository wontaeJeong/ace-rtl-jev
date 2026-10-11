# Environment and original workflow

## Provenance

- ACE-RTL upstream: `94754d796350d42502c9a32639a20d86f50e9678`.
- Official CVDP checkout: `8e894cf74414ab1eaea1e2b4e80a02f123df07b6`, cloned **inside this worktree**.
- Host: macOS 27.0 ARM64; Python 3.11.14 provisioned by uv in `.cvdp-native`.
- Original authoritative `requirements.txt` installed by official `setup_cvdp_native_env.sh`.
- Icarus Verilog 13.0, Verilator 5.052, Yosys 0.69_1 installed using Homebrew.
- Exact package versions and tool evidence are recorded under `experiments/preflight/`.
- Native evaluation differs from official Docker image (Yosys 0.40, Verilator 5.038, pytest 8.3.2). Both experimental modes must use the **same native environment**; this is not a reproduction of published paper metrics.

## Original execution path

`ace_cvdp_native_runner.py` → `ace_cvdp_native.cli.main` → per-datapoint spawned attempts → official CVDP generation processor `prepare` → `AceIterationModel.prompt` → `llm_call.py` → external adapter → `extract_solution.py` → original SV normalization/preflight → official `processor.run` with original native harness patch.

Only real evaluator results feed `result_passed`. Failed cases feed bounded evaluator diagnostics to original `FreshStartCoordinator` and `FocusedDebugger`; candidates and focus/restart history feed the next generator iteration. Success stops sibling attempts; `INFRA_SETUP` stops the datapoint; iteration budget bounds repair. External API retry count is originally three retries plus initial call. Output extraction retains original multi-target `// TARGET_FILE:` behavior.

Reusable reflector/coordinator clients use `LLMBackend`. At upstream HEAD this backend rejects non-NVIDIA models even when `ACE_RTL_LLM_SCRIPT` is configured. A minimal tested compatibility fix reuses the existing adapter helper for these roles. This fix applies identically to baseline and improved mode and is **not** a JEV optimization.

## CVDP scope

Primary dataset: `cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl`.
SHA256: `cbcd81295561ebb16e4d857e096f4d9908d042c33aff3b58abf236e868411857`.

302 rows: cid003 78, cid016 35, cid002 94, cid004 55, cid007 40. Actual service/tool inspection finds **10 rows still requiring xrun/imc**; dataset naming alone is insufficient. The eligible inventory contains 292 rows. Excluded IDs and reasons are saved in `experiments/preflight/environment.json`; they must not be silently counted as tested or successful. Agentic/heavy and subjective code-comprehension workflows are different execution/scoring paths, outside this first native non-agentic scope.

Success means **the existing official CVDP evaluator's pass predicate**, not runner exit code 0, HTTP success, candidate generation, or preflight success. Compile/functional/synthesis errors remain evaluator failures; missing dependencies/tools remain environment errors. Timeouts are separate.

## API contract evidence

Primary: prepared `gpt-6-luna` endpoint is **not a local/private address**. User explicitly authorized this prepared API for full experiments after being informed of potential costs. Initial real probes rejected `max_tokens` and nondefault temperature. Successful real inference uses `max_completion_tokens`, omits temperature/top_p and disables streaming. Both modes use this same confirmed provider contract; original NVIDIA-specific extra fields are omitted. Tokens include provider-reported reasoning tokens.

Initial SystemOne: user explicitly confirmed authentication was unnecessary (`JEV_AUTH_MODE=none`). A real valid inference returned HTTP 200, selecting `compile`, confidence 0.9924346304, probabilities summing to one, usage 122 input and 1 output tokens. Source: Ollama `docs/capabilities/decision.mdx`, retrieved via Context7; initial live response is retained in `experiments/preflight/systemone-warmup.json`.

**Updated JEV configuration (user steering during baseline):** user replaced JEV endpoint/model/key in original checkout `.env.local` and instructed using these settings. Only JEV fields were copied into the worktree; primary settings are identical. Current model is `typesafe/jev-1.13`, bearer authentication, endpoint path `/api/alpha/decisions`. Actual inference returned HTTP 200 with the same confirmed `state/questions` and `answers/probabilities/confidence` decision schema, 325 input / 32 output tokens, provider cost `0.00001365`. Response model version `typesafe/jev-1.13-20260917`, provider TypeSafe. Evidence: `experiments/preflight/jev-updated-warmup.json`. This is **not the earlier local Ollama server**; use the user's updated endpoint, without mislabeling it as local Ollama execution. Baseline manifest's earlier unused JEV configuration remains unchanged for provenance; fair comparison checks common primary settings, not unused baseline JEV fields.

Required primary env vars: `LLM_BASE_URL` (API prefix ending `/v1`), `LLM_API_KEY`, `LLM_MODEL`. Optional provider flags: `LLM_TOKEN_PARAMETER=max_tokens|max_completion_tokens`, `LLM_SAMPLING_MODE=explicit|default`, `REQUEST_TIMEOUT` positive seconds.

Required SystemOne vars: `JEV_API_MODE=systemone`, `JEV_ENDPOINT_URL` (full POST endpoint), `JEV_MODEL`, `JEV_AUTH_MODE=none|bearer`. `JEV_API_KEY` is required only for explicit bearer mode. `JEV_BASE_URL` is informational and never used to guess a missing full endpoint. Keys/URLs are not logged. `.env.local` is ignored and mode 0600; shell environment takes precedence.

## Known setup issue resolved

Official dataset downloader expected one unsplit heavy dataset filename. Current Hugging Face publishes commercial/no-commercial split files. Setup installed packages and downloaded seven valid files but exited 1 due to the stale expectation. The downloader now requires the two actual published names. No dataset or success predicate was changed.

First smoke reached the real evaluator but returned `INFRA_SETUP: pytest: command not found`. Native harness `compose_env` resolved the venv Python symlink and prepended the base interpreter's bin directory. A regression test reproduced the wrong PATH. The compatibility fix uses `sys.prefix` for tools and preserves the non-resolved venv interpreter path for cocotb. Both modes use this identical fix; the failed smoke remains separate evidence, not a baseline pass.

Native work directories embed private benchmark harness source and are Git-ignored. Original raw working artifacts remain available locally; published per-case JSON retains genuine evaluator outcomes and measured API event data without copying scorer implementations into the change.

During the broad baseline, four parentless `vvp` processes from already finished cases were found consuming CPU. These were individually verified against batch artifact paths and reaped; evidence is `experiments/preflight/baseline-orphan-cleanup.json`. Root cause: original process discovery uses Linux `/proc`, unavailable on macOS, and the timeout branch can skip group termination after the service shell has already exited. Current baseline runner code is frozen; an external watcher now reaps only parentless `vvp` with a completed-case or completed-iteration evaluator artifact. It never terminates a still-running evaluator or another batch. Monitoring/cleanup events are stored alongside this run.

Original diagnostic labels also sometimes map real service exit 124 / `native harness timeout after 300s` to functional failure. Reports normalize these using real service evidence without rewriting original results. Earlier interim raw counts may therefore have included timeouts under failure. The current baseline timing has environmental interference and cannot establish a clean speedup claim. Before matched timing claims, run a clean baseline and improved cohort with the same corrected portable cleanup implementation; preserve the original full run as feasibility/original-flow evidence.

## Original broad baseline outcome and recovery

All **292** selected cases have genuine final CVDP evaluator results: **240 success, 46 failure, 6 timeout**, success rate **82.1918%**. Reported primary tokens: **16,470,984**. **26 calls have unavailable usage**, so this number is only the known reported subtotal, not a complete billed-token total.

The parent batch runner disappeared before publishing its final summary; the reason is unknown because its ephemeral harness shell log was no longer available. Its final child native evaluator had already produced a genuine final result for `cvdp_copilot_sync_serial_communication_0001`. `recover_experiment.py` recovered that result without new inference or invented outcomes. Original parent manifest is retained as `manifest.before-recovery.json`. Batch wall time and the final case's whole-run timer are explicitly **unavailable**, not reconstructed as if measured. API call latency/token events and real evaluator outcomes remain available. See `reports/original-baseline/`.

Portable process discovery now uses the already-declared psutil dependency rather than Linux-only `/proc`; path matches reject adjacent similarly named task paths. Timeout process-group cleanup no longer depends on the service shell still being alive. New runs persist `execution.json` before and after each case. Empty successful HTTP completions retain provider-reported billed tokens even when the content is rejected.

Eight-worker real CVDP shakedown after these common fixes completed all eight cases: six passed and two candidate failures, with no setup/runner errors. These smoke outcomes do not establish a performance gain or replace the full cohort. Final clean baseline/improved comparison will use **eight workers for both** and otherwise unchanged 1 attempt × 5 iterations, API 60 s, LLM subprocess 90 s, evaluator 300 s, case 1800 s conditions. Durable parent driver logs are retained locally rather than depending only on harness-managed ephemeral stdout.

Clean batch `baseline-20261011T103810Z-97717` completed all 292 cases: 239 success / 52 candidate failure / 1 native service timeout (81.8493%). Measured batch wall time 4,367.2497 s, mean case time 109.6309 s, no missing case timers. Primary calls 1,311; reported input 14,235,838 and output 2,302,443, known subtotal 16,538,281; 33 usage-unknown calls mean full billed tokens are unavailable. Watcher observed zero orphan cleanup events. Report: `reports/clean-baseline/`.

The user subsequently required cost-first design/preparation before tests. No new paid runs are queued after this completion. Remaining work is design/offline integration and spending-limit preparation; JEV E2E, repeated/ablation experiments and optimization savings remain unexecuted/unavailable.

## Measurement protocol

One attempt, at most five iterations, four concurrent cases, request timeout 60 s, original LLM subprocess timeout 90 s, each evaluator 300 s, each whole case 1800 s. Smoke uses one case/one iteration/one worker. This reduced budget is an explicit controlled experiment, not the original default five attempts × 30 iterations.

Per-case runner wall time includes generation, repair, evaluator and process overhead. Batch wall time includes worker overlap and is not the sum of case times. Primary warmup uses actual inference and is stored separately/excluded from evaluation costs. Each API call writes a unique event before and after request; terminated calls retain `inflight` and **unknown usage**, never fictional zero billed tokens. Reported prompt/completion/total tokens and char/4 estimates are separate. No custom response cache is used. Provider cache counters are preserved where returned; server-internal cache/model-load timing may be unobservable.
