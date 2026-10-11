"""Native integration behavior, independent of paid model/EDA availability."""
import importlib
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ace-rtl/scripts'))


def test_settings_default_fixed_and_extensions_off(monkeypatch):
    from ace_rtl_agent.decision.settings import DecisionSettings
    monkeypatch.delenv('ACE_RTL_DECISION_MODE', raising=False)
    settings = DecisionSettings.from_env()
    assert settings.mode == 'baseline_fixed'
    assert settings.enabled_extensions == ()
    monkeypatch.setenv('ACE_RTL_ENABLE_BEAM', 'true')
    with pytest.raises(ValueError):
        DecisionSettings.from_env()


def test_unimplemented_question_version_cannot_be_reported_as_active(monkeypatch):
    from ace_rtl_agent.decision.settings import DecisionSettings
    monkeypatch.setenv('ACE_RTL_QUESTION_SCHEMA_VERSION','nonexistent-version')
    with pytest.raises(ValueError,match='question'):
        DecisionSettings.from_env()


def test_run_task_and_attempt_deadlines_are_distinct_configuration(monkeypatch):
    from ace_rtl_agent.decision.settings import DecisionSettings
    monkeypatch.setenv('ACE_RTL_RUN_WALL_SECONDS','30')
    monkeypatch.setenv('ACE_RTL_TASK_WALL_SECONDS','20')
    monkeypatch.setenv('ACE_RTL_ATTEMPT_WALL_SECONDS','10')
    settings=DecisionSettings.from_env()
    assert (settings.run_wall_seconds,settings.task_wall_seconds,settings.wall_seconds)==(30,20,10)


def test_reflector_context_only_reads_declared_public_input(tmp_path):
    from ace_cvdp_native.llm import build_reflector_harness_context
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/private_checker.py').write_text('PRIVATE ANSWER')
    (tmp_path / 'src/.env').write_text('SECRET=bad')
    public = {'rtl/a.sv': 'old A', 'rtl/b.sv': 'old B', 'rtl/helper.sv': 'public helper'}
    text = build_reflector_harness_context(tmp_path, 'rtl/a.sv',
              mutable_targets=['rtl/a.sv', 'rtl/b.sv'], public_context=public)
    assert 'public helper' in text
    assert 'old A' not in text and 'old B' not in text
    assert 'PRIVATE' not in text and 'SECRET' not in text


def test_generator_rejects_undeclared_and_escaping_targets_before_writing(tmp_path, monkeypatch):
    from ace_cvdp_native import llm
    def response(**kwargs):
        kwargs['out_json'].write_text(json.dumps({'content': '// TARGET_FILE: rtl/a.sv\nmodule a; endmodule\n// TARGET_FILE: rtl/private.sv\nmodule bad; endmodule'}))
    monkeypatch.setattr(llm, 'run_role_call', response)
    model = llm.AceIterationModel(workspace=Path(__file__).resolve().parents[1], iteration_dir=tmp_path/'iter', cid='cid002',
              generator_model='configured',llm_timeout=5,reflection='',coordinator='',previous_candidate=None)
    model.prompt('Implement A', files=['rtl/a.sv', 'rtl/b.sv'])
    assert any('undeclared' in issue for issue in model.preflight_issues)
    assert not (tmp_path/'iter/candidate/rtl/private.sv').exists()
    with pytest.raises(ValueError):
        model.prompt('unsafe', files=['../private.sv'])


def test_reflector_returns_structured_guidance_without_full_generator_prompt(tmp_path):
    from ace_cvdp_native.llm import call_reflector
    from ace_rtl_agent.decision.types import TaskContract
    class Debugger:
        def create_focused_prompt(self, **kwargs):
            assert 'TARGET_FILE: rtl/b.sv' in kwargs['buggy_code']
            return 'FULL PROMPT WITH DUPLICATED SPEC', 'error-A', 'align valid and data'
    contract = TaskContract('t',task_kind='rtl_implementation',mutable_targets=('rtl/a.sv','rtl/b.sv'))
    content, meta = call_reflector(Debugger(),tmp_path,'t','rtl/a.sv','a','runtime failure',1,
                     'public spec','',candidate_files={'rtl/a.sv':'a','rtl/b.sv':'b'},task_contract=contract)
    assert 'DUPLICATED SPEC' not in content
    assert meta['target_files'] == ['rtl/a.sv','rtl/b.sv']
    assert 'error_reasoning' not in meta


