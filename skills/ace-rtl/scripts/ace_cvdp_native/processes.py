# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ACE-RTL native CVDP runner internals."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import fcntl
import hashlib
import json
import logging
import multiprocessing
import os
import queue
import re
import shutil
import shlex
import signal
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml
import psutil

from .config import *

class Tee:
    def __init__(self, *streams: Any) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def ensure_under(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"{label} must stay under workspace root: {resolved}")
    return resolved


def unique_run_dir(outputs_root: Path, cid: str, dataset_stem: str) -> Path:
    base = outputs_root / f"cvdp_{cid}_{dataset_stem}_{now_stamp()}"
    run_dir = base
    i = 1
    while run_dir.exists():
        i += 1
        run_dir = Path(f"{base}_{i}")
    run_dir.mkdir(parents=True)
    return run_dir


def load_cid_rows(dataset: Path, cid: str, ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    wanted = set(ids or [])
    rows: List[Dict[str, Any]] = []
    with dataset.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if cid not in row.get("categories", []):
                continue
            if wanted and row["id"] not in wanted:
                continue
            rows.append(row)
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def pid_is_alive(pid: int) -> bool:
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
        tail = stat.rsplit(")", 1)[1].strip().split()
        if tail and tail[0] == "Z":
            return False
    except OSError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def proc_table() -> Dict[int, int]:
    table: Dict[int, int] = {}
    for process in psutil.process_iter(["pid", "ppid"]):
        try:
            table[process.pid] = process.info["ppid"]
        except psutil.Error:
            continue
    return table


def descendant_pids(root_pid: int) -> List[int]:
    table = proc_table()
    children: Dict[int, List[int]] = {}
    for pid, ppid in table.items():
        children.setdefault(ppid, []).append(pid)
    found: List[int] = []
    stack = list(children.get(root_pid, []))
    while stack:
        pid = stack.pop()
        found.append(pid)
        stack.extend(children.get(pid, []))
    return found


def proc_matches_path(pid: int, root: Path) -> bool:
    marker = str(root.resolve())
    try:
        process = psutil.Process(pid)
        cmdline = " ".join(process.cmdline())
        # Match a path boundary, never an adjacent similarly named task directory.
        if re.search(r"(?<![\w./-])" + re.escape(marker) + r"(?=$|[/\s'\"])", cmdline):
            return True
        cwd = Path(process.cwd()).resolve()
        root_resolved = root.resolve()
        return cwd == root_resolved or root_resolved in cwd.parents
    except (psutil.Error, OSError):
        return False


def filtered_victim_pids(pids: Iterable[int]) -> List[int]:
    own_pid = os.getpid()
    protected = {own_pid, os.getppid()}
    return sorted({pid for pid in pids if pid not in protected}, reverse=True)


def signal_pids(pids: Iterable[int], sig: signal.Signals = signal.SIGTERM) -> List[int]:
    victims = filtered_victim_pids(pids)
    for pid in victims:
        if not pid_is_alive(pid):
            continue
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass
    return victims


def pids_matching_path(root: Path) -> List[int]:
    pids: List[int] = []
    for process in psutil.process_iter(["pid"]):
        pid = process.pid
        if proc_matches_path(pid, root):
            pids.append(pid)
    return pids


def terminate_pids(pids: Iterable[int], *, grace_seconds: float = 1.0) -> List[int]:
    victims = filtered_victim_pids(pids)
    if not victims:
        return []

    for sig in (signal.SIGTERM, signal.SIGKILL):
        signal_pids(victims, sig)
        deadline = time.time() + grace_seconds
        while time.time() < deadline:
            if not any(pid_is_alive(pid) for pid in victims):
                break
            time.sleep(0.05)
    return victims


def terminate_processes_for_path(root: Path) -> List[int]:
    return terminate_pids(pids_matching_path(root))


def terminate_process_tree(pid: Optional[int]) -> List[int]:
    if not pid:
        return []
    return terminate_pids(descendant_pids(pid) + [pid])


def attempt_process_pids(process: multiprocessing.Process, attempt_root: Path) -> List[int]:
    pids: List[int] = []
    if process.pid:
        pids.extend(descendant_pids(process.pid))
        pids.append(process.pid)
    pids.extend(pids_matching_path(attempt_root))
    return filtered_victim_pids(pids)


def request_attempt_stop(process: multiprocessing.Process, attempt_root: Path) -> List[int]:
    return signal_pids(attempt_process_pids(process, attempt_root), signal.SIGTERM)


def cleanup_attempt_root(attempt_root: Path, dp_root: Path) -> Dict[str, Any]:
    result = {"attempt_dir": str(attempt_root), "attempt_dir_removed": False, "scratch_removed": []}
    try:
        resolved = attempt_root.resolve()
        dp_resolved = dp_root.resolve()
        if resolved != dp_resolved and dp_resolved in resolved.parents and resolved.exists():
            # Audit candidates, calls, results and harness logs are never scratch.
            for name in ('scratch', 'build', '.scratch', '.build'):
                scratch = resolved / name
                if scratch.is_dir() and not scratch.is_symlink():
                    ensure_under(scratch, resolved, 'scratch')
                    shutil.rmtree(scratch)
                    result['scratch_removed'].append(str(scratch))
    except OSError as exc:
        result["cleanup_error"] = str(exc)
    return result


def first_pass_claim_path(dp_root: Path) -> Path:
    return dp_root / "first_pass_claim.json"


def validate_evaluation_artifacts(*, candidate_path, manifest_path, evaluation_path,
                                  required_services=(), require_pass=True, expected_hash=None,
                                  task_id=None):
    """Bind complete native evaluator tests to the exact archived candidate bytes."""
    from ace_rtl_agent.decision.types import canonical_hash, validate_target
    from ace_rtl_agent.decision.observations import validate_result
    candidate_path, manifest_path, evaluation_path = map(Path, (candidate_path, manifest_path, evaluation_path))
    manifest_bytes = manifest_path.read_bytes()
    evaluation_bytes = evaluation_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    evaluation = json.loads(evaluation_bytes)
    if not isinstance(manifest, dict) or not isinstance(evaluation, dict):
        raise ValueError('artifacts must be objects')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files or any(not isinstance(v, str) for v in files.values()):
        raise ValueError('manifest needs nonempty candidate files')
    generated = manifest.get('generated_files')
    if generated is not None:
        if not isinstance(generated, dict) or set(generated) != set(files):
            raise ValueError('generated file targets differ from bundle')
        generated = {name: ensure_under(Path(path), manifest_path.parent, 'archived candidate')
                     for name, path in generated.items()}
        if candidate_path.is_file() and candidate_path.resolve() not in generated.values():
            raise ValueError('primary candidate is outside generated manifest')
    if manifest.get('mutable_targets') is not None and set(manifest['mutable_targets']) != set(files):
        raise ValueError('incomplete mutable target bundle')
    hashes = {}
    for name, content in files.items():
        validate_target(name)
        target = generated[name] if generated is not None else (candidate_path / name if candidate_path.is_dir() else candidate_path)
        if generated is None and not candidate_path.is_dir() and len(files) != 1:
            raise ValueError('multifile candidate needs directory')
        if generated is None and candidate_path.is_dir():
            ensure_under(target, candidate_path, 'candidate file')
        data = target.read_bytes()
        if data != content.encode('utf-8'):
            raise ValueError('candidate bytes differ from manifest')
        hashes[name] = hashlib.sha256(data).hexdigest()
    digest = canonical_hash(files)
    if any(manifest.get(key) != digest for key in ('candidate_id', 'tested_hash')):
        raise ValueError('candidate bundle hash mismatch')
    normalized=manifest.get('normalized_files',files)
    if not isinstance(normalized,dict) or manifest.get('normalized_hash')!=canonical_hash(normalized):
        raise ValueError('normalized provenance hash mismatch')
    if manifest.get('file_hashes') != hashes or (expected_hash and expected_hash != digest):
        raise ValueError('candidate file hash mismatch')
    if evaluation.get('tested_hash') != digest:
        raise ValueError('evaluation hash not bound to candidate')
    if task_id is not None:
        evaluation_task = evaluation.get('task_id', evaluation.get('id'))
        manifest_task = manifest.get('task_id')
        if evaluation_task is None and manifest_task is None:
            raise ValueError('task identity missing from artifacts')
        if any(value is not None and value != task_id for value in (evaluation_task, manifest_task)):
            raise ValueError('evaluation task mismatch')
    if validate_result(evaluation, required_services, digest):
        raise ValueError('invalid evaluator result')
    if require_pass and evaluation.get('errors') != 0:
        raise ValueError('evaluator did not pass')
    if evaluation.get('evaluation_validity', 'valid') != 'valid':
        raise ValueError('evaluation validity is not valid')
    return {'tested_hash': digest, 'manifest_hash': hashlib.sha256(manifest_bytes).hexdigest(),
            'evaluation_hash': hashlib.sha256(evaluation_bytes).hexdigest()}


def try_claim_first_pass(
    *,
    dp_root: Path,
    task_id: str,
    attempt_index: int,
    iteration: int,
    candidate_path: Path,
    evaluation_path: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    required_services: Iterable[str] = (),
) -> bool:
    # Legacy callers remain callable but cannot mint success without authoritative artifacts.
    if evaluation_path is None or manifest_path is None:
        return False
    claim_path = first_pass_claim_path(dp_root)
    payload = {
        "id": task_id,
        "attempt": attempt_index,
        "iteration": iteration,
        "candidate_path": str(candidate_path),
        "claimed_at": now_stamp(),
        "pid": os.getpid(),
        "schema_version": "ace-winner-1",
        "evaluation_path": str(Path(evaluation_path).resolve()),
        "manifest_path": str(Path(manifest_path).resolve()),
        "required_services": list(required_services),
    }
    payload['candidate_path'] = str(Path(candidate_path).resolve())
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    # Never unlink the lock inode. OS locks are released after writer death.
    with (dp_root / 'first_pass_claim.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if read_first_pass_claim(dp_root) is not None:
            return False
        try:
            payload.update(validate_evaluation_artifacts(candidate_path=candidate_path,
                manifest_path=manifest_path, evaluation_path=evaluation_path,
                required_services=payload['required_services'], task_id=task_id))
        except (OSError, ValueError, TypeError, KeyError):
            return False
        # Preserve corrupt/partial claims as audit evidence, then recover ownership.
        if claim_path.exists():
            os.replace(claim_path, claim_path.with_name('invalid_claim_' + uuid.uuid4().hex + '.json'))
        # Make the referenced artifacts durable before publishing the complete claim.
        manifest = json.loads(Path(manifest_path).read_text())
        generated = manifest.get('generated_files')
        candidate_files = list(generated.values()) if generated else [
            Path(candidate_path) / name if Path(candidate_path).is_dir() else candidate_path
            for name in manifest['files']]
        for artifact in (manifest_path, evaluation_path, *candidate_files):
            with Path(artifact).open('rb') as stream:
                os.fsync(stream.fileno())
        for directory in {Path(p).parent for p in (manifest_path, evaluation_path, *candidate_files)}:
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        from ace_rtl_agent.decision.ledger import durable_json
        durable_json(claim_path, payload)
        return True


def read_first_pass_claim(dp_root: Path) -> Optional[Dict[str, Any]]:
    claim_path = first_pass_claim_path(dp_root)
    if not claim_path.exists():
        return None
    try:
        payload = json.loads(claim_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get('schema_version') != 'ace-winner-1':
            return None
        if type(payload.get('attempt')) is not int or type(payload.get('iteration')) is not int:
            return None
        if not isinstance(payload.get('id'), str) or not isinstance(payload.get('required_services'), list):
            return None
        hashes = validate_evaluation_artifacts(candidate_path=Path(payload['candidate_path']),
            manifest_path=Path(payload['manifest_path']), evaluation_path=Path(payload['evaluation_path']),
            required_services=payload['required_services'], task_id=payload['id'])
        if any(payload.get(key) != value for key, value in hashes.items()):
            return None
    except (OSError, ValueError, TypeError, KeyError):
        return None
    return payload


def map_container_path(text: str, issue_path: Path) -> str:
    replacements = {
        "/code/rundir": issue_path / "rundir",
        "/code/verif": issue_path / "verif",
        "/code/docs": issue_path / "docs",
        "/code/rtl": issue_path / "rtl",
        "/code/src": issue_path / "src",
        "/rundir": issue_path / "rundir",
        "/src": issue_path / "src",
        "/code": issue_path,
    }
    pattern = re.compile("|".join(re.escape(key) for key in replacements))
    return pattern.sub(lambda match: str(replacements[match.group(0)]), text)


def compose_command(command: Any, issue_path: Path) -> str:
    if isinstance(command, list):
        mapped = [map_container_path(str(part), issue_path) for part in command]
        return " ".join(shlex.quote(part) for part in mapped)
    return map_container_path(str(command), issue_path)


def prepend_env_paths(paths: Iterable[Path]) -> List[str]:
    existing = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    preferred: List[str] = []
    for path in paths:
        text = str(path)
        if path.exists() and text not in preferred:
            preferred.append(text)
    if preferred:
        remainder = [entry for entry in existing if entry not in preferred]
        os.environ["PATH"] = os.pathsep.join(preferred + remainder)
    return preferred


def detect_cadence_license_environment() -> Dict[str, Any]:
    env_state = {
        name: bool(os.environ.get(name))
        for name in CADENCE_LICENSE_ENV_VARS
    }
    configured = any(env_state.values())
    return {
        "configured": configured,
        "env_present": env_state,
        "message": (
            "Cadence/license environment variables are present"
            if configured
            else "No common EDA license environment variables are set"
        ),
    }
