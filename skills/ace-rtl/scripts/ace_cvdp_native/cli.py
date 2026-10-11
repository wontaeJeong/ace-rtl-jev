# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ACE-RTL native CVDP runner internals."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import inspect
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

from .config import *
from .processes import *
from .harness import *
from .sv import *
from .diagnostics import *
from .llm import *


def select_generation_processor_class(dataset_processor):
    """Find the CVDP dataset processor used for LLM-driven generation."""
    base_processor = getattr(dataset_processor, "DatasetProcessor", None)
    agentic_processor = getattr(dataset_processor, "AgenticProcessor", None)
    required_args = {"filename", "golden", "threads", "debug", "host", "prefix"}
    preferred_args = {"network_name", "manage_network"}
    candidates = []

    for name in dir(dataset_processor):
        value = getattr(dataset_processor, name)
        if not isinstance(value, type):
            continue
        if value in {base_processor, agentic_processor}:
            continue
        if not name.endswith("Processor"):
            continue

        try:
            signature = inspect.signature(value)
        except (TypeError, ValueError):
            try:
                signature = inspect.signature(value.__init__)
            except (TypeError, ValueError):
                continue

        params = signature.parameters
        has_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values())
        if has_kwargs or required_args.issubset(params):
            score = len(required_args.intersection(params)) + len(preferred_args.intersection(params)) * 2
            if has_kwargs:
                score += 1
            candidates.append((score, name, value))

    if not candidates:
        raise AttributeError("No compatible CVDP generation processor class found")

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _legacy_run_attempt(
    *,
    workspace: Path,
    cvdp_repo: Path,
    row: Dict[str, Any],
    row_jsonl: Path,
    attempt_root: Path,
    attempt_index: int,
    args: argparse.Namespace,
    stop_event: Any,
) -> Dict[str, Any]:
    sys.path.insert(0, str(cvdp_repo))
    install_native_harness_patch()
    from src import dataset_processor

    task_id = row["id"]
    target_files = list(row["output"]["context"].keys())
    target_file = target_files[0]
    input_data = row.get("input") or {}
    specification_parts = [str(input_data.get("prompt", ""))]
    input_context = input_data.get("context") or {}
    if isinstance(input_context, dict):
        for name, content in input_context.items():
            specification_parts.append(f"\n# Context file: {name}\n```systemverilog\n{content}\n```")
    specification = "\n".join(part for part in specification_parts if part)

    logger = logging.getLogger(f"ace_cvdp_native_runner.{task_id}.attempt{attempt_index}")
    focused_debugger = FocusedDebugger(
        logger,
        model_name=args.reflector_model,
        api_key=role_api_key(),
        max_retries=3,
        initial_backoff=5.0,
    )
    fresh_start_coordinator = FreshStartCoordinator(
        args.coordinator_model,
        logger,
        api_key=role_api_key(),
        max_retries=3,
        initial_backoff=5.0,
    )
    fresh_start_coordinator.focused_debugger = focused_debugger

    previous_candidates: Dict[str, str] = {}
    reflection = "Initial generation. No evaluator feedback is available yet."
    coordinator = "Generate a complete implementation from the public prompt and context."
    reflection_metadata: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = []
    previous_candidate_hash: Optional[str] = None

    for iteration in range(1, args.max_iterations + 1):
        if stop_event.is_set():
            return {
                "attempt": attempt_index,
                "status": "stopped_after_sibling_pass",
                "history": history,
            }

        iteration_dir = attempt_root / f"iter_{iteration:02d}"
        work_prefix = iteration_dir / "cvdp_work"
        model = AceIterationModel(
            workspace=workspace,
            iteration_dir=iteration_dir,
            cid=args.cid,
            generator_model=args.generator_model,
            llm_timeout=args.llm_timeout,
            reflection=reflection,
            coordinator=coordinator,
            previous_candidate=previous_candidates or None,
        )

        processor_cls = select_generation_processor_class(dataset_processor)
        processor = processor_cls(
            filename=str(row_jsonl),
            golden=False,
            threads=1,
            debug=False,
            host=False,
            prefix=str(work_prefix),
            network_name=None,
            manage_network=False,
        )
        # These CVDP generation categories are evaluated by executable harness
        # services; avoid constructing an unrelated subjective scorer that would
        # require a separate subjective-scoring model key.
        processor._sbj_model_config = None
        processor._sbj_model_instance = None
        processor.include_harness = False
        processor.include_golden_patch = False
        processor.process_json()
        prepared_id, obj, repo = processor.prepare(issue=task_id, model=model)
        if prepared_id != task_id:
            raise RuntimeError(f"unexpected prepared id {prepared_id} for {task_id}")
        prepared_harness_dir = Path(getattr(repo, "issue_path", "") or (work_prefix / task_id))
        fresh_start_coordinator.set_harness_directory(prepared_harness_dir)
        reflector_harness_context = build_reflector_harness_context(
            prepared_harness_dir,
            target_file,
        )

        if model.preflight_issues:
            result = make_preflight_result(model.preflight_issues, model.postprocess_actions)
            write_json(iteration_dir / "preflight_result.json", result)
        else:
            previous_native_timeout = os.environ.get("CVDP_NATIVE_TIMEOUT")
            os.environ["CVDP_NATIVE_TIMEOUT"] = str(args.evaluator_timeout)
            try:
                result = processor.run(id=task_id, obj=obj, repo=repo, model=model)
            finally:
                if previous_native_timeout is None:
                    os.environ.pop("CVDP_NATIVE_TIMEOUT", None)
                else:
                    os.environ["CVDP_NATIVE_TIMEOUT"] = previous_native_timeout
        write_json(iteration_dir / "real_evaluator_result.json", result)

        candidate_path = Path(model.generated_files[target_file])
        candidate = candidate_path.read_text(encoding="utf-8", errors="replace")
        candidate_files = read_generated_candidate_files(model.generated_files)
        current_hash = candidate_bundle_hash(candidate_files)
        candidate_changed = previous_candidate_hash is None or current_hash != previous_candidate_hash
        from ace_rtl_agent.decision.types import CandidateBundle
        from ace_rtl_agent.decision.observations import build_task_contract
        legacy_contract = build_task_contract(row,args.cid)
        legacy_bundle = CandidateBundle.create(candidate_files,episode_id='legacy')
        result = {**result,'tested_hash':legacy_bundle.tested_hash}
        write_json(iteration_dir/'real_evaluator_result.json',result)
        write_json(iteration_dir/'candidate_manifest.json',{**legacy_bundle.to_dict(),
            'generated_files':dict(model.generated_files),'mutable_targets':target_files,'task_id':task_id})
        passed = result_passed(result,required_services=legacy_contract.required_services,tested_hash=legacy_bundle.tested_hash)
        if passed:
            stop_event.set()
            if not try_claim_first_pass(
                dp_root=attempt_root.parent,
                task_id=task_id,
                attempt_index=attempt_index,
                iteration=iteration,
                candidate_path=candidate_path,
                evaluation_path=iteration_dir/'real_evaluator_result.json',
                manifest_path=iteration_dir/'candidate_manifest.json',
                required_services=legacy_contract.required_services,
            ):
                claim = read_first_pass_claim(attempt_root.parent)
                logger.info(
                    "Suppressing duplicate PASS from attempt %s because attempt %s already claimed this datapoint",
                    attempt_index,
                    claim.get("attempt") if claim else "unknown",
                )
                history.append(
                    {
                        "iteration": iteration,
                        "passed": True,
                        "result": result,
                        "summary": "suppressed duplicate pass after sibling first-pass claim",
                        "primary_failure": {
                            "stage": "PASS",
                            "message": "candidate passed after a sibling already claimed first pass",
                            "signature": "duplicate pass suppressed",
                        },
                        "candidate_hash": current_hash,
                        "candidate_changed": candidate_changed,
                        "candidate_path": str(candidate_path),
                        "suppressed_duplicate_pass": True,
                    }
                )
                return {
                    "attempt": attempt_index,
                    "status": "stopped_after_sibling_pass",
                    "winner_attempt": claim.get("attempt") if claim else None,
                    "suppressed_duplicate_pass": True,
                    "passed_iteration": iteration,
                    "candidate_path": str(candidate_path),
                    "history": history,
                }
        summary = summarize_result(result)
        primary_failure = primary_failure_from_summary(result, summary)
        error_report = build_evaluator_error_report(result, summary)
        (iteration_dir / "evaluator_error_report.txt").write_text(
            error_report, encoding="utf-8", errors="replace"
        )
        record_reflector_iteration_result(
            focused_debugger=focused_debugger,
            iteration=iteration,
            error_report=error_report,
            metadata=reflection_metadata,
            passed=passed,
            code_before=previous_candidates.get(target_file, ""),
            code_after=candidate,
        )
        history.append(
            {
                "iteration": iteration,
                "passed": passed,
                "result": result,
                "summary": summary,
                "primary_failure": primary_failure,
                "candidate_hash": current_hash,
                "candidate_changed": candidate_changed,
                "candidate_path": str(candidate_path),
                "generated_files": dict(model.generated_files),
                "evaluator_error_report": str(iteration_dir / "evaluator_error_report.txt"),
            }
        )

        print(
            f"{task_id} attempt {attempt_index} iteration {iteration}: "
            f"{'PASS' if passed else 'FAIL'} ({primary_failure['stage']})"
        )
        if passed:
            return {
                "attempt": attempt_index,
                "status": "passed",
                "passed_iteration": iteration,
                "candidate_path": str(candidate_path),
                "history": history,
            }

        if primary_failure["stage"] == "INFRA_SETUP":
            stop_event.set()
            return {
                "attempt": attempt_index,
                "status": "infra_error",
                "failed_iteration": iteration,
                "candidate_path": str(candidate_path),
                "history": history,
            }

        if stop_event.is_set():
            return {
                "attempt": attempt_index,
                "status": "stopped_after_sibling_pass",
                "history": history,
            }

        coordinator, fresh_start_hint = call_coordinator(
            fresh_start_coordinator,
            iteration_dir,
            iteration,
            passed,
            candidate,
            error_report,
        )
        if fresh_start_hint:
            focused_debugger.clear_history()
            fresh_start_coordinator.mark_fresh_start(iteration)
            reflection = (
                "Fresh start requested after repeated no-progress functional failures. "
                "Ignore the previous candidate architecture and local repair history. "
                "Re-derive a complete implementation from only the public prompt and "
                "public context. Preserve the public module interface, parameters, reset "
                "polarity, clocking, latency/protocol requirements, and target file path. "
                "Ensure every checked output is driven by an active datapath on the same "
                "cycle as its valid/done flag, not left at reset/default values."
            )
            reflection_metadata = None

        previous_candidates = {} if fresh_start_hint else candidate_files
        previous_candidate_hash = None if fresh_start_hint else current_hash
        if iteration >= args.max_iterations:
            break

        if stop_event.is_set():
            return {
                "attempt": attempt_index,
                "status": "stopped_after_sibling_pass",
                "history": history,
            }

        if fresh_start_hint:
            continue

        reflection, reflection_metadata = call_reflector(
            focused_debugger,
            iteration_dir,
            task_id,
            target_file,
            candidate,
            error_report,
            iteration,
            specification,
            reflector_harness_context,
        )

    return {
        "attempt": attempt_index,
        "status": "failed",
        "history": history,
    }