@pytest.mark.parametrize('exit_code', [0, 1, 124])
def test_terminal_iteration_records_effect_without_optional_inference(tmp_path, monkeypatch, exit_code):
    import threading
    import types
    from argparse import Namespace
    from ace_cvdp_native import cli
    from ace_rtl_agent.decision.types import CandidateBundle
    calls = []
    recorded_observations = []
    class Model:
        def __init__(self, **kwargs):
            self.root = kwargs['iteration_dir']
            self.root.mkdir(parents=True)
            self.preflight_issues = []
            self.postprocess_actions = []
            self.generated_files = {}
            for name in ['rtl/a.sv','rtl/b.sv']:
                p = self.root/'candidate'/name
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('module a; endmodule')
                self.generated_files[name] = str(p)
            self.bundle = CandidateBundle.create({k:Path(v).read_text() for k,v in self.generated_files.items()}, episode_id='episode-1')
    class Processor:
        def __init__(self, **kwargs): pass
        def process_json(self): pass
        def prepare(self, issue, model):
            for name,path in model.generated_files.items():
                target=tmp_path/'harness'/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(Path(path).read_text())
            return issue, {}, types.SimpleNamespace(issue_path=str(tmp_path/'harness'))
        def run(self, **kwargs): return {'errors':int(exit_code!=0),'tests':[{'service':'1','result':exit_code,'execution':0.01}]}
    monkeypatch.setitem(sys.modules,'src',types.SimpleNamespace(dataset_processor=object()))
    monkeypatch.setattr(cli,'install_native_harness_patch',lambda:None)
    monkeypatch.setattr(cli,'select_generation_processor_class',lambda _:Processor)
    monkeypatch.setattr(cli,'AceIterationModel',Model)
    monkeypatch.setattr(cli,'FocusedDebugger',lambda *a,**kw:types.SimpleNamespace(fix_history=[],
                       record_observation=lambda observation,*a,**kw:recorded_observations.append(observation)))
    monkeypatch.setattr(cli,'FreshStartCoordinator',lambda *a,**kw:types.SimpleNamespace(set_harness_directory=lambda p:None))
    monkeypatch.setattr(cli,'call_coordinator',lambda *a,**kw:calls.append('coordinator'))
    monkeypatch.setattr(cli,'call_reflector',lambda *a,**kw:calls.append('reflector'))
    monkeypatch.setattr(cli,'record_reflector_iteration_result',lambda *a,**kw:calls.append('retrospective'))
    args=Namespace(cid='cid002',reflector_model='configured',coordinator_model='configured',
                   generator_model='configured',max_iterations=1,llm_timeout=5,evaluator_timeout=5,decision_mode='baseline_fixed')
    row={'id':'t','required_services':['1'],'categories':['cid002','easy'],'input':{'prompt':'Implement RTL','context':{}},
         'output':{'context':{'rtl/a.sv':'','rtl/b.sv':''}},'harness':{'services':{'1':{'type':'simulation'}}}}
    result=cli.run_attempt(workspace=tmp_path,cvdp_repo=tmp_path,row=row,row_jsonl=tmp_path/'row.jsonl',
              attempt_root=tmp_path/'dp/attempt_1',attempt_index=1,args=args,stop_event=threading.Event())
    assert calls == []
    assert len(recorded_observations) == 1
    iteration=tmp_path/'dp/attempt_1/iter_01'
    observation=json.loads((iteration/'observation.json').read_text())
    effect=json.loads((iteration/'effect.json').read_text())
    assert observation['iteration'] == 1
    assert effect['after_observation_id'] == observation['observation_id']
    assert result['history'][0]['observation']['observation_id'] == observation['observation_id']
    assert bool(result['status']=='passed') == bool(exit_code==0)
    events=[json.loads(line) for path in (tmp_path/'dp/events').glob('*.jsonl') for line in path.read_text().splitlines()]
    kinds={e.get('kind') for e in events}
    assert {'evaluation_started','evaluation_completed','attempt_terminated'} <= kinds


def test_model_diagnostics_strip_checker_source_and_credentials(tmp_path, monkeypatch):
    from ace_cvdp_native.llm import build_evaluator_error_report
    monkeypatch.setenv('SYSTEMONE_API_KEY','fixture-secret-never-prompt')
    log=tmp_path/'service.txt'
    log.write_text('>       expected = private_reference(signal)\nE       AssertionError: public output mismatch\nAPI_KEY=fixture-secret-never-prompt\n1 failed in 0.1s\n')
    report=build_evaluator_error_report({'errors':1,'tests':[{'service':'1','result':1,'log':str(log)}]},'{}')
    assert 'private_reference(signal)' not in report
    assert 'fixture-secret-never-prompt' not in report
    assert 'output mismatch' in report


def test_checker_source_excerpts_never_reach_model_diagnostics():
    from ace_cvdp_native.llm import sanitize_model_diagnostics
    text='def test_checker():\n    computed = scorer_lookup(dut.value)\n>   assert computed == table[index]\nE   raise AssertionError(table[index])\nE   AssertionError: public output mismatch\n'
    cleaned=sanitize_model_diagnostics(text)
    assert 'scorer_lookup' not in cleaned and 'table[index]' not in cleaned
    assert 'public output mismatch' in cleaned


