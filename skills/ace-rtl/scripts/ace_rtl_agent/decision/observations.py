"""Deterministic public evaluator facts; prose is not a success authority."""
from __future__ import annotations

import math
import re
from .types import TaskContract, Observation, EffectRecord, canonical_hash, validate_target


def build_task_contract(row: dict, cid: str = '') -> TaskContract:
    from ace_cvdp_native.config import classify_task
    from ace_cvdp_native.harness import service_names_from_row
    inputs = row.get('input') or {}
    targets = tuple(validate_target(p) for p in (row.get('output') or {}).get('context', {}))
    spec = str(inputs.get('prompt', ''))
    categories = row.get('categories') or []
    category = str(row.get('category') or (categories[0] if categories else cid))
    kind = classify_task(targets[0] if targets else '', spec, category=category,
                         task_kind=row.get('task_kind'))
    kind = {'rtl': 'rtl_implementation', 'optimization': 'rtl_optimization', 'generic': 'unknown'}.get(kind, kind)
    context = {p: str(v) for p, v in (inputs.get('context') or {}).items() if p not in targets}
    initial = {p:str(v) for p,v in (inputs.get('context') or {}).items() if p in targets}
    services = row.get('required_services')
    if services is None:
        services = service_names_from_row(row)
    return TaskContract(str(row.get('id', cid)), cid, category, kind,
                        canonical_hash({'prompt': spec, 'context': context, 'initial_targets':initial}), targets,
                        context, tuple(services), tuple(row.get('allowed_tools') or ()),
                        specification=spec,initial_targets=initial)


def validate_result(result, required_services=(), tested_hash=None):
    """Return validation issues; legacy service exit records remain supported.

    A missing hash is bound by the caller's evaluated-bundle boundary. A supplied
    hash must match; callers must not reuse this binding for cached results.
    """
    issues = []
    if not isinstance(result, dict):
        return ['result_not_object']
    tests = result.get('tests')
    if type(result.get('errors')) is not int or result['errors'] < 0:
        issues.append('invalid_errors')
    if not isinstance(tests, list) or not tests:
        return issues + ['missing_authoritative_tests']
    if result.get('authoritative_parse_error') or result.get('evaluation_validity') in {'invalid', 'incomplete'}:
        issues.append('corrupt_authoritative_result')
    if result.get('execution_status', 'completed') not in {'completed', 'complete', 'finished'}:
        issues.append('incomplete_execution')
    if tested_hash and result.get('tested_hash', tested_hash) != tested_hash:
        issues.append('tested_hash_mismatch')
    names = []
    failures = 0
    for test in tests:
        if not isinstance(test, dict):
            issues.append('corrupt_service'); continue
        name = test.get('service') or test.get('service_id') or test.get('name')
        if name:
            names.append(name)
        code = test.get('result')
        if code==124 or test.get('timeout'):
            issues.append('evaluation_timeout')
        if type(code) is not int:
            issues.append('invalid_service_exit')
        else:
            failures += code != 0
        status = test.get('execution_status', test.get('status', 'completed'))
        if status not in {'completed', 'complete', 'finished', 'passed', 'failed', 'PASS', 'FAIL'}:
            issues.append('incomplete_service')
        if test.get('authoritative_parse_error'):
            issues.append('corrupt_service')
        if test.get('tests') == [] or test.get('checks') == []:
            issues.append('empty_required_checks')
        checks = test.get('checks', test.get('tests'))
        if checks is not None:
            if not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks):
                issues.append('corrupt_authoritative_checks')
            else:
                ids = []
                for check in checks:
                    check_id = check.get('id') or check.get('test_id') or check.get('name')
                    if not check_id:
                        issues.append('missing_check_id')
                    ids.append(check_id)
                    check_status = check.get('execution_status', check.get('status', 'completed'))
                    if check_status in {'running', 'pending', 'cancelled'}:
                        issues.append('incomplete_check')
                    if check.get('required',True) and check_status in {'skipped','not_executed'}:
                        issues.append('required_check_not_executed')
                    if check_status not in {'skipped', 'not_executed', 'passed', 'failed', 'PASS', 'FAIL'} and type(check.get('result')) is not int:
                        issues.append('invalid_check_exit')
                    if (check.get('result') not in (None, 0) or check_status in {'failed', 'FAIL'}) and code == 0:
                        issues.append('inconsistent_check_result')
                if len(ids) != len(set(ids)):
                    issues.append('duplicate_check_id')
    if len(names) != len(set(names)):
        issues.append('duplicate_service')
    if set(required_services) - set(names):
        issues.append('missing_required_service')
    if result.get('errors') == 0 and failures:
        issues.append('inconsistent_errors')
    if result.get('errors', 0) > 0 and not failures:
        issues.append('unaccounted_errors')
    return issues


