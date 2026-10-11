"""Native opt-in extension adapters. All unmeasured predictions are advice only."""
from dataclasses import asdict
import json
from pathlib import Path
from ace_rtl_agent.decision.extensions import route_model, load_lesson_snapshot


def route_roles(settings, decision, *, failures, default_model):
    if 'model_routing' not in settings.enabled_extensions:
        return {'generator_model':default_model,'reflector_model':None,'max_output_tokens':None,'reason':'disabled'}
    config=settings.policy or {}
    risks={k: v.get('noul') for k,v in (decision.answers.items() if decision else []) if k.startswith('risk_')}
    route=route_model(settings.model_aliases or {},local_alias=config.get('local_model_alias','local'),
          strong_alias=config.get('strong_model_alias','strong'),risks=risks,failures=failures,
          complex_redesign=bool(decision and decision.chosen_action and decision.chosen_action.action_kind=='fresh_start'),
          enabled=True)
    if not route.allowed:
        raise ValueError('model route violates structural hard gate')
    return {'generator_model':route.model,'reflector_model':route.model,'max_output_tokens':route.max_output_tokens,
            'reason':route.reason,'alias':route.alias,'evaluator_required':True}


def load_learned_policy(path, *, question_version, policy_version, model_version):
    artifact=json.loads(Path(path).read_text())
    if artifact.get('production_ready') is not True or artifact.get('validation',{}).get('held_out_valid_evaluations',0)<1:
        raise ValueError('learned policy requires a separately validated non-fixture artifact')
    if artifact.get('artifact_version')!='ace-offline-stump-1' or any(artifact.get(k)!=v for k,v in
          [('question_version',question_version),('policy_version',policy_version),('model_version',model_version)]):
        raise ValueError('learned policy pinned versions do not match')
    return artifact


def lesson_guidance(path, version, contract):
    snapshot=load_lesson_snapshot(path,expected_version=version)
    lessons=snapshot.retrieve(contract.category,contract.task_id)
    return {'snapshot_digest':snapshot.digest,'snapshot_version':snapshot.version,
            'lesson_ids':[x.lesson_id for x in lessons],
            'guidance':'\n'.join(x.text for x in lessons),'frozen':True}