def test_deep_action_uses_one_bounded_analysis_and_complete_bundle(tmp_path, monkeypatch):
    from ace_cvdp_native import llm
    from ace_rtl_agent.decision.types import TaskContract, CandidateBundle, Observation, ProposedAction
    calls=[]
    def role(**kwargs):
        calls.append(kwargs)
        kwargs['out_json'].write_text(json.dumps({'content':json.dumps({'analysis':'timing misalignment','guidance':'align pipeline'})}))
        return json.dumps({'analysis':'timing misalignment','guidance':'align pipeline'})
    monkeypatch.setattr(llm,'run_role_call',role)
    class Debugger:
        model_name='configured'
        def create_focused_prompt(self,**kwargs):raise AssertionError('deep must not use legacy focused analysis')
    contract=TaskContract('t',task_kind='rtl_implementation',mutable_targets=('rtl/a.sv','rtl/b.sv'))
    bundle=CandidateBundle.create({'rtl/a.sv':'module a; endmodule','rtl/b.sv':'module b; endmodule'},episode_id='e')
    observation=Observation('o',1,'t',1,'e',1,bundle.tested_hash,failed_checks=('1',))
    action=ProposedAction('act','o','reflect_deep',target_ids=contract.mutable_targets,error_id='1')
    content,meta=llm.call_reflector(Debugger(),tmp_path,'t','rtl/a.sv','a','public mismatch',1,'public spec','',
       candidate_files=dict(bundle.files),task_contract=contract,observation=observation,bundle=bundle,action=action)
    assert len(calls)==1
    assert 'rtl/b.sv' in calls[0]['prompt']
    assert 'align pipeline' in content and 'timing misalignment' in content
    assert meta['action_kind']=='reflect_deep'


def test_runtime_error_candidates_are_distinct_not_prose_counts():
    from ace_cvdp_native.llm import diagnostic_error_candidates
    text='E AssertionError: reset output mismatch\nE AssertionError: reset output mismatch\nE AssertionError: valid/data latency mismatch'
    errors=diagnostic_error_candidates(text,service_ids=('sanity',))
    assert len(errors)==2
    assert len(set(errors))==2
    assert all(item['cause_verified'] is False for item in errors.values())


@pytest.mark.parametrize('mode,choice', [('jev_core','fresh_start'),('shadow','fresh_start'),
                                        ('jev_core','repair_with_template')])
def test_native_core_actions_and_shadow_reach_next_generator(tmp_path, monkeypatch, mode, choice):
    import threading,types
    from argparse import Namespace
    from ace_cvdp_native import cli
    from ace_rtl_agent.decision import systemone_client
    generated=[];requests=[]
    class Model:
        def __init__(self, **kw):
            generated.append(kw); self.generated_files={};self.preflight_issues=[];self.postprocess_actions=[]
            for name in ('rtl/a.sv','rtl/b.sv'):
                path=kw['iteration_dir']/'candidate'/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('module a; endmodule\n'+str(len(generated)))
                self.generated_files[name]=str(path)
    class Processor:
        def __init__(self,**kw):pass
        def process_json(self):pass
        def prepare(self,issue,model):
            for name,path in model.generated_files.items():
                target=tmp_path/'harness'/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(Path(path).read_text())
            return issue,{},types.SimpleNamespace(issue_path=str(tmp_path/'harness'))
        def run(self,**kw):return {'errors':int(len(generated)==1),'tests':[{'service':'1','result':int(len(generated)==1),
                                    'execution':.1,'error_msg':'syntax error rtl/a.sv' if len(generated)==1 else None}]}
    class Debugger:
        def __init__(self,*a,**kw):self.fix_history=[]
        def record_observation(self,*a,**kw):pass
        def clear_history(self):self.fix_history=[]
        def create_focused_prompt(self,**kw):return 'full prompt','error','repair guidance'
    class Coordinator:
        def __init__(self,*a,**kw):pass
        def add_iteration_result(self,**kw):pass
        def should_fresh_start(self,iteration):return False,'continue'
        def mark_fresh_start(self,iteration):pass
    class Client:
        def decide(self,state,questions,**kw):
            requests.append(state)
            answers={}
            for key,q in questions.items():
                if q['type']=='noul':answers[key]={'type':'noul','noul':0.0 if key.startswith('risk_') else 1.0}
                elif q['type']=='score':answers[key]={'type':'score','score':2.0}
                else:
                    selected=choice if key=='next_action' else next(iter(q['criteria']))
                    answers[key]={'type':'choice','choice':selected,'confidence':1.0,'probabilities':{k:float(k==selected) for k in q['criteria']}}
            return {'answers':answers,'requested_model':'configured','resolved_model':None,'usage':{'source':'unknown'}}
    monkeypatch.setitem(sys.modules,'src',types.SimpleNamespace(dataset_processor=object()))
    monkeypatch.setattr(cli,'install_native_harness_patch',lambda:None)
    monkeypatch.setattr(cli,'select_generation_processor_class',lambda _:Processor)
    monkeypatch.setattr(cli,'AceIterationModel',Model)
    monkeypatch.setattr(cli,'FocusedDebugger',Debugger);monkeypatch.setattr(cli,'FreshStartCoordinator',Coordinator)
    monkeypatch.setattr(systemone_client.SystemOneClient,'from_env',lambda:Client())
    args=Namespace(cid='cid002',reflector_model='configured',coordinator_model='configured',generator_model='configured',
                   max_iterations=2,llm_timeout=5,evaluator_timeout=5,decision_mode=mode)
    row={'id':'t','required_services':['1'],'categories':['RTL implementation','easy'],'input':{'prompt':'Implement RTL','context':{}},
         'output':{'context':{'rtl/a.sv':'','rtl/b.sv':''}},'harness':{'services':{'1':{}}}}
    result=cli.run_attempt(workspace=tmp_path,cvdp_repo=tmp_path,row=row,row_jsonl=tmp_path/'row.jsonl',
              attempt_root=tmp_path/'dp/attempt_1',attempt_index=1,args=args,stop_event=threading.Event())
    assert result['status']=='passed'
    assert len(requests)==1 and len(generated)==2
    assert bool(generated[1]['previous_candidate']) == bool(mode=='shadow' or choice!='fresh_start')
    assert generated[1]['task_contract'].task_kind=='rtl_implementation'
    if choice=='repair_with_template':assert 'reported syntax' in generated[1]['reflection']
    assert result['history'][1]['effect']['action_id'] is not None


