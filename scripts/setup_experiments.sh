#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
command -v uv >/dev/null || { echo 'Missing uv; install uv first.' >&2; exit 2; }
if [ ! -x .cvdp-native/bin/python ]; then
  uv venv --python 3.11 --seed .cvdp-native
fi
# The authoritative requirements and dataset setup remain owned by ACE-RTL.
bash skills/ace-rtl/scripts/setup_cvdp_native_env.sh
missing=0
for tool in iverilog vvp verilator yosys make; do
  if ! command -v "$tool" >/dev/null; then
    echo "Missing native tool: $tool" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo 'macOS: brew install icarus-verilog verilator yosys' >&2
  echo 'Ubuntu: sudo apt-get install iverilog verilator yosys make' >&2
  exit 2
fi
.cvdp-native/bin/python scripts/run_experiments.py preflight