def execution_stage(result):
    if not isinstance(result, dict):
        return 'INVALID_EVALUATION'
    raw_tests = result.get('tests')
    tests = [t for t in raw_tests if isinstance(t, dict)] if isinstance(raw_tests, list) else []
    if result.get('category') == 'LOCAL_PREFLIGHT' or result.get('preflight_failures'):
        return 'LOCAL_PREFLIGHT'
    if result.get('timeout') or any(t.get('result') == 124 or t.get('timeout') for t in tests):
        return 'EVALUATOR_TIMEOUT'
    for stage in ('INFRA_SETUP', 'CANDIDATE_COMPILE', 'CANDIDATE_FUNCTIONAL'):
        if result.get('stage') == stage or any(t.get('stage') == stage for t in tests):
            return stage
    text = '\n'.join(str(t.get('error_msg') or '') for t in tests).lower()
    if re.search(r'timeout|timed out', text):
        return 'EVALUATOR_TIMEOUT'
    if re.search(r'command not found|no command|license.*(?:unavailable|failed)|permission denied|no such file', text):
        return 'INFRA_SETUP'
    if re.search(r'compilation failed|compile error|syntax error|parse error|port mismatch|undeclared|module not found', text):
        return 'CANDIDATE_COMPILE'
    if re.search(r'assertionerror|runtime|mismatch|test.*failed', text):
        return 'CANDIDATE_FUNCTIONAL'
    return 'UNKNOWN'


