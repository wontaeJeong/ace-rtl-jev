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


def apply_reflector_route(debugger, route):
    if not route.get('reflector_model'):return
    debugger.model_name=route['reflector_model']
    if getattr(debugger,'llm_client',None):
        debugger.llm_client.model=route['reflector_model']
        debugger.llm_client.client.model=route['reflector_model']
        debugger.llm_client.max_output_tokens=route['max_output_tokens']


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


def curate_episode_lesson(observation, action, evidence, *, family, generator_version,
                          evaluator_version, client=None, timeout=5):
    """Emit bounded candidate lessons; evaluation memory is never updated online."""
    from ace_rtl_agent.decision.extensions import Lesson,curate_lessons
    from ace_rtl_agent.decision.types import canonical_hash
    from ace_rtl_agent.decision.state_builder import public_evidence,public_observation
    clean=public_evidence(evidence,observation)
    if not action or not clean:
        return {'lesson':None,'reason':'insufficient_action_or_public_evidence','active_memory_updated':False}
    text=f'Observed {observation.evaluator_status} in this episode. Preserve the public interface and previously verified passing constraints; the root cause remains unconfirmed.'
    lesson=Lesson(canonical_hash([observation.observation_id,action.action_id,text]),text,family,observation.task_id,
            (observation.observation_id,),(action.action_id,),(observation.observation_id,),
            tuple(e.evidence_id for e in clean),('same public task contract and observed failure stage',),
            generator_version=generator_version,evaluator_version=evaluator_version)
    envelope=None
    if client:
        envelope=client.decide({'purpose':'lesson_curation','lesson':asdict(lesson),'observation':public_observation(observation),
                    'evidence':[e.to_dict() for e in clean]},
            {'supported':{'type':'noul','instructions':'Is state.lesson supported by the supplied state.observation and public state.evidence? Do not infer a cause or solution.'},
             'applicable':{'type':'noul','instructions':'Does state.lesson apply under its explicit same-task-contract preconditions, without claiming a general verified rule?'}},timeout=timeout)
        if any(envelope.get('answers',{}).get(k,{}).get('noul',0)<.7 for k in ('supported','applicable')):
            return {'lesson':None,'reason':'unsupported_or_inapplicable','decision':envelope,'active_memory_updated':False}
    curated=curate_lessons((lesson,),[e.evidence_id for e in clean],confirmed_evaluations=())
    return {'lesson':asdict(curated[0]),'decision':envelope,'active_memory_updated':False,
            'status':'candidate_only','experimental_threshold':.7}
