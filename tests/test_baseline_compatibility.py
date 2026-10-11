import importlib.util
import json
import sys
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ace-rtl/scripts'
sys.path.insert(0, str(SCRIPTS))


def test_reusable_backend_uses_external_adapter_without_nvidia_key(tmp_path, monkeypatch):
    from ace_rtl_agent.llm_backend import LLMBackend
    adapter = tmp_path / 'adapter.py'
    adapter.write_text('import sys,json\nr=json.load(sys.stdin)\nprint(json.dumps({"content":r["messages"][0]["content"]+" adapted"}))\n')
    monkeypatch.setenv('ACE_RTL_LLM_SCRIPT', str(adapter))
    monkeypatch.delenv('NVIDIA_API_KEY', raising=False)
    backend = LLMBackend(model='local-model')
    assert backend.prompt('public prompt') == 'public prompt adapted'


def test_download_reuses_current_split_heavy_dataset(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('download', SCRIPTS / 'download_cvdp_datasets.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = [
        'agentic_code_generation_commercial', 'agentic_code_generation_no_commercial',
        'agentic_heavy_code_generation_commercial', 'agentic_heavy_code_generation_no_commercial',
        'nonagentic_code_comprehension', 'nonagentic_code_generation_commercial',
        'nonagentic_code_generation_no_commercial',
    ]
    for name in names:
        (tmp_path / f'cvdp_v1.1.0_{name}.jsonl').write_text('{}\n')
    monkeypatch.setattr(sys, 'argv', ['download', '--target-dir', str(tmp_path)])
    import huggingface_hub
    def reject_network(**kwargs):
        raise AssertionError('complete local dataset must not trigger network')
    monkeypatch.setattr(huggingface_hub, 'snapshot_download', reject_network)
    assert module.main() == 0


def test_native_harness_preserves_virtualenv_python_and_tools(tmp_path):
    from ace_cvdp_native.harness import compose_env
    env = compose_env({}, None, tmp_path)
    assert env['PATH'].split(':')[0] == str(Path(sys.prefix) / 'bin')
    assert env['PYGPI_PYTHON_BIN'] == str(Path(sys.executable).absolute())


def test_portable_process_discovery_finds_owned_children_not_similar_paths(tmp_path):
    import os
    from ace_cvdp_native.processes import descendant_pids, pids_matching_path, proc_matches_path
    root=tmp_path/'owned';root.mkdir()
    owned=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)',str(root/'simulation.vvp')])
    other=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)',str(tmp_path/'owned-other'/'simulation.vvp')])
    try:
        assert owned.pid in descendant_pids(os.getpid())
        assert owned.pid in pids_matching_path(root)
        assert proc_matches_path(other.pid,root) is False
    finally:
        for p in (owned,other):p.terminate();p.wait()


def test_evaluator_environment_does_not_receive_model_credentials(tmp_path,monkeypatch):
    from ace_cvdp_native.harness import compose_env
    for name in ('LLM_API_KEY','JEV_API_KEY','NVIDIA_API_KEY','OPENAI_API_KEY','OPENAI_USER_KEY','ACE_EXPERIMENT_BUDGET_FILE'):
        monkeypatch.setenv(name,'secret-fixture-value')
    env=compose_env({},None,tmp_path)
    assert all(name not in env for name in ('LLM_API_KEY','JEV_API_KEY','NVIDIA_API_KEY','OPENAI_API_KEY','OPENAI_USER_KEY','ACE_EXPERIMENT_BUDGET_FILE'))