def run_attempt(
    *, workspace: Path, cvdp_repo: Path, row: Dict[str, Any], row_jsonl: Path,
    attempt_root: Path, attempt_index: int, args: argparse.Namespace, stop_event: Any,
    checkpoint_queue: Any = None, admission_event: Any = None,
) -> Dict[str, Any]:
    """Native state -> valid evaluation -> terminal gate -> bounded action loop."""
    from dataclasses import replace
    from ace_rtl_agent.decision.settings import DecisionSettings
    from ace_rtl_agent.decision.types import CandidateBundle, ProposedAction, Evidence, canonical_hash
    from ace_rtl_agent.decision.observations import build_task_contract, observe, effect
    from ace_rtl_agent.decision.ledger import EventLedger
    from ace_rtl_agent.decision.cache import EvaluationCache
    settings = DecisionSettings.from_env(getattr(args, 'decision_mode', None))
    if settings.mode == 'legacy':
        return _legacy_run_attempt(workspace=workspace, cvdp_repo=cvdp_repo, row=row,
                   row_jsonl=row_jsonl, attempt_root=attempt_root, attempt_index=attempt_index,
                   args=args, stop_event=stop_event)

    sys.path.insert(0, str(cvdp_repo))
    install_native_harness_patch()
    from src import dataset_processor
    contract = build_task_contract(row, args.cid)
    if not row.get('allowed_tools'):
        contract = replace(contract,allowed_tools=('inspect_public_artifact','retry_evaluator'))
    target_files = list(contract.mutable_targets)
    if not target_files:
        raise ValueError('task declares no mutable targets')
    if not contract.required_services:
        raise RuntimeError('INFRA_SETUP: missing expected CVDP evaluator service manifest')
    target_file = target_files[0]
    logger = logging.getLogger(f'ace_cvdp_native_runner.{contract.task_id}.attempt{attempt_index}')
    debugger = FocusedDebugger(logger, model_name=args.reflector_model, api_key=role_api_key(),
                              max_retries=3, initial_backoff=1.0)
    debugger.task_contract = contract
    coordinator_agent = FreshStartCoordinator(args.coordinator_model, logger, api_key=role_api_key(),
                                              max_retries=3, initial_backoff=1.0)
    coordinator_agent.focused_debugger = debugger
    coordinator_agent.task_contract = contract
    deadline = time.monotonic() + settings.wall_seconds
    deadline = min(deadline,getattr(args,'task_deadline',deadline),getattr(args,'run_deadline',deadline))
    os.environ['ACE_RTL_DEADLINE_MONOTONIC'] = str(deadline)
    os.environ['ACE_RTL_EVENT_ROOT'] = str(attempt_root.parent / 'events')
    os.environ['ACE_RTL_ATTEMPT_ID'] = str(attempt_index)
    os.environ['ACE_RTL_TASK_ID'] = contract.task_id
    os.environ['ACE_RTL_RUN_ID'] = str(getattr(args,'run_id',attempt_root.parent.parent.name))
    os.environ['ACE_RTL_DECISION_MODE'] = settings.mode
    ledger = EventLedger(attempt_root.parent/'events',attempt_index)
    evaluation_cache = EvaluationCache(attempt_root.parent/'evaluation_cache')
    cache_context = dict((settings.policy or {}).get('evaluation_context',{}))
    cache_context.update(task_hash=canonical_hash(row),config_hash=canonical_hash({
        'evaluator_timeout':args.evaluator_timeout,'cid':args.cid}),policy_version='evaluation-1')
    cache_context['deterministic'] = bool(settings.evaluation_cache_mode=='deterministic' and
                                           cache_context.get('determinism_verified') is True)
    # Durable paid request artifacts are never inside evaluator scratch.
    os.environ['ACE_EXPERIMENT_TELEMETRY'] = str(attempt_root.parent / 'calls' / f'attempt_{attempt_index}')
    write_json(attempt_root / 'task_contract.json', contract.to_dict())
    write_json(attempt_root / 'decision_settings.json', {
        'mode':settings.mode, 'enabled_extensions':settings.enabled_extensions,
        'question_version':settings.question_version, 'policy':settings.policy,
        'deadline_seconds':settings.wall_seconds, 'generator_model':args.generator_model,
        'reflector_model':args.reflector_model, 'coordinator_model':args.coordinator_model,
    })
    policy = None
    if settings.mode in ('shadow','jev_core','jev_extended'):
        from ace_rtl_agent.decision.policy import DecisionPolicy
        from ace_rtl_agent.decision.systemone_client import SystemOneClient
        try:
            client = SystemOneClient.from_env()
        except (ValueError, RuntimeError) as exc:
            client = None
            write_json(attempt_root / 'decision_preflight_error.json', {'error_type':type(exc).__name__})
        policy = DecisionPolicy(client=client, config=settings.policy)
        if settings.mode in ('jev_core','jev_extended'):
            debugger.decision_policy = policy
            if getattr(debugger,'rtl_rule_advisor',None):
                debugger.rtl_rule_advisor.decision_client = client
        if contract.task_kind == 'unknown' and client:
            from ace_rtl_agent.decision.questions import build_task_kind_questions
            try:
                task_proposal = client.decide({'contract':contract.to_dict(),'public_requirements':[],'generated_code':None},build_task_kind_questions(),
                                             timeout=min(15,max(.001,deadline-time.monotonic())))
                write_json(attempt_root/'task_kind_proposal.json',task_proposal)
                answer = task_proposal['answers']['task_kind']
                if settings.mode != 'shadow' and answer.get('confidence',0) >= .7 and answer.get('choice') != 'unknown':
                    contract = replace(contract,task_kind=answer['choice'])
                    debugger.task_contract = coordinator_agent.task_contract = contract
                    write_json(attempt_root/'task_contract.json',contract.to_dict())
            except (ValueError,RuntimeError) as exc:
                write_json(attempt_root/'task_kind_abstained.json',{'reason':type(exc).__name__})
    history = []
    archive = []
    before = None
    parent_bundle = None
    action = None
    episode = 1
    restarts = 0
    previous_candidates = {}
    reflection = 'Initial generation from the public specification.'
    coordinator_text = 'Generate every declared mutable target.'
    metadata = None
    state_version = 0
    best = None
    decision = None
    memory = None
    if 'lesson_memory' in settings.enabled_extensions:
        from .extensions import lesson_guidance
        config = settings.policy or {}
        if not config.get('lesson_snapshot') or not config.get('lesson_version'):
            raise ValueError('lesson_memory requires an explicit frozen snapshot and version')
        memory = lesson_guidance(config['lesson_snapshot'],config['lesson_version'],contract)
        write_json(attempt_root/'lesson_snapshot_reference.json',memory)
        reflection += '\nPinned confirmed lessons:\n' + memory['guidance']
    learned = None
    if 'learned_policy' in settings.enabled_extensions:
        from .extensions import load_learned_policy
        config = settings.policy or {}
        if not config.get('learned_policy_artifact') or not config.get('learned_model_version'):
            raise ValueError('learned_policy requires separately validated artifact and pinned model version')
        learned = load_learned_policy(config['learned_policy_artifact'],question_version=settings.question_version,
                  policy_version=config.get('learned_policy_version','policy-1'),model_version=config['learned_model_version'])
    started = time.monotonic()

    def budget_snapshot():
        value={'attempt_remaining_seconds':max(0,deadline-time.monotonic()),
               'task_remaining_seconds':max(0,getattr(args,'task_deadline',deadline)-time.monotonic()),
               'run_remaining_seconds':max(0,getattr(args,'run_deadline',deadline)-time.monotonic())}
        raw=os.environ.get('ACE_EXPERIMENT_BUDGET_FILE')
        if raw:
            from ace_rtl_agent.decision.budget import campaign
            value['campaign']=campaign().snapshot(Path(raw))
        return value

    def finish(status, **fields):
        result = {'attempt':attempt_index,'status':status,'history':history,
                  'worker_wall_seconds':time.monotonic()-started, **fields}
        write_json(attempt_root / 'attempt_result.json',result)
        ledger.append('attempt_terminated',status=status,task_id=contract.task_id,**fields)
        return result

    def cancellation():
        claim = read_first_pass_claim(attempt_root.parent)
        if claim:
            return finish('stopped_after_sibling_pass', cancellation_reason='verified_sibling_pass', winner_attempt=claim['attempt'])
        return finish('cancelled', cancellation_reason='infra_halt' if (attempt_root.parent/'infra_halt.json').exists() else 'user_cancel')

    for iteration in range(1, args.max_iterations + 1):
        if stop_event.is_set():
            return cancellation()
        if time.monotonic() >= deadline:
            return finish('budget_exhausted',cancellation_reason='budget_exhausted')
        if admission_event is not None and checkpoint_queue is not None:
            checkpoint_queue.put({'checkpoint_attempt':attempt_index,'iteration':iteration,
                'candidate_id':parent_bundle.candidate_id if parent_bundle else '',
                'observation_id':before.observation_id if before else '',
                'progress':None,'policy_version':'policy-1'})
            while not admission_event.wait(timeout=.05):
                if stop_event.is_set():
                    return cancellation()
                if time.monotonic() >= deadline:
                    return finish('budget_exhausted',cancellation_reason='budget_exhausted')
            admission_event.clear()
        iteration_dir = attempt_root / f'iter_{iteration:02d}'
        from .extensions import route_roles
        route = route_roles(settings,decision,failures=len([h for h in history if not h.get('passed')]),
                            default_model=args.generator_model)
        if route.get('reflector_model'):
            debugger.model_name = route['reflector_model']
            if getattr(debugger,'llm_client',None):
                debugger.llm_client.model_name = route['reflector_model']
                debugger.llm_client.client.model = route['reflector_model']
        model = AceIterationModel(workspace=workspace,iteration_dir=iteration_dir,cid=args.cid,
             generator_model=route['generator_model'],llm_timeout=max(1,min(args.llm_timeout,int(deadline-time.monotonic()))),
             reflection=reflection,coordinator=coordinator_text,previous_candidate=previous_candidates or None,
             task_contract=contract,episode_id=f'episode-{episode}',generator_output_tokens=route['max_output_tokens'])
        write_json(iteration_dir/'model_route.json',route)
        processor = select_generation_processor_class(dataset_processor)(filename=str(row_jsonl),golden=False,
            threads=1,debug=False,host=False,prefix=str(iteration_dir/'cvdp_work'),network_name=None,manage_network=False)
        processor._sbj_model_config = None
        processor._sbj_model_instance = None
        processor.include_harness = False
        processor.include_golden_patch = False
        processor.process_json()
        prepared_id, obj, repo = processor.prepare(issue=contract.task_id, model=model)
        if prepared_id != contract.task_id:
            raise RuntimeError('prepared task ID mismatch')
        prepared_root=Path(getattr(repo,'issue_path','') or (iteration_dir/'cvdp_work'/contract.task_id))
        bundle=bind_prepared_candidate(model,prepared_root,target_files,iteration_dir=iteration_dir,
                                      episode_id=f'episode-{episode}',parent=parent_bundle)
        files=dict(bundle.files)
        manifest = {**bundle.to_dict(), 'generated_files':dict(model.generated_files),
                    'mutable_targets':target_files, 'task_id':contract.task_id}
        write_json(iteration_dir/'candidate_manifest.json',manifest)
        # A cancelled generation is evidence, not a fabricated evaluation.
        if stop_event.is_set() or time.monotonic() >= deadline:
            cancelled_obs = observe({'errors':1,'tests':[],'cancelled':True},contract,bundle,
                attempt=attempt_index,iteration=iteration,version=len(history)+1,episode_id=f'episode-{episode}')
            cancelled_obs = replace(cancelled_obs,evaluator_status='UNKNOWN',evaluation_validity='unknown')
            cancelled_effect = effect(before,cancelled_obs,action,bundle)
            write_json(iteration_dir/'observation.json',cancelled_obs.to_dict())
            write_json(iteration_dir/'effect.json',cancelled_effect.to_dict())
            history.append({'iteration':iteration,'passed':False,'observation':cancelled_obs.to_dict(),
                            'effect':cancelled_effect.to_dict(),'outcome':'cancelled'})
            return cancellation() if stop_event.is_set() else finish('budget_exhausted',cancellation_reason='budget_exhausted')
        if model.preflight_issues:
            result = make_preflight_result(model.preflight_issues,model.postprocess_actions)
            write_json(iteration_dir/'preflight_result.json',result)
        else:
            cached = evaluation_cache.get(bundle.tested_hash,cache_context)
            ledger.append('evaluation_started',candidate_hash=bundle.tested_hash,iteration=iteration,cache_hit=bool(cached),
                          parent_action_id=action.action_id if action else None)
            if cached:
                result = json.loads(Path(cached['evaluation_path']).read_text())
                write_json(iteration_dir/'evaluation_reuse.json',{'evaluation_path':cached['evaluation_path'],
                                      'reused_measurement':True,'candidate_hash':bundle.tested_hash})
            else:
                os.environ['CVDP_NATIVE_TIMEOUT'] = str(max(1,min(args.evaluator_timeout,int(deadline-time.monotonic()))))
                result = processor.run(id=contract.task_id,obj=obj,repo=repo,model=model)
            ledger.append('evaluation_completed',candidate_hash=bundle.tested_hash,iteration=iteration,cache_hit=bool(cached))
        # Explicit runner provenance does not manufacture tool execution facts.
        if isinstance(result, dict):
            result = {**result, 'tested_hash':bundle.tested_hash}
        write_json(iteration_dir/'real_evaluator_result.json',result)
        if not model.preflight_issues:
            evaluation_cache.put(bundle.tested_hash,cache_context,{
                'candidate_path':model.generated_files[target_file],
                'evaluation_path':str(iteration_dir/'real_evaluator_result.json'),
                'manifest_path':str(iteration_dir/'candidate_manifest.json'),'required_services':contract.required_services})
        observation = observe(result,contract,bundle,attempt=attempt_index,iteration=iteration,
                       version=state_version+1,episode_id=f'episode-{episode}',budget_snapshot=budget_snapshot())
        state_version = observation.version
        summary = summarize_result(result)
        failure = primary_failure_from_summary(result,summary)
        if observation.evaluator_status == 'UNKNOWN' and failure['stage'] in ('INFRA_SETUP','CANDIDATE_COMPILE','CANDIDATE_FUNCTIONAL'):
            observation = replace(observation,evaluator_status=failure['stage'],
                          evaluation_validity='incomplete' if failure['stage']=='INFRA_SETUP' else observation.evaluation_validity,
                          inferences={'stage_source':'sanitized_emitted_diagnostics','stage_message':failure['message']})
        error_report = build_evaluator_error_report(result,summary)
        error_catalog = diagnostic_error_candidates(error_report,service_ids=observation.failed_checks)
        if error_catalog and observation.evaluator_status!='PASS':
            observation = replace(observation,errors=observation.errors+tuple(error_catalog),
                                  inferences={**observation.inferences,'error_candidates':error_catalog})
        transition = effect(before,observation,action,bundle)
        debugger.record_observation(observation,bundle,before=before,action=action,effect=transition,
                                    focus_error_id=action.error_id if action else None)
        write_json(iteration_dir/'observation.json',observation.to_dict())
        write_json(iteration_dir/'effect.json',transition.to_dict())
        passed = observation.evaluation_validity == 'valid' and observation.evaluator_status == 'PASS'
        (iteration_dir/'evaluator_error_report.txt').write_text(error_report,encoding='utf-8')
        history.append({'iteration':iteration,'passed':passed,'result':result,'summary':summary,
            'primary_failure':failure,'observation':observation.to_dict(),'effect':transition.to_dict(),
            'candidate_hash':bundle.tested_hash,'candidate_changed':bool(bundle.changed_files),
            'candidate_path':model.generated_files.get(target_file),'generated_files':dict(model.generated_files)})
        archive.append((bundle,observation))
        write_json(attempt_root/'candidate_archive.json',[{'bundle':b.to_dict(),'observation':o.to_dict()} for b,o in archive])
        if observation.evaluation_validity == 'valid':
            if best is None or (transition.comparable and transition.metric_delta.get('failed_count',0)<0):
                best = (bundle,observation)
        print(f'{contract.task_id} attempt {attempt_index} iteration {iteration}: {"PASS" if passed else "FAIL"} ({observation.evaluator_status})')
        # The deterministic effect and audit are saved before every terminal return.
        if passed:
            candidate_path = Path(model.generated_files[target_file])
            claimed = try_claim_first_pass(dp_root=attempt_root.parent,task_id=contract.task_id,
                 attempt_index=attempt_index,iteration=iteration,candidate_path=candidate_path,
                 evaluation_path=iteration_dir/'real_evaluator_result.json',manifest_path=iteration_dir/'candidate_manifest.json',
                 required_services=contract.required_services)
            claim = read_first_pass_claim(attempt_root.parent)
            if claimed or claim:
                stop_event.set()
            return finish('passed' if claimed else 'stopped_after_sibling_pass',passed_iteration=iteration,
                  candidate_path=str(candidate_path),time_to_first_verified_pass=time.monotonic()-started,
                  cancellation_reason=None if claimed else 'verified_sibling_pass',winner_attempt=claim.get('attempt') if claim else None)
        if observation.evaluator_status == 'INFRA_SETUP' and not any(
                  s.get('retryable_execution_failure') is True and not s.get('fatal_infra') for s in observation.services.values()):
            write_json(attempt_root.parent/'infra_halt.json',{'cause':'infra_halt','attempt':attempt_index})
            stop_event.set()
            return finish('infra_error',failed_iteration=iteration,cancellation_reason='infra_halt')
        if stop_event.is_set():
            return cancellation()
        if iteration >= args.max_iterations:
            status={'EVALUATOR_TIMEOUT':'evaluator_timeout','INVALID_EVALUATION':'invalid_evaluation',
                    'INFRA_SETUP':'infra_error'}.get(observation.evaluator_status,'failed')
            return finish(status)
        if time.monotonic() >= deadline:
            return finish('budget_exhausted',cancellation_reason='budget_exhausted')

        debugger.current_observation = observation
        debugger.previous_observation = before
        debugger.current_effect = transition
        debugger.current_bundle = bundle
        # Baseline/effects are already recorded; prose retrospective never controls native state.
        coordinator_agent.add_iteration_result(iteration=iteration,test_passed=False,error_report=error_report,
                                                rtl_code=format_candidate_bundle(target_files,files),mismatch_count=-1)
        chosen = None
        os.environ['ACE_RTL_ROLE']='coordinator'
        evidence = [Evidence('current-failure','emitted_evaluator','emitted_log',text=error_report,
                     candidate_id=bundle.candidate_id,observation_id=observation.observation_id)]
        if policy:
            decision = policy.decide(observation,contract,bundle,before=before,history=tuple(history),
                          evidence=evidence,best=best,budget_remaining=max(0,deadline-time.monotonic()),cancelled=stop_event.is_set())
            write_json(iteration_dir/'decision.json',decision.to_dict())
            if decision.fallback_reason == 'explicit_termination':
                return finish('decision_budget_exhausted',cancellation_reason='budget_exhausted')
            if settings.mode != 'shadow':
                try:
                    chosen = policy.commit(decision,observation,contract,bundle,
                              budget_remaining=max(0,deadline-time.monotonic()),cancelled=stop_event.is_set())
                except ValueError as exc:
                    write_json(iteration_dir/'decision_rejected.json',{'reason':str(exc)})
                    return finish('decision_rejected',abstention_reason=str(exc))
        if chosen is None:
            should_restart, reason = coordinator_agent.should_fresh_start(iteration)
            kind = 'fresh_start' if should_restart and restarts < settings.max_restarts else 'reflect_focused'
            chosen = ProposedAction(canonical_hash([observation.observation_id,kind]),observation.observation_id,kind,
                target_ids=contract.mutable_targets,observation_version=observation.version,tested_hash=bundle.tested_hash)
        if learned is not None and decision is not None:
            from ace_rtl_agent.decision.offline import predict_policy
            fits=[v.get('noul') for k,v in decision.answers.items() if k.startswith('fit_') and isinstance(v.get('noul'),(int,float))]
            risks=[v.get('noul') for k,v in decision.answers.items() if k.startswith('risk_') and isinstance(v.get('noul'),(int,float))]
            features={'fit': min(fits) if fits else None,'risk_max':max(risks) if risks else None,
                      'prior_changed_files':len(bundle.changed_files)}
            advice=predict_policy(learned,features,pinned_versions={'question_version':settings.question_version,
                 'model_version':decision.resolved_model or decision.requested_model,
                 'policy_version':(settings.policy or {}).get('learned_policy_version','policy-1')})
            write_json(iteration_dir/'learned_policy_advice.json',{'prediction':advice,'calibrated':False,'features':features})
            if not advice:
                chosen=replace(chosen,action_kind='reflect_deep',strategy_id=None)
        if stop_event.is_set() or time.monotonic() >= deadline:
            return cancellation() if stop_event.is_set() else finish('budget_exhausted',cancellation_reason='budget_exhausted')
        action = chosen
        os.environ['ACE_RTL_PARENT_ACTION'] = chosen.action_id
        write_json(iteration_dir/'action.json',chosen.to_dict())
        ledger.append('action_committed',action_id=chosen.action_id,action_kind=chosen.action_kind,
                      observation_id=chosen.observation_id,version=chosen.observation_version)
        previous_candidates = dict(files)
        parent_bundle = bundle
        before = observation
        coordinator_text = f'Typed action: {chosen.action_kind}. Preserve task kind {contract.task_kind} and all targets.'
        if chosen.action_kind == 'switch_focus':
            debugger.current_focused_error = chosen.error_id
            debugger.error_solved = False
            ledger.append('focus_switched',error_id=chosen.error_id,observation_id=observation.observation_id)
        if chosen.action_kind == 'gather_evidence':
            from ace_rtl_agent.decision.strategies import summarize_diagnostic
            try:
                additional = summarize_diagnostic(chosen,evidence)
                state_version += 1
                observation = replace(observation,observation_id=canonical_hash([observation.observation_id,additional.evidence_id]),
                             version=state_version,evidence_ids=observation.evidence_ids+(additional.evidence_id,))
                additional = replace(additional,observation_id=observation.observation_id)
                evidence = [replace(e,observation_id=observation.observation_id,
                              values={**e.values,'unexposed_tail_available':False}) for e in evidence]+[additional]
                write_json(iteration_dir/f'diagnostic-{state_version}.json',{'evidence':additional.to_dict(),
                           'observation':observation.to_dict(),'reused_measurement':True,'action_id':chosen.action_id})
                ledger.append('diagnostic_completed',action_id=chosen.action_id,evidence_id=additional.evidence_id,
                               new_measurement=False)
                debugger.current_observation = observation
                before = observation
                next_decision = policy.decide(observation,contract,bundle,before=before,history=tuple(history),
                               evidence=evidence,best=best,budget_remaining=deadline-time.monotonic())
                write_json(iteration_dir/f'decision-{state_version}.json',next_decision.to_dict())
                chosen = policy.commit(next_decision,observation,contract,bundle,
                                       budget_remaining=deadline-time.monotonic(),cancelled=stop_event.is_set())
                if chosen.action_kind == 'gather_evidence':
                    return finish('decision_budget_exhausted',abstention_reason='repeated_diagnostic_without_new_source')
                action = chosen
                write_json(iteration_dir/'action.json',chosen.to_dict())
                ledger.append('action_committed',action_id=chosen.action_id,action_kind=chosen.action_kind,
                              observation_id=observation.observation_id,version=state_version)
            except ValueError as exc:
                write_json(iteration_dir/'diagnostic_rejected.json',{'reason':str(exc)})
                return finish('decision_rejected',abstention_reason='diagnostic_unavailable_or_repeated')
        if chosen.action_kind == 'retry_evaluator':
            if not any(s.get('retryable_execution_failure') is True and not s.get('fatal_infra') for s in observation.services.values()):
                return finish('decision_rejected',abstention_reason='evaluator_retry_not_eligible')
            retry_limit=int((settings.policy or {}).get('max_evaluator_retries',1))
            if sum(h.get('evaluation_retry',False) for h in history) >= retry_limit:
                return finish('decision_budget_exhausted',abstention_reason='evaluator_retry_limit')
            ledger.append('evaluation_started',candidate_hash=bundle.tested_hash,retry_index=1,parent_action_id=chosen.action_id)
            os.environ['CVDP_NATIVE_TIMEOUT']=str(max(1,min(args.evaluator_timeout,int(deadline-time.monotonic()))))
            retried=processor.run(id=contract.task_id,obj=obj,repo=repo,model=model)
            retried={**retried,'tested_hash':bundle.tested_hash}
            retry_path=iteration_dir/'retry_evaluator_result.json'
            write_json(retry_path,retried)
            state_version += 1
            after=observe(retried,contract,bundle,attempt=attempt_index,iteration=iteration,
                          version=state_version,episode_id=f'episode-{episode}')
            retry_effect=effect(observation,after,chosen,bundle)
            write_json(iteration_dir/'retry_observation.json',after.to_dict())
            write_json(iteration_dir/'retry_effect.json',retry_effect.to_dict())
            debugger.record_observation(after,bundle,before=observation,action=chosen,effect=retry_effect)
            history.append({'iteration':iteration,'evaluation_retry':True,'passed':after.evaluator_status=='PASS',
                            'result':retried,'observation':after.to_dict(),'effect':retry_effect.to_dict()})
            ledger.append('evaluation_completed',candidate_hash=bundle.tested_hash,retry_index=1,observation_id=after.observation_id)
            if after.evaluator_status=='PASS' and after.evaluation_validity=='valid':
                claimed=try_claim_first_pass(dp_root=attempt_root.parent,task_id=contract.task_id,attempt_index=attempt_index,
                    iteration=iteration,candidate_path=Path(model.generated_files[target_file]),evaluation_path=retry_path,
                    manifest_path=iteration_dir/'candidate_manifest.json',required_services=contract.required_services)
                if claimed:stop_event.set()
                return finish('passed' if claimed else 'stopped_after_sibling_pass',passed_iteration=iteration,
                              time_to_first_verified_pass=time.monotonic()-started)
            observation=after
            before=after
            error_report=build_evaluator_error_report(retried,summarize_result(retried))
            chosen=replace(chosen,action_id=canonical_hash([chosen.action_id,'repair-after-retry']),
                           action_kind='reflect_focused',observation_id=after.observation_id,observation_version=after.version)
            action=chosen
        if chosen.action_kind == 'fresh_start' and restarts < settings.max_restarts:
            restarts += 1
            episode += 1
            debugger.clear_history()
            coordinator_agent.mark_fresh_start(iteration)
            previous_candidates = {}
            reflection = 'New episode: regenerate from public specification; do not re-inject previous candidate or guidance.'
            if memory:
                reflection += '\nPinned confirmed lessons:\n'+memory['guidance']
            continue
        if chosen.action_kind == 'rollback_best' and best:
            previous_candidates = dict(best[0].files)
            parent_bundle = best[0]
            # New monotonic version referencing archived observation; never new measurement.
            write_json(iteration_dir/'rollback.json',{'archived_observation_id':best[1].observation_id,
                         'active_version':observation.version+1,'budget_remaining':deadline-time.monotonic()})
            state_version += 1
            archived=best[1]
            observation=replace(archived,observation_id=canonical_hash([archived.observation_id,'rollback',state_version]),version=state_version)
            before=observation
            debugger.current_observation=observation
            error_report=next((build_evaluator_error_report(h['result'],h.get('summary',summarize_result(h['result'])))
                              for h in history if h.get('observation',{}).get('observation_id')==archived.observation_id),error_report)
            evidence=[Evidence('rollback-failure','archived_emitted_evaluator','diagnostic',text=error_report,
                               candidate_id=parent_bundle.candidate_id,observation_id=observation.observation_id)]
            ledger.append('rollback_activated',action_id=chosen.action_id,archived_observation_id=archived.observation_id,
                          active_version=state_version,budget_rewound=False,new_measurement=False)
        if chosen.action_kind == 'repair_with_template':
            from ace_rtl_agent.decision.strategies import STRATEGIES
            recipe = STRATEGIES.get(chosen.strategy_id)
            reflection = getattr(recipe,'guidance','') or 'Apply the selected narrow repair while preserving the public interface.'
            continue
        harness_context = build_reflector_harness_context(None,target_file,mutable_targets=target_files,
                                                           public_context=contract.immutable_context)
        os.environ['ACE_RTL_ROLE']='reflector'
        reflection, metadata = call_reflector(debugger,iteration_dir,contract.task_id,target_file,
                  files.get(target_file,''),error_report,iteration,contract.specification,harness_context,
                  candidate_files=previous_candidates,task_contract=contract,observation=observation,
                  bundle=parent_bundle,action=chosen,evidence=evidence,best=best)
    return finish('failed')


