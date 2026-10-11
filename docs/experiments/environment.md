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

SystemOne: user explicitly confirmed authentication is unnecessary (`JEV_AUTH_MODE=none`). A real valid inference returned HTTP 200, selecting `compile`, confidence 0.9924346304, probabilities summing to one, usage 122 input and 1 output tokens. This establishes a decision API, **not Chat Completions**. Source: Ollama `docs/capabilities/decision.mdx`, retrieved via Context7; live response is retained in `experiments/preflight/systemone-warmup.json`.

Required primary env vars: `LLM_BASE_URL` (API prefix ending `/v1`), `LLM_API_KEY`, `LLM_MODEL`. Optional provider flags: `LLM_TOKEN_PARAMETER=max_tokens|max_completion_tokens`, `LLM_SAMPLING_MODE=explicit|default`, `REQUEST_TIMEOUT` positive seconds.

Required SystemOne vars: `JEV_API_MODE=systemone`, `JEV_ENDPOINT_URL` (full POST endpoint), `JEV_MODEL`, `JEV_AUTH_MODE=none|bearer`. `JEV_API_KEY` is required only for explicit bearer mode. `JEV_BASE_URL` is informational and never used to guess a missing full endpoint. Keys/URLs are not logged. `.env.local` is ignored and mode 0600; shell environment takes precedence.

## Known setup issue resolved

Official dataset downloader expected one unsplit heavy dataset filename. Current Hugging Face publishes commercial/no-commercial split files. Setup installed packages and downloaded seven valid files but exited 1 due to the stale expectation. The downloader now requires the two actual published names. No dataset or success predicate was changed.

First smoke reached the real evaluator but returned `INFRA_SETUP: pytest: command not found`. Native harness `compose_env` resolved the venv Python symlink and prepended the base interpreter's bin directory. A regression test reproduced the wrong PATH. The compatibility fix uses `sys.prefix` for tools and preserves the non-resolved venv interpreter path for cocotb. Both modes use this identical fix; the failed smoke remains separate evidence, not a baseline pass.

Native work directories embed private benchmark harness source and are Git-ignored. Original raw working artifacts remain available locally; published per-case JSON retains genuine evaluator outcomes and measured API event data without copying scorer implementations into the change.

## Measurement protocol

One attempt, at most five iterations, four concurrent cases, request timeout 60 s, original LLM subprocess timeout 90 s, each evaluator 300 s, each whole case 1800 s. Smoke uses one case/one iteration/one worker. This reduced budget is an explicit controlled experiment, not the original default five attempts × 30 iterations.

Per-case runner wall time includes generation, repair, evaluator and process overhead. Batch wall time includes worker overlap and is not the sum of case times. Primary warmup uses actual inference and is stored separately/excluded from evaluation costs. Each API call writes a unique event before and after request; terminated calls retain `inflight` and **unknown usage**, never fictional zero billed tokens. Reported prompt/completion/total tokens and char/4 estimates are separate. No custom response cache is used. Provider cache counters are preserved where returned; server-internal cache/model-load timing may be unobservable.