def observe(result, contract, bundle, *, attempt, iteration, version, episode_id, budget_snapshot=None):
    issues = validate_result(result, contract.required_services, bundle.tested_hash)
    result = result if isinstance(result, dict) else {}
    stage = execution_stage(result)
    validity = 'invalid' if issues else 'valid'
    if stage in ('EVALUATOR_TIMEOUT','INFRA_SETUP'):
        validity='incomplete'
    if not issues and result.get('errors') == 0:
        stage = 'PASS'
    elif issues and stage == 'UNKNOWN':
        stage = 'INVALID_EVALUATION'
    services, executed, passed, failed, skipped = {}, set(), set(), set(), set()
    raw_tests = result.get('tests')
    raw_tests = raw_tests if isinstance(raw_tests, list) else []
    for index, test in enumerate(raw_tests):
        if not isinstance(test, dict):
            continue
        name = str(test.get('service') or test.get('service_id') or test.get('name') or f'service:{index}')
        services[name] = dict(test)
        checks = test.get('checks', test.get('tests'))
        if isinstance(checks, list):
            records = [(f"{name}/{c.get('id') or c.get('test_id') or c.get('name')}", c) for c in checks
                       if isinstance(c, dict) and (c.get('id') or c.get('test_id') or c.get('name'))]
        else:
            records = [(name, test)] if name != f'service:{index}' else []
        for check_id, check in records:
            status = check.get('execution_status', check.get('status', 'completed'))
            if status in {'skipped', 'not_executed', 'running', 'pending', 'cancelled'}:
                skipped.add(check_id); continue
            code = check.get('result')
            if type(code) is int:
                executed.add(check_id)
                (passed if code == 0 else failed).add(check_id)
            elif status in {'passed', 'PASS', 'failed', 'FAIL'}:
                executed.add(check_id)
                (passed if status in {'passed', 'PASS'} else failed).add(check_id)
    supports_checks = bool(services) and all(isinstance(t.get('checks', t.get('tests')), list) for t in services.values())
    metrics = {'mismatch_count': None, 'passed_count': len(passed) if supports_checks else None,
               'failed_count': len(failed) if supports_checks else None}
    raw_metrics = result.get('metrics')
    for k, v in (raw_metrics if isinstance(raw_metrics, dict) else {}).items():
        metrics[k] = v if type(v) in (int, float) and math.isfinite(v) and v >= 0 else None
    key_fields = ('seed', 'testset', 'parameterization', 'harness_version', 'tool_version', 'config_version')
    key = canonical_hash({'task': contract.spec_hash, 'services': sorted(services),
                          'executed': sorted(executed), **{k: result.get(k) for k in key_fields},
                          'service_config': {n: {k: t.get(k) for k in key_fields} for n, t in services.items()},
                          'check_config': {n: {str(c.get('id') or c.get('test_id') or c.get('name')):
                                               {k: c.get(k) for k in key_fields}
                                               for c in t.get('checks', t.get('tests', [])) if isinstance(c, dict)}
                                            for n, t in services.items() if isinstance(t.get('checks', t.get('tests', [])), list)}})
    if any(result.get(name) is None for name in key_fields):
        key = None  # Matching unknown versions/seeds is not evidence of comparability.
    diagnostic = ('truncated' if result.get('diagnostics_truncated') else
                  'incomplete' if result.get('diagnostics_parse_error') else result.get('diagnostic_completeness', 'unknown'))
    identity = canonical_hash([contract.task_id, attempt, episode_id, iteration, version, bundle.tested_hash])
    availability={k:{'available':v is not None,'reason':None if v is not None else 'authoritative harness does not supply a comparable metric'}
                  for k,v in metrics.items()}
    return Observation(identity, version, contract.task_id, attempt, episode_id, iteration,
                       bundle.tested_hash, stage, validity, diagnostic, services,
                       tuple(sorted(executed)), tuple(sorted(passed)), tuple(sorted(failed)), tuple(sorted(skipped)),
                       metrics, key, tuple(result.get('evidence_ids') or ()), budget_snapshot or {}, tuple(issues),
                       metric_availability=availability)


def effect(before, after, action, bundle):
    comparable = bool(before and before.metric_comparability_key and before.evaluation_validity == after.evaluation_validity == 'valid'
                      and before.metric_comparability_key == after.metric_comparability_key
                      and before.executed_checks == after.executed_checks)
    focus = 'unknown'
    target = action.error_id if action else None
    if target:
        corresponding = before.inferences.get('error_candidates',{}).get(target,{}).get('services',()) if before else ()
        if target in after.failed_checks or target in after.errors:
            focus = 'persists'
        elif target in after.passed_checks and after.evaluation_validity == 'valid':
            focus = 'observed_resolved'
        elif corresponding and set(corresponding) <= set(after.passed_checks) and after.evaluation_validity == 'valid':
            focus = 'observed_resolved'
        elif after.evaluator_status in {'LOCAL_PREFLIGHT', 'INFRA_SETUP', 'CANDIDATE_COMPILE', 'EVALUATOR_TIMEOUT'}:
            focus = 'masked'
        elif target in after.skipped_checks:
            focus = 'not_executed'
    new = tuple(sorted(set(after.failed_checks) - set(before.executed_checks))) if before else ()
    regressions = tuple(sorted(set(after.failed_checks) & set(before.passed_checks))) if comparable else ()
    delta = {k: v - before.metrics[k] for k, v in after.metrics.items()
             if comparable and type(v) in (int, float) and type(before.metrics.get(k)) in (int, float)}
    outcome = 'passed' if after.evaluator_status == 'PASS' and after.evaluation_validity == 'valid' else (
        'failed' if after.evaluation_validity == 'valid' else 'unknown')
    return EffectRecord(canonical_hash([before.observation_id if before else None, after.observation_id,
                                       action.action_id if action else None]),
                        before.observation_id if before else None, after.observation_id,
                        action.action_id if action else None, bundle.changed_files, focus,
                        new, regressions, delta, comparable, outcome)