def attempt_worker_main(
    result_queue: multiprocessing.Queue,
    run_log: str,
    attempt_kwargs: Dict[str, Any],
) -> None:
    """Run one datapoint attempt in an isolated process.

    Attempts must be OS processes rather than threads so the parent can stop
    sibling attempts immediately once one attempt passes, including attempts
    blocked in an LLM client call or evaluator subprocess.
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_handle = open(run_log, "a", encoding="utf-8", buffering=1)
    sys.stdout = Tee(sys.__stdout__, log_handle)
    sys.stderr = Tee(sys.__stderr__, log_handle)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    attempt_index = attempt_kwargs.get("attempt_index")
    try:
        result = run_attempt(**attempt_kwargs)
    except BaseException as exc:
        traceback.print_exc()
        error_message = str(exc)
        result = {
            "attempt": attempt_index,
            "status": "error",
            "error": error_message,
            "primary_failure": primary_failure_from_attempt_error(error_message),
            "traceback": traceback.format_exc(),
        }
    try:
        result_queue.put(result)
    finally:
        logging.shutdown()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_handle.close()


def stop_attempt_process(
    *,
    process: multiprocessing.Process,
    attempt_root: Path,
    dp_root: Path,
    winner_attempt: int,
    pre_signaled_pids: Optional[Iterable[int]] = None,
    cancellation_reason: Optional[str] = None,
) -> Dict[str, Any]:
    killed_pids: List[int] = list(pre_signaled_pids or [])
    killed_pids.extend(terminate_pids(attempt_process_pids(process, attempt_root), grace_seconds=0.2))
    process.join(timeout=0.5)
    if process.is_alive():
        process.kill()
        process.join(timeout=0.5)
    killed_pids.extend(terminate_pids(pids_matching_path(attempt_root), grace_seconds=0.1))
    cleanup = cleanup_attempt_root(attempt_root, dp_root)
    reason = cancellation_reason or ('verified_sibling_pass' if winner_attempt > 0 else 'user_cancel')
    from ace_rtl_agent.decision.ledger import EventLedger
    EventLedger(dp_root/'events','parent').append('attempt_terminated',
         terminated_attempt=int(attempt_root.name.rsplit('_',1)[-1]),cancellation_reason=reason,
         upstream_usage='unknown_unless_received',winner_attempt=winner_attempt if reason=='verified_sibling_pass' else None)
    return {
        "attempt": int(attempt_root.name.rsplit("_", 1)[-1]),
        "status": "stopped_after_sibling_pass" if reason=='verified_sibling_pass' else 'cancelled',
        "winner_attempt": winner_attempt if reason=='verified_sibling_pass' else None,
        "cancellation_reason": reason,
        "terminated_pids": sorted(set(killed_pids)),
        "cleanup": cleanup,
    }


def passed_result_from_claim(claim: Dict[str, Any], *, exitcode: Optional[int] = None) -> Dict[str, Any]:
    return {
        "attempt": int(claim["attempt"]),
        "status": "passed",
        "passed_iteration": claim.get("iteration"),
        "candidate_path": claim.get("candidate_path"),
        "first_pass_claim": claim,
        "result_source": "first_pass_claim",
        "exitcode": exitcode,
    }


def run_datapoint(
    *,
    workspace: Path,
    cvdp_repo: Path,
    row: Dict[str, Any],
    run_dir: Path,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    task_id = row["id"]
    dp_root = run_dir / "datapoints" / task_id
    dp_root.mkdir(parents=True, exist_ok=True)
    row_jsonl = dp_root / "row.jsonl"
    write_jsonl(row_jsonl, [row])

    ctx = multiprocessing.get_context("spawn")
    stop_event = ctx.Event()
    result_queue: multiprocessing.Queue = ctx.Queue()
    attempt_results: List[Dict[str, Any]] = []
    processes: Dict[int, multiprocessing.Process] = {}
    attempt_roots: Dict[int, Path] = {}
    reported_attempts: set[int] = set()
    passed_attempt: Optional[int] = None
    from ace_rtl_agent.decision.settings import DecisionSettings
    settings = DecisionSettings.from_env(getattr(args,'decision_mode',None))
    worker_args = copy.copy(args)
    worker_args.task_deadline = min(time.monotonic()+settings.task_wall_seconds,
                                   getattr(args,'run_deadline',float('inf')))
    admission_events = {}
    checkpoints = {}
    active_checkpoints = set()
    scheduler = None
    if 'adaptive_scheduling' in settings.enabled_extensions:
        from ace_rtl_agent.decision.extensions import AdaptiveScheduler, AttemptCheckpoint
        scheduler = AdaptiveScheduler(int((settings.policy or {}).get('minimum_checkpoints',1)),enabled=True)

    def admit_checkpoints():
        if not scheduler:
            return
        slots=max(0,int((settings.policy or {}).get('checkpoint_concurrency',1))-len(active_checkpoints))
        for attempt_id in scheduler.allocate(list(checkpoints.values()),slots):
            attempt=int(attempt_id)
            checkpoints.pop(attempt_id,None)
            active_checkpoints.add(attempt)
            admission_events[attempt].set()

    def stop_sibling_attempts(winner_attempt: int) -> None:
        pre_signaled_pids: Dict[int, List[int]] = {}
        for sibling, process in processes.items():
            if sibling == winner_attempt:
                continue
            if process.is_alive():
                pre_signaled_pids[sibling] = request_attempt_stop(process, attempt_roots[sibling])

        for sibling, process in processes.items():
            if sibling == winner_attempt:
                continue
            if sibling in reported_attempts:
                if process.is_alive():
                    cleanup_result = stop_attempt_process(
                        process=process,
                        attempt_root=attempt_roots[sibling],
                        dp_root=dp_root,
                        winner_attempt=winner_attempt,
                        pre_signaled_pids=pre_signaled_pids.get(sibling),
                    )
                    for existing in attempt_results:
                        if existing.get("attempt") == sibling:
                            existing["cleanup_after_sibling_pass"] = cleanup_result
                            break
                else:
                    cleanup = cleanup_attempt_root(attempt_roots[sibling], dp_root)
                    for existing in attempt_results:
                        if existing.get("attempt") == sibling:
                            existing["cleanup_after_sibling_pass"] = cleanup
                            break
                write_json(dp_root / "attempt_results.partial.json", attempt_results)
                continue

            stopped = stop_attempt_process(
                process=process,
                attempt_root=attempt_roots[sibling],
                dp_root=dp_root,
                winner_attempt=winner_attempt,
                pre_signaled_pids=pre_signaled_pids.get(sibling),
            )
            reported_attempts.add(sibling)
            attempt_results.append(stopped)
            write_json(dp_root / "attempt_results.partial.json", attempt_results)

    try:
        for i in range(1, args.attempts + 1):
            attempt_root = dp_root / f"attempt_{i}"
            attempt_roots[i] = attempt_root
            process = ctx.Process(
                target=attempt_worker_main,
                args=(
                    result_queue,
                    str(run_dir / "run.log"),
                    {
                        "workspace": workspace,
                        "cvdp_repo": cvdp_repo,
                        "row": copy.deepcopy(row),
                        "row_jsonl": row_jsonl,
                        "attempt_root": attempt_root,
                        "attempt_index": i,
                        "args": worker_args,
                        "stop_event": stop_event,
                        **({'checkpoint_queue':result_queue,'admission_event':admission_events.setdefault(i,ctx.Event())} if scheduler else {}),
                    },
                ),
            )
            process.start()
            processes[i] = process

        while len(reported_attempts) < args.attempts:
            claim = read_first_pass_claim(dp_root)
            if claim and passed_attempt is None:
                passed_attempt = int(claim["attempt"])
                stop_event.set()
                stop_sibling_attempts(passed_attempt)
            # Enforce total wall time even if a transport keeps its socket alive.
            if time.monotonic() >= worker_args.task_deadline:
                stop_event.set()
                for attempt,process in processes.items():
                    if attempt in reported_attempts:
                        continue
                    stopped=stop_attempt_process(process=process,attempt_root=attempt_roots[attempt],
                         dp_root=dp_root,winner_attempt=-1,cancellation_reason='budget_exhausted')
                    stopped['status']='budget_exhausted'
                    reported_attempts.add(attempt)
                    attempt_results.append(stopped)
                write_json(dp_root/'attempt_results.partial.json',attempt_results)
                break

            try:
                result = result_queue.get(timeout=0.05)
            except queue.Empty:
                result = None

            if result is not None:
                if scheduler and 'checkpoint_attempt' in result:
                    from ace_rtl_agent.decision.extensions import AttemptCheckpoint
                    attempt=result['checkpoint_attempt']
                    active_checkpoints.discard(attempt)
                    checkpoints[str(attempt)] = AttemptCheckpoint(str(attempt),progress=result.get('progress'),
                        candidate_id=result.get('candidate_id',''),observation_id=result.get('observation_id',''),
                        policy_version=result.get('policy_version','policy-1'))
                    admit_checkpoints()
                    result=None
            if result is not None:
                attempt = result.get("attempt")
                if isinstance(attempt, int) and attempt not in reported_attempts:
                    if (
                        result.get("status") == "passed"
                        and passed_attempt is not None
                        and attempt != passed_attempt
                    ):
                        result = dict(result)
                        result["status"] = "stopped_after_sibling_pass"
                        result["winner_attempt"] = passed_attempt
                        result["suppressed_duplicate_pass"] = True
                    reported_attempts.add(attempt)
                    active_checkpoints.discard(attempt)
                    checkpoints.pop(str(attempt),None)
                    admit_checkpoints()
                    attempt_results.append(result)
                    write_json(dp_root / "attempt_results.partial.json", attempt_results)
                    if result.get("status") == "passed" and passed_attempt is None:
                        passed_attempt = attempt
                        stop_event.set()
                        stop_sibling_attempts(passed_attempt)

            for attempt, process in list(processes.items()):
                if attempt in reported_attempts or process.is_alive():
                    continue
                process.join(timeout=0)
                if attempt not in reported_attempts:
                    if passed_attempt is not None and attempt == passed_attempt:
                        claim = read_first_pass_claim(dp_root)
                        if claim and int(claim["attempt"]) == attempt:
                            result = passed_result_from_claim(claim, exitcode=process.exitcode)
                        else:
                            result = {
                                "attempt": attempt,
                                "status": "error",
                                "exitcode": process.exitcode,
                                "error": "winning attempt exited without reporting a result or first-pass claim",
                                "primary_failure": primary_failure_from_attempt_error(
                                    "winning attempt exited without reporting a result or first-pass claim"
                                ),
                            }
                    elif passed_attempt is not None:
                        result = {
                            "attempt": attempt,
                            "status": "stopped_after_sibling_pass",
                            "exitcode": process.exitcode,
                            "winner_attempt": passed_attempt,
                            "cleanup": cleanup_attempt_root(attempt_roots[attempt], dp_root),
                        }
                    else:
                        result = {
                            "attempt": attempt,
                            "status": "error",
                            "exitcode": process.exitcode,
                            "primary_failure": primary_failure_from_attempt_error(
                                "attempt process exited without reporting a result"
                            ),
                        }
                        result["error"] = "attempt process exited without reporting a result"
                    reported_attempts.add(attempt)
                    attempt_results.append(result)
                    write_json(dp_root / "attempt_results.partial.json", attempt_results)
    except KeyboardInterrupt:
        stop_event.set()
        for attempt, process in processes.items():
            if attempt not in reported_attempts:
                stop_attempt_process(
                    process=process,
                    attempt_root=attempt_roots[attempt],
                    dp_root=dp_root,
                    winner_attempt=-1,
                )
        raise
    finally:
        stop_event.set()
        for attempt, process in processes.items():
            if process.is_alive() and attempt not in reported_attempts:
                terminate_processes_for_path(attempt_roots[attempt])
                terminate_process_tree(process.pid)
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
        result_queue.close()
        result_queue.join_thread()

    passed_attempts = [r for r in attempt_results if r.get("status") == "passed"]
    claim = read_first_pass_claim(dp_root)
    if claim and not passed_attempts:
        winner_attempt = int(claim["attempt"])
        recovered = passed_result_from_claim(claim, exitcode=None)
        recovered["result_source"] = "first_pass_claim_final_recovery"
        for idx, existing in enumerate(attempt_results):
            if existing.get("attempt") == winner_attempt:
                attempt_results[idx] = recovered
                break
        else:
            attempt_results.append(recovered)
        passed_attempts = [recovered]
    final = {
        "id": task_id,
        "category": row.get("categories", [None])[0],
        "difficulty": row.get("categories", [None, None])[1],
        "passed": bool(passed_attempts),
        "passed_attempt": passed_attempts[0].get("attempt") if passed_attempts else None,
        "stopped_after_first_pass": sum(
            1 for r in attempt_results if r.get("status") == "stopped_after_sibling_pass"
        ),
        "attempts": attempt_results,
    }
    write_json(dp_root / "result.json", final)
    return final


def write_results_md(
    *,
    path: Path,
    dataset: Path,
    cid: str,
    role_map: Dict[str, str],
    cvdp_repo: Path,
    cvdp_commit: str,
    rows: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    passed_ids = sorted(r["id"] for r in results if r.get("passed"))
    failed_ids = sorted(r["id"] for r in results if not r.get("passed"))
    total = len(rows)
    pass_rate = (len(passed_ids) / total) if total else 0.0
    stopped = sum(
        1
        for r in results
        for a in r.get("attempts", [])
        if a.get("status") == "stopped_after_sibling_pass"
    )
    text = f"""\
