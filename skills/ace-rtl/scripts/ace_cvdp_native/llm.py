# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ACE-RTL native CVDP runner internals."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

from ace_rtl_agent.focused_debugger import FocusedDebugger
from ace_rtl_agent.fresh_start_coordinator import FreshStartCoordinator
from .config import *
from .sv import *
from .diagnostics import *
from .processes import write_json
from ace_rtl_agent.decision.types import CandidateBundle, TaskContract, validate_target
from extract_solution import extract_code, split_target_files, load_text

def run_role_call(
    *,
    workspace: Path,
    component: str,
    model: str,
    system: str,
    prompt: str,
    out_json: Path,
    timeout: int,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> str:
    from ace_rtl_agent.decision.budget import Deadline
    remaining = Deadline.from_env().timeout(timeout)
    prompt_path = out_json.with_suffix(".prompt.txt")
    stdout_path = out_json.with_suffix(".stdout.txt")
    prompt_path.write_text(prompt, encoding="utf-8")
    cmd = [
        sys.executable,
        str(workspace / "skills/ace-rtl/scripts/llm_call.py"),
        "--component",
        component,
        "--model",
        model,
        "--system",
        system,
        "--prompt-file",
        str(prompt_path),
        "--output",
        str(out_json),
        "--timeout",
        str(timeout),
        "--temperature",
        str(temperature),
    ]
    env = os.environ.copy()
    if max_tokens:
        cmd.extend(['--max-tokens',str(max_tokens)])
    env["PYTHONNOUSERSITE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(workspace),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=remaining,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"{component} LLM call failed; see {stdout_path}")
    return load_response_content(out_json)


class AceIterationModel:
    def __init__(
        self,
        *,
        workspace: Path,
        iteration_dir: Path,
        cid: str,
        generator_model: str,
        llm_timeout: int,
        reflection: str,
        coordinator: str,
        previous_candidate: Optional[Any],
        task_contract: Optional[TaskContract] = None,
        episode_id: str = 'episode-1',
        generator_output_tokens: Optional[int] = None,
    ) -> None:
        self.workspace = workspace
        self.iteration_dir = iteration_dir
        self.cid = cid
        self.generator_model = generator_model
        self.llm_timeout = llm_timeout
        self.reflection = reflection
        self.coordinator = coordinator
        self.previous_candidate = previous_candidate
        self.requires_evaluation = True
        self.generated_files: Dict[str, str] = {}
        self.preflight_issues: List[str] = []
        self.postprocess_actions: List[str] = []
        self.task_contract = task_contract
        self.episode_id = episode_id
        self.bundle: Optional[CandidateBundle] = None
        self.generator_output_tokens = generator_output_tokens

    def prompt(
        self,
        prompt: str,
        schema: str = None,
        prompt_log: str = "",
        files: Optional[List[str]] = None,
        timeout: int = 60,
        category: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        files = files or []
        if not files:
            raise ValueError("ACE-RTL runner expected at least one target file")
        files = [validate_target(name) for name in files]
        if self.task_contract and set(files) != set(self.task_contract.mutable_targets):
            raise ValueError('processor targets differ from declared mutable manifest')

        self.iteration_dir.mkdir(parents=True, exist_ok=True)
        if prompt_log:
            Path(prompt_log).parent.mkdir(parents=True, exist_ok=True)

        target_file = files[0]
        candidate_root = self.iteration_dir / "candidate"
        candidate_path = candidate_root / target_file
        candidate_path.parent.mkdir(parents=True, exist_ok=True)

        previous = format_candidate_bundle(files, self.previous_candidate)
        task_kind = self.task_contract.task_kind if self.task_contract else classify_task(target_file, prompt)
        task_guidance = guidance_for_task(task_kind)
        response_label = response_label_for_task(task_kind, target_file, files)
        target_file_list = "\n".join(f"- {name}" for name in files)
        if len(files) > 1:
            output_contract = (
                "Return every target file listed above as a complete replacement. "
                "Use one section per file headed exactly by `// TARGET_FILE: <path>`, "
                "where `<path>` matches the target file path. Do not omit unchanged "
                "targets, do not add undeclared target files, and do not return a patch."
            )
        else:
            output_contract = (
                f"Return the complete {response_label} only. Do not include JSON or commentary."
            )
            if task_kind in ('rtl','rtl_implementation') and Path(target_file).suffix in ('.sv','.v'):
                public_initial = self.task_contract.initial_targets.get(target_file,'') if self.task_contract else ''
                header = re.search(r'\bmodule\s+([A-Za-z_][\w$]*)\s*(?:#\s*\(|\()',public_initial or prompt)
                module_name = Path(target_file).stem
                output_contract += f' Expose module name `{module_name}` for the public target basename.'
                if header and header.group(1)!=module_name:
                    output_contract += f' Preserve the specified module `{header.group(1)}` and its public interface; provide a same-interface wrapper named `{module_name}` when needed, within this declared target file.'
        full_prompt = f"""\
{prompt}

ACE-RTL task guidance:
{task_guidance}

Target file(s):
{target_file_list}

Coordinator guidance:
{self.coordinator}

Reflector guidance:
{self.reflection}

Previous candidate, if any:
```systemverilog
{previous}
```

{output_contract}
"""
        system = system_prompt_for_task(task_kind, multi_file=len(files) > 1)
        if prompt_log:
            Path(prompt_log).write_text(system + "\n\n" + full_prompt, encoding="utf-8")

        response_json = self.iteration_dir / "generator.response.json"
        run_role_call(
            workspace=self.workspace,
            component="generator",
            model=self.generator_model,
            system=system,
            prompt=full_prompt,
            out_json=response_json,
            timeout=self.llm_timeout,
            max_tokens=self.generator_output_tokens,
        )

        # Validate the complete output manifest before writing any model-chosen path.
        extracted = extract_code(load_text(str(response_json)))
        sections = split_target_files(extracted)
        if not sections and len(files) == 1:
            sections = {target_file: extracted.rstrip() + '\n'}
        for name in sections:
            try:
                validate_target(name)
                if name not in files:
                    raise ValueError('undeclared target')
            except ValueError:
                self.preflight_issues.append('generator response contains unsafe or undeclared target')
        if not any('undeclared target' in issue for issue in self.preflight_issues):
            for name, content in sections.items():
                path = candidate_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')

        missing_targets = [name for name in files if not (candidate_root / name).exists()]
        if missing_targets:
            self.preflight_issues.extend(
                f"generator response omitted declared target file: {name}"
                for name in missing_targets
            )

        normalized_contents: Dict[str, str] = {}
        raw_contents: Dict[str, str] = {}
        file_actions: List[str] = []
        for name in files:
            path = candidate_root / name
            if not path.exists():
                continue
            raw_code = path.read_text(encoding="utf-8", errors="replace")
            raw_contents[name] = raw_code
            code, actions = normalize_generated_sv(raw_code)
            if code != raw_code:
                raw_path = path.with_suffix(path.suffix + ".raw")
                raw_path.write_text(raw_code, encoding="utf-8")
                path.write_text(code, encoding="utf-8")
            normalized_contents[name] = code
            file_actions.extend(f"{name}: {action}" for action in actions)
            self.preflight_issues.extend(
                f"{name}: {issue}" for issue in high_confidence_candidate_issues(code, self.cid)
            )
            self.generated_files[name] = str(path)

        self.postprocess_actions.extend(file_actions)
        if target_file not in normalized_contents:
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            candidate_path.write_text("", encoding="utf-8")
            normalized_contents[target_file] = ""
            self.generated_files[target_file] = str(candidate_path)

        code = normalized_contents[target_file]
        self.bundle = CandidateBundle.create(normalized_contents, episode_id=self.episode_id,
                     raw_files=raw_contents, normalization_actions=self.postprocess_actions)
        write_json(
            self.iteration_dir / "postprocess_result.json",
            {
                "target_file": target_file,
                "target_files": files,
                "candidate_hash": candidate_hash(code),
                "candidate_bundle_hash": candidate_bundle_hash(normalized_contents),
                "file_hashes": {
                    name: candidate_hash(content)
                    for name, content in sorted(normalized_contents.items())
                },
                "generated_files": self.generated_files,
                "actions": self.postprocess_actions,
                "preflight_issues": self.preflight_issues,
                "provenance": self.bundle.to_dict(),
            },
        )
        if len(files) == 1:
            return {"direct_text": code}, True
        return {"code": [{name: normalized_contents[name]} for name in files if name in normalized_contents]}, True


def role_api_key() -> Optional[str]:
    return os.environ.get("NVIDIA_API_KEY")


def bind_prepared_candidate(model, prepared_root, targets, *, iteration_dir, episode_id, parent=None):
    """Archive only declared mutable files as actually materialized by CVDP.

    Repository.restore_files applies template substitution; model output is not
    by itself evidence of the bytes passed to the evaluator.
    """
    from dataclasses import replace
    normalized = read_generated_candidate_files(model.generated_files)
    original = getattr(model,'bundle',None)
    raw = dict(original.raw_files) if original else {
        name:Path(path).with_suffix(Path(path).suffix+'.raw').read_text()
        if Path(path).with_suffix(Path(path).suffix+'.raw').exists() else normalized[name]
        for name,path in model.generated_files.items()}
    if model.preflight_issues:
        return CandidateBundle.create(normalized,episode_id=episode_id,parent=parent,raw_files=raw,
                                      normalization_actions=model.postprocess_actions)
    root=Path(prepared_root).resolve()
    tested={}
    archive=Path(iteration_dir)/'tested_candidate'
    for name in targets:
        validate_target(name)
        source=(root/name).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise RuntimeError('INFRA_SETUP: prepared mutable target missing or outside manifest')
        tested[name]=source.read_text(encoding='utf-8')
        destination=archive/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(tested[name],encoding='utf-8')
        if tested[name]!=normalized.get(name):
            model.postprocess_actions.append(f'{name}: CVDP preparation changed normalized candidate bytes')
        model.generated_files[name]=str(destination)
    bundle=CandidateBundle.create(tested,episode_id=episode_id,parent=parent,raw_files=raw,
                                  normalization_actions=model.postprocess_actions)
    from ace_rtl_agent.decision.types import canonical_hash
    return replace(bundle,normalized_hash=canonical_hash(normalized),normalized_files=normalized)


def sanitize_model_diagnostics(text: str) -> str:
    """Keep emitted failure messages, not pytest's hidden checker source excerpts."""
    lines = []
    python_excerpt=False
    for line in str(text).splitlines():
        stripped = line.lstrip()
        if stripped.startswith('def ') or re.search(r'File ["\'].*\.py["\'], line \d+',stripped):
            python_excerpt=True
            continue
        if stripped.startswith('E '):
            message=re.sub(r'^E\s+','',stripped)
            if not re.match(r'[\w.]+(?:Error|Exception):',message):
                continue
        elif python_excerpt and line[:1].isspace() and stripped:
            continue
        elif stripped.startswith(('===','---','___','# ')):
            python_excerpt=False
        if stripped.startswith('>') or re.match(r'^(?:E\s+)?(?:def |assert |expected\s*=|reference\s*=|golden\s*=)', stripped):
            continue
        if re.search(r'(?:api[_ -]?key|authorization|password|access[_ -]?token)\s*[=:]',line,re.I):
            lines.append('[credential-bearing diagnostic withheld]')
            continue
        if re.search(r'private_reference|mutation_definition|hidden_checker',line,re.I):
            continue
        lines.append(line)
    cleaned = '\n'.join(lines)
    for name,value in os.environ.items():
        if value and (name.endswith(('API_KEY','PASSWORD','ACCESS_TOKEN')) or name=='NVIDIA_API_KEY'):
            cleaned = cleaned.replace(value,'[REDACTED]')
    return cleaned


def diagnostic_error_candidates(text: str, *, service_ids=()) -> Dict[str, Any]:
    """Stable symptom IDs from emitted messages, not causes or test-count metrics."""
    from ace_rtl_agent.decision.types import canonical_hash
    result = {}
    for line in sanitize_model_diagnostics(text).splitlines():
        if re.search(r'AssertionError:|(?:syntax|elaboration|width)\s+(?:error|mismatch)|\b(?:ERROR|Error):|cocotb\.regression.*failed',line):
            message = re.sub(r'\s+',' ',line.strip())[:500]
            identity = 'symptom-' + canonical_hash([tuple(service_ids),message])[:20]
            result[identity] = {'message':message,'services':tuple(service_ids),'cause_verified':False,
                                'source':'sanitized_emitted_diagnostic'}
            if len(result) >= 16:
                break
    return result


def build_evaluator_error_report(result: Dict[str, Any], summary: str) -> str:
    parts = [
        "# CVDP evaluator summary",
        "```json",
        summary,
        "```",
    ]
    remaining = MAX_REPORT_BYTES
    native_reserve = min(NATIVE_RUNDIR_REPORT_RESERVE_BYTES, MAX_REPORT_BYTES // 4)
    native_rundirs: List[Path] = []
    for idx, test in enumerate(result.get("tests", []), start=1):
        if not isinstance(test, dict):
            continue
        header = (
            f"\n# Service result {idx}: result={test.get('result')} "
            f"execution={test.get('execution')} log={test.get('log')}"
        )
        parts.append(header)
        remaining -= len(header.encode("utf-8", errors="replace"))
        error_msg = test.get("error_msg")
        if error_msg:
            block = f"\nerror_msg: {error_msg}\n"
            parts.append(block)
            remaining -= len(block.encode("utf-8", errors="replace"))
        raw_log = test.get("log")
        if remaining <= 0 or not raw_log:
            continue
        log_path = Path(raw_log)
        if not log_path.exists():
            continue
        try:
            available_for_log = remaining - native_reserve
            if available_for_log < 4096:
                available_for_log = remaining
            log_budget = max(0, min(MAX_SERVICE_LOG_BYTES, available_for_log, remaining))
            if log_budget <= 0:
                continue
            text = read_bounded_text(log_path, log_budget)
        except OSError as exc:
            text = f"[could not read evaluator log: {exc}]"
        native_rundirs.extend(rundir_candidates_from_service_log(log_path, text))
        parts.append("\n```text\n")
        parts.append(text)
        parts.append("\n```")
        remaining -= len(text.encode("utf-8", errors="replace"))
    native_diagnostics = collect_native_rundir_diagnostics(native_rundirs, remaining)
    if native_diagnostics:
        parts.append(native_diagnostics)
    return sanitize_model_diagnostics("\n".join(parts))


def build_reflector_harness_context(
    harness_dir: Optional[Path],
    target_file: str,
    max_total_chars: int = 90000,
    *,
    mutable_targets: Optional[Iterable[str]] = None,
    public_context: Optional[Dict[str, str]] = None,
) -> str:
    """Only dataset-declared public context is eligible, never harness internals.

    The harness directory is retained for legacy call compatibility, not read.
    Context size is a character cap, explicitly not a token measurement.
    """
    mutable = set(mutable_targets or [target_file])
    parts = ['# Declared public immutable context (character-bounded)']
    total = len(parts[0])
    for name, content in sorted((public_context or {}).items()):
        validate_target(name)
        if name in mutable or name.endswith('.env'):
            continue
        block = f'\n# Public context file: {name}\n{content}\n'
        remaining = max_total_chars - total
        if remaining <= 0:
            break
        parts.append(block[:remaining])
        total += min(len(block), remaining)
    return '\n'.join(parts) if len(parts) > 1 else ''


def call_reflector(
    focused_debugger: FocusedDebugger,
    iteration_dir: Path,
    task_id: str,
    target_file: str,
    candidate: str,
    error_report: str,
    iteration: int,
    specification: str,
    harness_context: str,
    *,
    candidate_files: Optional[Dict[str, str]] = None,
    task_contract: Optional[TaskContract] = None,
    observation=None,
    bundle=None,
    action=None,
    evidence=(),
    best=None,
) -> Tuple[str, Dict[str, Any]]:
    if task_contract:
        focused_debugger.task_contract = task_contract
    bundle_text = format_candidate_bundle(list(candidate_files), candidate_files) if candidate_files else candidate
    if action and action.action_kind == 'reflect_deep':
        workspace = Path(__file__).resolve().parents[4]
        prompt = json.dumps({'contract':task_contract.to_dict(),'candidate_files':candidate_files,
            'diagnostics':sanitize_model_diagnostics(error_report),'focus':action.to_dict()},ensure_ascii=False)
        raw = run_role_call(workspace=workspace,component='reflector',model=focused_debugger.model_name,
            system='Analyze only this public evidence. Return JSON with analysis and guidance strings. Do not generate RTL or assert benchmark success.',
            prompt=prompt,out_json=iteration_dir/'reflector.deep.response.json',timeout=env_int('ACE_RTL_LLM_TIMEOUT',60),
            max_tokens=getattr(getattr(focused_debugger,'llm_client',None),'max_output_tokens',None))
        try:
            analysis = json.loads(raw)
            if not isinstance(analysis,dict) or not all(isinstance(analysis.get(k),str) for k in ('analysis','guidance')):
                raise ValueError('invalid deep reflection')
        except (ValueError,TypeError):
            analysis = {'analysis':raw,'guidance':'Use the public analysis above to repair all declared targets.'}
        content = json.dumps({'focus':action.error_id,'analysis':analysis['analysis'],'guidance':analysis['guidance'],
                  'constraints':{'task_kind':task_contract.task_kind,'mutable_targets':task_contract.mutable_targets}},ensure_ascii=False)
        metadata = {'approach':'structured','action_kind':'reflect_deep','task_id':task_id,
                    'target_files':list(candidate_files),'task_kind':task_contract.task_kind}
        write_json(iteration_dir/'reflector.response.json',{'content':content,'metadata':metadata})
        return content,metadata
    focused_prompt, focused_error, fix_guidance = focused_debugger.create_focused_prompt(
        buggy_code=bundle_text,
        error_report=error_report,
        iteration=iteration,
        specification=specification,
        testbench_code=harness_context or None,
        context_code=None,
        per_signal_mismatches=None,
    )
    metadata = {
        "approach": "focused",
        "component": "FocusedDebugger.create_focused_prompt",
        "task_id": task_id,
        "target_file": target_file,
        "target_files": list(candidate_files or {target_file: candidate}),
        "task_kind": task_contract.task_kind if task_contract else None,
        "iteration": iteration,
        "focused_error": focused_error,
        "guidance": fix_guidance,
        "harness_context_chars": len(harness_context or ""),
        'action_kind': action.action_kind if action else 'reflect_focused',
    }
    content = f"""\
Focused error:
{focused_error}

Fix guidance:
{fix_guidance}

Constraints:
Preserve the canonical task and every declared mutable target. Generate the complete bundle.
"""
    if observation is not None and bundle is not None and hasattr(focused_debugger,'create_reflection'):
        structured = focused_debugger.create_reflection(observation,task_contract,bundle,action=action,evidence=evidence,
                       guidance=fix_guidance,history=focused_debugger.fix_history,best=best)
        content = json.dumps(structured,ensure_ascii=False)
        metadata['approach'] = 'structured'
        metadata['context_selection'] = structured['context_selection']
    (iteration_dir / "reflector.response.prompt.txt").write_text(
        focused_prompt, encoding="utf-8", errors="replace"
    )
    write_json(
        iteration_dir / "reflector.response.json",
        {
            "content": content,
            "metadata": metadata,
            "focused_error": focused_error,
            "fix_guidance": fix_guidance,
        },
    )
    return content, metadata


def record_reflector_iteration_result(
    focused_debugger: FocusedDebugger,
    iteration: int,
    error_report: str,
    metadata: Optional[Dict[str, Any]],
    passed: bool,
    code_before: str,
    code_after: str,
) -> None:
    if not metadata or metadata.get("approach") != "focused":
        return

    num_passing, num_total = focused_debugger.parse_test_results(error_report)
    test_results = f"{num_passing}/{num_total} tests passed"
    if passed:
        outcome = "solved"
    elif focused_debugger.fix_history:
        previous = focused_debugger.fix_history[-1]
        try:
            previous_passing = int(previous.test_results.split("/", 1)[0])
        except (ValueError, IndexError):
            previous_passing = num_passing
        if num_passing > previous_passing:
            outcome = "improved"
        elif num_passing < previous_passing:
            outcome = "regressed"
        else:
            outcome = "no_change"
    else:
        outcome = "no_change"

    guidance = str(metadata.get("guidance", ""))
    focused_error = str(metadata.get("focused_error", "Unknown error"))
    if code_before.strip() and code_after.strip():
        implementation_changes, fix_effectiveness = focused_debugger.extract_implementation_changes(
            code_before=code_before,
            code_after=code_after,
            guidance=guidance,
            focused_error=focused_error,
            new_error_report=error_report,
        )
    else:
        implementation_changes = "Code changes not tracked"
        fix_effectiveness = "Effectiveness not analyzed"
    focused_debugger.record_attempt(
        iteration=iteration,
        focused_error=focused_error,
        error_reasoning=str(metadata.get("error_reasoning", "")),
        guidance=guidance,
        implementation_changes=implementation_changes,
        fix_effectiveness=fix_effectiveness,
        test_results=test_results,
        outcome=outcome,
        test_passed=passed,
        mismatch_count=-1,
    )


def call_coordinator(
    fresh_start_coordinator: FreshStartCoordinator,
    iteration_dir: Path,
    iteration: int,
    passed: bool,
    candidate: str,
    error_report: str,
) -> Tuple[str, Optional[str]]:
    fresh_start_coordinator.add_iteration_result(
        iteration=iteration,
        test_passed=passed,
        error_report=error_report,
        rtl_code=candidate,
        mismatch_count=-1,
    )
    should_restart, reason = fresh_start_coordinator.should_fresh_start(iteration)
    content = (
        "FreshStartCoordinator decision:\n"
        f"- decision: {'fresh_start' if should_restart else 'continue'}\n"
        f"- reason: {reason}\n\n"
        "Next generator instruction:\n"
        + (
            "Start from the public specification again. Do not preserve the previous "
            "candidate structure, and do not carry forward local reflector repair steps. "
            "Use only the public specification, module interface, tool compatibility "
            "requirements, and the generic failure class described in the restart reason."
            if should_restart
            else "Revise the current candidate using the reflector's focused error and fix guidance."
        )
    )
    (iteration_dir / "coordinator.response.prompt.txt").write_text(
        "FreshStartCoordinator.should_fresh_start was called with the accumulated "
        "iteration history and the latest evaluator report.\n\n"
        f"Latest evaluator report:\n{error_report}",
        encoding="utf-8",
        errors="replace",
    )
    write_json(
        iteration_dir / "coordinator.response.json",
        {
            "content": content,
            "component": "FreshStartCoordinator.should_fresh_start",
            "decision": "fresh_start" if should_restart else "continue",
            "reason": reason,
            "restart_summary": fresh_start_coordinator.get_restart_summary(),
        },
    )
    return content, reason if should_restart else None
