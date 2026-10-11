"""Explicit runtime modes; experiments never enable themselves."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path

MODES = ('legacy', 'baseline_fixed', 'shadow', 'jev_core', 'jev_extended')
EXTENSIONS = {'beam': 'ACE_RTL_ENABLE_BEAM',
              'adaptive_scheduling': 'ACE_RTL_ENABLE_ADAPTIVE_SCHEDULING',
              'model_routing': 'ACE_RTL_ENABLE_MODEL_ROUTING',
              'lesson_memory': 'ACE_RTL_ENABLE_LESSON_MEMORY',
              'learned_policy': 'ACE_RTL_ENABLE_LEARNED_POLICY'}


@dataclass(frozen=True)
class DecisionSettings:
    mode: str = 'baseline_fixed'
    enabled_extensions: tuple[str, ...] = ()
    beam_width: int = 2
    max_restarts: int = 2
    max_decisions_per_candidate: int = 3
    wall_seconds: float = 600.0
    evaluation_cache_mode: str = 'off'
    question_version: str = 'jev-questions-1'
    policy: dict | None = None
    model_aliases: dict | None = None
    task_wall_seconds: float = 1200.0
    run_wall_seconds: float = 1800.0

    @classmethod
    def from_env(cls, mode=None):
        budget_path=os.environ.get('ACE_RTL_RUN_BUDGET_FILE')
        if budget_path:
            budget=json.loads(Path(budget_path).read_text())
            campaign=Path(budget['campaign_file'])
            if not campaign.is_absolute():campaign=Path(budget_path).resolve().parent/campaign
            existing=os.environ.get('ACE_EXPERIMENT_BUDGET_FILE')
            if existing and Path(existing).resolve()!=campaign.resolve():
                raise ValueError('run budget file conflicts with prepared campaign')
            os.environ.setdefault('ACE_EXPERIMENT_BUDGET_FILE',str(campaign.resolve()))
            if budget.get('scope_limits'):
                from .budget import campaign as campaign_module
                campaign_module().init_scope_limits(campaign,budget['scope_limits'])
            for scope in ('run','task','attempt'):
                if scope+'_wall_seconds' in budget:
                    os.environ.setdefault('ACE_RTL_'+scope.upper()+'_WALL_SECONDS',str(budget[scope+'_wall_seconds']))
        selected = mode or os.environ.get('ACE_RTL_DECISION_MODE', 'baseline_fixed')
        if selected not in MODES:
            raise ValueError('invalid decision mode')
        enabled = tuple(k for k,v in EXTENSIONS.items() if os.environ.get(v,'false').lower() in ('true','1','yes'))
        if enabled and selected != 'jev_extended':
            raise ValueError('X extensions require explicit jev_extended mode')
        policy = {}
        path = os.environ.get('ACE_RTL_POLICY_FILE')
        if path:
            policy = json.loads(Path(path).read_text())
            if not isinstance(policy, dict):
                raise ValueError('policy must be an object')
            from .state_builder import assert_public
            assert_public(policy)
        seconds = float(os.environ.get('ACE_RTL_ATTEMPT_WALL_SECONDS', 600))
        task_seconds = float(os.environ.get('ACE_RTL_TASK_WALL_SECONDS',1200))
        run_seconds = float(os.environ.get('ACE_RTL_RUN_WALL_SECONDS',1800))
        width = int(os.environ.get('ACE_RTL_BEAM_WIDTH', 2))
        if any(not math.isfinite(x) or x <= 0 for x in (seconds,task_seconds,run_seconds)) or not 1 <= width <= 8:
            raise ValueError('finite positive wall budget and beam width 1..8 required')
        aliases = json.loads(os.environ.get('ACE_RTL_MODEL_ALIASES', '{}'))
        question_version = os.environ.get('ACE_RTL_QUESTION_SCHEMA_VERSION','jev-questions-1')
        from .questions import QUESTION_REGISTRY
        if question_version not in QUESTION_REGISTRY:
            raise ValueError('unknown question schema version')
        return cls(selected, enabled, width, int(policy.get('max_restarts',2)),
                   int(policy.get('max_decisions_per_candidate',3)), seconds,
                   os.environ.get('ACE_RTL_EVALUATION_CACHE_MODE','off'),
                   question_version,policy,aliases,task_seconds,run_seconds)
