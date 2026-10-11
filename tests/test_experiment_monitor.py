import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def test_only_completed_case_orphans_belong_to_cleanup_scope(tmp_path):
    monitor=importlib.import_module('watch_experiment')
    batch=tmp_path/'batch';case=batch/'cases'/'finished'
    case.mkdir(parents=True);(case/'result.json').write_text(json.dumps({'status':'failure'}))
    owned=str(case/'native'/'simulation.vvp')
    assert monitor.finished_orphan_case(batch,'vvp',1,[owned])=='finished'
    assert monitor.finished_orphan_case(batch,'vvp',123,[owned]) is None
    assert monitor.finished_orphan_case(batch,'python',1,[owned]) is None
    assert monitor.finished_orphan_case(batch,'vvp',1,[str(batch/'cases'/'running'/'native'/'simulation.vvp')]) is None
    assert monitor.finished_orphan_case(batch,'vvp',1,[str(tmp_path/'batch-other'/'cases'/'finished'/'sim.vvp')]) is None


def test_finished_iteration_is_cleanable_without_stopping_live_case(tmp_path):
    monitor=importlib.import_module('watch_experiment')
    batch=tmp_path/'batch'
    iteration=batch/'cases'/'active'/'native'/'run'/'datapoints'/'active'/'attempt_1'/'iter_02'
    iteration.mkdir(parents=True)
    owned=str(iteration/'cvdp_work'/'task'/'rundir'/'sim.vvp')
    assert monitor.finished_orphan_case(batch,'vvp',1,[owned]) is None
    (iteration/'real_evaluator_result.json').write_text('{}')
    assert monitor.finished_orphan_case(batch,'vvp',1,[owned])=='active'
