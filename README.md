<!--
SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->


# ACE-RTL

ACE-RTL is an iterative RTL generation and repair agent for the CVDP benchmark.
It bundles the agent skill, reusable role components, CVDP integration scripts,
and an external LLM path that defaults to the publicly available NVIDIA
Inference API using the NVIDIA-supported Python client interface.

The default hosted model is `nvidia/nemotron-3-ultra-550b-a55b` through
`https://integrate.api.nvidia.com/v1`. API keys are read only from environment
variables and must never be committed to this repository. Users can also set
`ACE_RTL_LLM_SCRIPT` to route calls through their own adapter.

## Requirements

- Python 3.11 recommended
- `git`, `make`, `curl`
- CVDP simulation backends required by the selected rows, commonly `iverilog`,
  `vvp`, `verilator`, and `yosys`
- Commercial EDA tools only for CVDP rows that explicitly require them, for
  example Cadence Xcelium/IMC coverage flows
- A NVIDIA Inference API key in `NVIDIA_API_KEY`

## Setup

Run from this repository root:

```bash
./skills/ace-rtl/scripts/setup_cvdp_native_env.sh
```

The setup helper creates `.cvdp-native` if needed, clones
`https://github.com/NVlabs/cvdp_benchmark` into `external/cvdp_benchmark` if it
is not already present, installs the Python requirements, and downloads CVDP
JSONL files from Hugging Face repo `nvidia/cvdp-benchmark-dataset`. Existing
datasets are reused.

First check whether native simulator tools are already available in the shell
that will run ACE-RTL:

```bash
command -v iverilog vvp verilator yosys make
```

If your site provides tools through modules, Conda/Mamba, or installation roots
such as `IVERILOG_HOME`, load that environment first and rerun the check. Install
native simulator tools only if they are still unavailable. On Ubuntu/Debian this
is typically:

```bash
sudo apt-get update
sudo apt-get install -y iverilog verilator yosys make
```

For commercial/Cadence CVDP rows, configure your site-provided EDA tools before
running the evaluator. Start from `skills/eda_tool_setup/SKILL.md` and the
example script at `skills/eda_tool_setup/scripts/setup_eda_env.example.sh`.

Set your NVIDIA Inference API key in the shell that will run ACE-RTL:

```bash
export NVIDIA_API_KEY="<your NVIDIA Inference API key>"
```

Optional LLM defaults:

```bash
export ACE_RTL_MODEL="nvidia/nemotron-3-ultra-550b-a55b"
export ACE_RTL_MAX_TOKENS=32768
export ACE_RTL_ENABLE_REASONING=1
export ACE_RTL_REASONING_BUDGET=32768
export ACE_RTL_STREAM=1
export ACE_RTL_TEMPERATURE=0.2
export ACE_RTL_TOP_P=0.95
```

To use a non-default provider, implement a small adapter script and set:

```bash
export ACE_RTL_LLM_SCRIPT="/path/to/your_llm_adapter.py"
```

The adapter receives a JSON request on stdin with `model`, `messages`,
`temperature`, `top_p`, `max_tokens`, `stream`, and `extra_body`. It may return
either raw assistant text or JSON containing `{"content": "..."}` or an
chat-completions-style `choices[0].message.content` payload.

## Run With A Coding Agent Recommended

Use Codex, Claude Code, Cursor, or another coding agent from this repository
root and ask it to use the ACE-RTL skill. Example prompt:

```text
Use ACE-RTL to run CVDP cid016 from
datasets/cvdp-benchmark-dataset/cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl
with generator=nvidia/nemotron-3-ultra-550b-a55b,
reflector=nvidia/nemotron-3-ultra-550b-a55b,
coordinator=nvidia/nemotron-3-ultra-550b-a55b.
Use external/cvdp_benchmark as the official CVDP checkout.
```

The agent will read `skills/ace-rtl/SKILL.md`, inspect the selected CVDP rows,
verify local harness tools, choose the native or Docker path, and preserve run
artifacts under `outputs/`.

## Direct CID016 Run

For a direct non-agentic, no-commercial `cid016` run:

```bash
export NVIDIA_API_KEY="<your NVIDIA Inference API key>"
export CVDP_NATIVE_HARNESS=1

# The native runner uses open-source simulator tools from this shell.
# Load your site/module/Conda environment first, or prepend a tool root.
# The run will preflight required tools such as iverilog/vvp before evaluation.
command -v iverilog vvp

.cvdp-native/bin/python3 skills/ace-rtl/scripts/ace_cvdp_native_runner.py \
  --workspace "$PWD" \
  --cvdp-repo "$PWD/external/cvdp_benchmark" \
  --dataset "$PWD/datasets/cvdp-benchmark-dataset/cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl" \
  --cid cid016 \
  --generator-model nvidia/nemotron-3-ultra-550b-a55b \
  --reflector-model nvidia/nemotron-3-ultra-550b-a55b \
  --coordinator-model nvidia/nemotron-3-ultra-550b-a55b \
  --attempts 5 \
  --datapoint-workers 5 \
  --max-iterations 30
```

If `command -v iverilog vvp` fails but the tools are installed under explicit
roots, set those roots before launching the runner:

```bash
export IVERILOG_HOME=/path/to/iverilog
export VERILATOR_HOME=/path/to/verilator
export YOSYS_HOME=/path/to/yosys
export PATH="$IVERILOG_HOME/bin:$VERILATOR_HOME/bin:$YOSYS_HOME/bin:$PATH"
command -v iverilog vvp verilator yosys
```

ACE-RTL does not install simulator binaries during a run. It uses tools already
discoverable from the environment and writes `native_tool_preflight.json` in the
run directory showing which tools were required, found, or missing.

Use `--attempts 1 --max-iterations 1 --limit 1` first for a shakedown if you are
setting up a new machine.

Results are written under `outputs/`, including `run.log`, `summary.json`, and
`results.md`.