# ACE-RTL CVDP Results

- Dataset: `{dataset}`
- CID: `{cid}`
- Row count: {total}
- Role models: `{json.dumps(role_map, sort_keys=True)}`
- CVDP repo: `{cvdp_repo}`
- CVDP commit: `{cvdp_commit}`
- Backend: workspace-local native harness (`CVDP_NATIVE_HARNESS=1`)
- Datapoint workers: {args.datapoint_workers}
- Iteration budget: {args.max_iterations} per attempt
- Attempts per datapoint: {args.attempts}
- Sibling attempts stopped after pass: {stopped}

## Pass Rate

- {len(passed_ids)} / {total} = {pass_rate:.4f}

## Passed IDs

{chr(10).join(f"- `{x}`" for x in passed_ids) if passed_ids else "- None"}

## Failed IDs

{chr(10).join(f"- `{x}`" for x in failed_ids) if failed_ids else "- None"}

## Artifact Paths

- Raw result summary: `summary.json`
- Per-datapoint artifacts: `datapoints/<id>/`
- Run log: `run.log`

Integrity note: role prompts used the workspace-local CVDP task data, generated
candidates, role history, and evaluator reports produced by the local native
harness. No external scripts are required at runtime.
"""
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--cvdp-repo", default=None)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--cid", required=True)
    parser.add_argument("--outputs-root", default="outputs")
    parser.add_argument("--generator-model", default="nvidia/nemotron-3-ultra-550b-a55b")
    parser.add_argument("--reflector-model", default="nvidia/nemotron-3-ultra-550b-a55b")
    parser.add_argument("--coordinator-model", default="nvidia/nemotron-3-ultra-550b-a55b")
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument(
        "--datapoint-workers",
        type=int,
        default=4,
        help="Number of CVDP datapoints to run in parallel by default",
    )
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument('--decision-mode', choices=('legacy','baseline_fixed','shadow','jev_core','jev_extended'),
                        default=os.environ.get('ACE_RTL_DECISION_MODE','baseline_fixed'))
    parser.add_argument("--llm-timeout", type=int, default=1800)
    parser.add_argument(
        "--evaluator-timeout",
        type=int,
        default=env_int(
            "CVDP_NATIVE_TIMEOUT",
            env_int("DOCKER_TIMEOUT", DEFAULT_EVALUATOR_TIMEOUT_SECONDS),
        ),
        help="Seconds before a native CVDP evaluator service is killed and reported as candidate timeout",
    )
    parser.add_argument("--id", action="append", default=None, help="Optional datapoint id filter")
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for shakedown/debug")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from ace_rtl_agent.decision.settings import DecisionSettings
    settings = DecisionSettings.from_env(args.decision_mode)
    args.run_deadline = time.monotonic()+settings.run_wall_seconds
    if min(args.attempts,args.max_iterations,args.datapoint_workers,args.llm_timeout,args.evaluator_timeout) <= 0:
        raise ValueError('attempt, iteration, worker and timeout budgets must be positive')
    workspace = Path(args.workspace).resolve()
    maybe_reexec_workspace_python(workspace)
    dataset = ensure_under(Path(args.dataset), workspace, "dataset")
    outputs_root = ensure_under(Path(args.outputs_root), workspace, "outputs root")
    cvdp_repo = Path(args.cvdp_repo or (workspace / "external/cvdp_benchmark")).resolve()
    ensure_under(cvdp_repo, workspace, "CVDP repo")
    if not (cvdp_repo / "run_benchmark.py").exists():
        raise FileNotFoundError(f"CVDP repo not found: {cvdp_repo}")
    if not role_api_key() and not os.environ.get("ACE_RTL_LLM_SCRIPT"):
        raise RuntimeError("NVIDIA_API_KEY must be set, or set ACE_RTL_LLM_SCRIPT")

    run_dir = unique_run_dir(outputs_root, args.cid, dataset.stem)
    args.run_id = run_dir.name
    log_file = (run_dir / "run.log").open("w", encoding="utf-8", buffering=1)
    sys.stdout = Tee(sys.__stdout__, log_file)
    sys.stderr = Tee(sys.__stderr__, log_file)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    print(f"RUN_DIR={run_dir}")

    sys.path.insert(0, str(cvdp_repo))
    install_native_harness_patch()

    commit = git_commit_or_unknown(cvdp_repo)
    rows = load_cid_rows(dataset, args.cid, args.id)
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        raise RuntimeError(f"no rows found for {args.cid} in {dataset}")
    filtered = run_dir / f"{dataset.stem}_{args.cid}.jsonl"
    write_jsonl(filtered, rows)

    role_map = {
        "generator": args.generator_model,
        "reflector": args.reflector_model,
        "coordinator": args.coordinator_model,
    }
    write_json(
        run_dir / "metadata.json",
        {
            "dataset": str(dataset),
            "filtered_dataset": str(filtered),
            "cid": args.cid,
            "row_count": len(rows),
            "role_map": role_map,
            "cvdp_repo": str(cvdp_repo),
            "cvdp_commit": commit,
            "attempts": args.attempts,
            "datapoint_workers": args.datapoint_workers,
            "max_iterations": args.max_iterations,
            "evaluator_timeout": args.evaluator_timeout,
            "native_harness": True,
            "decision_mode": settings.mode,
            "enabled_extensions": settings.enabled_extensions,
            "question_version": settings.question_version,
            "policy": settings.policy,
            "evaluation_cache_mode": settings.evaluation_cache_mode,
            "wall_budgets": {'run_seconds':settings.run_wall_seconds,'task_seconds':settings.task_wall_seconds,
                             'attempt_seconds':settings.wall_seconds},
        },
    )

    indexed_rows = list(enumerate(rows, start=1))
    eda_setup = apply_eda_tool_setup(rows)
    tool_preflight = native_tool_preflight(rows)
    tool_preflight["eda_tool_setup"] = eda_setup
    write_json(run_dir / "native_tool_preflight.json", tool_preflight)
    if not tool_preflight["ok"]:
        missing = ", ".join(tool_preflight["missing_tools"])
        print(f"INFRA_SETUP: missing required native simulator tool(s): {missing}")
        for row_id, tools in sorted(tool_preflight["missing_by_row"].items()):
            print(f"INFRA_SETUP: {row_id} requires: {', '.join(tools)}")
        results = [
            {
                "_row_index": index,
                "id": row["id"],
                "category": row.get("categories", [None])[0],
                "difficulty": row.get("categories", [None, None])[1],
                "passed": False,
                "error": (
                    "INFRA_SETUP: missing required native simulator tool(s): "
                    + ", ".join(tool_preflight["missing_by_row"].get(row["id"], []))
                ),
                "attempts": [],
            }
            for index, row in indexed_rows
        ]
        for result in results:
            result.pop("_row_index", None)
        summary = {
            "dataset": str(dataset),
            "cid": args.cid,
            "row_count": len(rows),
            "passed_ids": [],
            "failed_ids": sorted(r["id"] for r in results),
            "preflight_failed": True,
            "native_tool_preflight": tool_preflight,
            "results": results,
        }
        write_json(run_dir / "summary.json", summary)
        write_results_md(
            path=run_dir / "results.md",
            dataset=dataset,
            cid=args.cid,
            role_map=role_map,
            cvdp_repo=cvdp_repo,
            cvdp_commit=commit,
            rows=rows,
            results=results,
            args=args,
        )
        print(f"completed run with INFRA_SETUP preflight failure: {run_dir}")
        return 2

    results: List[Dict[str, Any]] = []
    datapoint_workers = max(1, min(args.datapoint_workers, len(indexed_rows)))

    def run_indexed_datapoint(index: int, row: Dict[str, Any]) -> Dict[str, Any]:
        print(f"=== Datapoint {index}/{len(rows)}: {row['id']} ===")
        result = run_datapoint(
            workspace=workspace,
            cvdp_repo=cvdp_repo,
            row=row,
            run_dir=run_dir,
            args=args,
        )
        result["_row_index"] = index
        return result

    if datapoint_workers == 1:
        for index, row in indexed_rows:
            result = run_indexed_datapoint(index, row)
            results.append(result)
            write_json(run_dir / "summary.partial.json", results)
    else:
        print(f"Running up to {datapoint_workers} CVDP datapoints in parallel")
        with concurrent.futures.ThreadPoolExecutor(max_workers=datapoint_workers) as executor:
            futures = {
                executor.submit(run_indexed_datapoint, index, row): (index, row)
                for index, row in indexed_rows
            }
            for future in concurrent.futures.as_completed(futures):
                index, row = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "_row_index": index,
                        "id": row["id"],
                        "category": row.get("categories", [None])[0],
                        "difficulty": row.get("categories", [None, None])[1],
                        "passed": False,
                        "error": str(exc),
                        "attempts": [],
                    }
                results.append(result)
                results.sort(key=lambda item: item.get("_row_index", 0))
                write_json(run_dir / "summary.partial.json", results)

    for result in results:
        result.pop("_row_index", None)

    summary = {
        "dataset": str(dataset),
        "cid": args.cid,
        "row_count": len(rows),
        "passed_ids": sorted(r["id"] for r in results if r.get("passed")),
        "failed_ids": sorted(r["id"] for r in results if not r.get("passed")),
        "results": results,
    }
    write_json(run_dir / "summary.json", summary)
    write_results_md(
        path=run_dir / "results.md",
        dataset=dataset,
        cid=args.cid,
        role_map=role_map,
        cvdp_repo=cvdp_repo,
        cvdp_commit=commit,
        rows=rows,
        results=results,
        args=args,
    )
    print(f"completed run: {run_dir}")
    return 0