def test_parent_enforces_wall_deadline_even_when_child_never_returns(tmp_path,monkeypatch):
    import queue,threading,types
    from argparse import Namespace
    from ace_cvdp_native import cli
    monkeypatch.setenv('ACE_RTL_TASK_WALL_SECONDS','.001')
    class Queue(queue.Queue):
        def close(self):pass
        def join_thread(self):pass
    class Process:
        pid=None
        exitcode=None
        def __init__(self,**kw):self.alive=False
        def start(self):self.alive=True
        def is_alive(self):return self.alive
        def join(self,**kw):pass
    monkeypatch.setattr(cli.multiprocessing,'get_context',lambda _:types.SimpleNamespace(Event=threading.Event,Queue=Queue,Process=Process))
    def stop(**kw):
        kw['process'].alive=False
        assert kw['cancellation_reason']=='budget_exhausted'
        return {'attempt':1,'status':'cancelled','cancellation_reason':'budget_exhausted'}
    monkeypatch.setattr(cli,'stop_attempt_process',stop)
    args=Namespace(attempts=1,decision_mode='baseline_fixed')
    row={'id':'t','output':{'context':{'rtl/a.sv':''}},'categories':['cid002','easy']}
    result=cli.run_datapoint(workspace=tmp_path,cvdp_repo=tmp_path,row=row,run_dir=tmp_path,args=args)
    assert result['passed'] is False
    assert result['attempts'][0]['status']=='budget_exhausted'


def test_tested_hash_binds_actual_prepared_mutable_files_not_assumed_model_bytes(tmp_path):
    import types
    from ace_cvdp_native.llm import bind_prepared_candidate
    from ace_rtl_agent.decision.types import CandidateBundle,canonical_hash
    normalized={'rtl/a.sv':'module a; parameter N=__PUBLIC_TEMPLATE__; endmodule'}
    tested={'rtl/a.sv':'module a; parameter N=8; endmodule'}
    path=tmp_path/'candidate/rtl/a.sv';path.parent.mkdir(parents=True);path.write_text(normalized['rtl/a.sv'])
    prepared=tmp_path/'prepared'
    target=prepared/'rtl/a.sv';target.parent.mkdir(parents=True);target.write_text(tested['rtl/a.sv'])
    model=types.SimpleNamespace(generated_files={'rtl/a.sv':str(path)},postprocess_actions=[],preflight_issues=[],
              bundle=CandidateBundle.create(normalized,episode_id='e'))
    bundle=bind_prepared_candidate(model,prepared,['rtl/a.sv'],iteration_dir=tmp_path,episode_id='e')
    assert bundle.normalized_hash==canonical_hash(normalized)
    assert bundle.tested_hash==canonical_hash(tested)
    assert bundle.files==tested
    assert path.read_text()==normalized['rtl/a.sv']
    assert Path(model.generated_files['rtl/a.sv']).read_text()==tested['rtl/a.sv']
