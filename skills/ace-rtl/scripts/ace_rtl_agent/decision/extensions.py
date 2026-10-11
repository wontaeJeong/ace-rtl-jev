"""Opt-in X-01..04 algorithms; no model calls or runtime activation here.

Selection probabilities are search heuristics, never evaluator pass probabilities.
Callers gate these APIs with pinned settings and reserve actual run budgets before
dispatch. Scheduling only admits the *next* checkpoint; it never kills a worker.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

from .types import CandidateBundle, Observation, ProposedAction, canonical_hash, validate_target


def _probability(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('expected finite probability in [0, 1]')
    return float(value)


@dataclass(frozen=True)
class BranchPlan:
    selected: tuple[str, ...]
    discarded: Mapping[str, str]
    heuristic_scores: Mapping[str, float]
    checkpoint_budget: int


def select_branches(distribution, strategies, budget, max_width=2, margin=.1):
    """Choose close, semantically distinct eligible strategies.

    budget is an integer number of reserved branch checkpoints, not money/tokens.
    strategies maps IDs to metadata with required semantic_family, optional
    eligible flag and action_kind. Missing diversity metadata is rejected.
    """
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ValueError('budget must be nonnegative checkpoint count')
    if isinstance(max_width, bool) or not isinstance(max_width, int) or max_width < 1:
        raise ValueError('max_width must be positive')
    margin = _probability(margin)
    scores = {key: _probability(value) for key, value in distribution.items()}
    if scores and not math.isclose(sum(scores.values()), 1, abs_tol=1e-6):
        raise ValueError('distribution must sum to one')
    discarded, eligible = {}, []
    for key in scores:
        if key not in strategies or not strategies[key].get('semantic_family'):
            raise ValueError('strategy must declare semantic_family')
        if strategies[key].get('eligible', True):
            eligible.append(key)
        else:
            discarded[key] = 'ineligible'
    ranked = sorted(eligible, key=lambda key: (-scores[key], key))
    selected, families = [], set()
    for key in ranked:
        family = strategies[key]['semantic_family']
        if family in families:
            discarded[key] = 'semantic_duplicate'
        elif ranked and scores[ranked[0]] - scores[key] > margin + 1e-12:
            discarded[key] = 'outside_margin'
        elif len(selected) >= min(max_width, budget):
            discarded[key] = 'checkpoint_budget_or_width'
        else:
            selected.append(key)
            families.add(family)
    return BranchPlan(tuple(selected), MappingProxyType(discarded), MappingProxyType(scores), budget)


@dataclass(frozen=True)
class BranchCheckpoint:
    branch_id: str
    strategy_id: str
    directory: Path
    parent_candidate_id: str
    observation_id: str
    action: ProposedAction
    checkpoint_budget: int


def materialize_branches(plan, parent: CandidateBundle, observation: Observation, root,
                         *, checkpoint_version, action_kind='reflect_focused'):
    """Copy a frozen best/active bundle into exclusive branch directories.

    Not rollback or fresh_start: shared spending/ledger must remain monotonic in
    the orchestrator. Existing branch paths are never overwritten. The manifest
    preserves the discarded alternatives for later exploration audits.
    """
    if parent.tested_hash != observation.tested_hash or parent.episode_id != observation.episode_id:
        raise ValueError('parent and observation provenance mismatch')
    if not checkpoint_version:
        raise ValueError('checkpoint policy version required')
    from .types import ACTION_KINDS
    if action_kind not in ACTION_KINDS:
        raise ValueError('unknown action kind')
    results = []
    for index, strategy in enumerate(plan.selected):
        branch_id = canonical_hash([parent.candidate_id, observation.observation_id,
                                    observation.version, strategy, checkpoint_version])[:24]
        directory = Path(root) / branch_id
        directory.mkdir(parents=True, exist_ok=False)
        for name, content in parent.files.items():
            target = directory / validate_target(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        allocation = plan.checkpoint_budget // len(plan.selected) + (index < plan.checkpoint_budget % len(plan.selected))
        action = ProposedAction(branch_id + '-action', observation.observation_id, action_kind,
                                tuple(parent.files), strategy_id=strategy,
                                observation_version=observation.version, tested_hash=parent.tested_hash)
        manifest = {'branch_id': branch_id, 'strategy_id': strategy,
                    'parent_candidate_id': parent.candidate_id, 'parent_tested_hash': parent.tested_hash,
                    'episode_id': parent.episode_id, 'observation_id': observation.observation_id,
                    'observation_version': observation.version, 'checkpoint_version': checkpoint_version,
                    'action': action.to_dict(), 'checkpoint_budget': allocation,
                    'discarded': dict(plan.discarded), 'outcome': 'not_executed'}
        (directory / 'branch.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
        results.append(BranchCheckpoint(branch_id, strategy, directory, parent.candidate_id,
                                        observation.observation_id, action, allocation))
    return tuple(results)


@dataclass(frozen=True)
class AttemptCheckpoint:
    attempt_id: str
    progress: float | None = None
    relevance: float = .5
    risk: float = .5
    novelty: float = .5
    cost: float | None = None
    paid_inflight: bool = False
    at_checkpoint: bool = True
    terminal: bool = False
    candidate_id: str = ''
    observation_id: str = ''
    policy_version: str = ''


class AdaptiveScheduler:
    """Least-served-first allocation, semantic/cost score breaks fair ties.

    Every attempt receives minimum_checkpoints before exploitation. Thereafter
    least-served cohorts prevent starvation even for unknown progress. Admission
    counters count reserved checkpoints, not valid evaluations. Failed/cancelled
    evaluations must still be recorded independently. No process pause/resume.
    """
    cancel_attempts = ()

    def __init__(self, minimum_checkpoints=1, *, enabled=False):
        if not isinstance(minimum_checkpoints, int) or minimum_checkpoints < 1:
            raise ValueError('minimum exploration must be positive')
        self.minimum_checkpoints = minimum_checkpoints
        self.enabled = enabled
        self.allocations = {}

    def allocate(self, checkpoints, budget):
        if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
            raise ValueError('budget must be nonnegative checkpoint count')
        if len({s.attempt_id for s in checkpoints}) != len(checkpoints):
            raise ValueError('duplicate attempt IDs')
        ready = [s for s in checkpoints if s.at_checkpoint and not s.paid_inflight and not s.terminal]
        def rank(s):
            served = self.allocations.get(s.attempt_id, 0)
            relevance, risk, novelty = map(_probability, (s.relevance, s.risk, s.novelty))
            progress = .5 if s.progress is None else _probability(s.progress)
            if s.cost is not None and (not math.isfinite(s.cost) or s.cost < 0):
                raise ValueError('invalid checkpoint cost')
            score = (progress + relevance + novelty + 1 - risk) / (1 + (s.cost or 0))
            return (served >= self.minimum_checkpoints, served, -score, s.attempt_id)
        ordered = sorted(ready, key=rank) if self.enabled else ready
        chosen = tuple(s.attempt_id for s in ordered[:budget])
        for attempt in chosen:
            self.allocations[attempt] = self.allocations.get(attempt, 0) + 1
        return chosen


@dataclass(frozen=True)
class ModelRoute:
    alias: str
    model: str
    max_output_tokens: int
    allowed: bool
    reason: str
    evaluator_required: bool = True


def route_model(aliases, *, local_alias, strong_alias, risks=None, hard_violations=(),
                failures=0, complex_redesign=False, enabled=False, risk_threshold=.7,
                failure_threshold=2, local_output_tokens=2048, strong_output_tokens=4096):
    """Aliases only; maximum individual risk, never average, controls promotion."""
    if local_alias not in aliases or strong_alias not in aliases or not aliases[local_alias] or not aliases[strong_alias]:
        raise ValueError('routing aliases must be configured')
    if min(local_output_tokens, strong_output_tokens, failure_threshold) < 1 or failures < 0:
        raise ValueError('invalid routing budget/threshold')
    threshold = _probability(risk_threshold)
    risks = risks or {}
    known = [_probability(value) for value in risks.values() if value is not None]
    unknown = any(value is None for value in risks.values())
    promote = enabled and (complex_redesign or unknown or max(known, default=0) >= threshold or failures >= failure_threshold)
    alias = strong_alias if promote else local_alias
    return ModelRoute(alias, aliases[alias], strong_output_tokens if promote else local_output_tokens,
                      not bool(hard_violations), 'hard_violation' if hard_violations else
                      'risk_or_complexity_promotion' if promote else 'local_or_disabled')


@dataclass(frozen=True)
class Lesson:
    lesson_id: str
    text: str
    family: str
    source_task_id: str
    observation_ids: tuple[str, ...]
    action_ids: tuple[str, ...]
    evaluation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    preconditions: tuple[str, ...]
    counterexamples: tuple[str, ...] = ()
    status: str = 'candidate'
    generator_version: str = ''
    evaluator_version: str = ''
    public: bool = True
    contains_solution: bool = False

    def __post_init__(self):
        for name in ('observation_ids', 'action_ids', 'evaluation_ids', 'evidence_ids',
                     'preconditions', 'counterexamples'):
            values = tuple(getattr(self, name))
            if len(values) > 32 or any(not isinstance(value, str) or len(value) > 1000 for value in values):
                raise ValueError('lesson reference/precondition bounds exceeded')
            object.__setattr__(self, name, values)


def curate_lessons(lessons, available_evidence_ids, *, confirmed_evaluations=(), max_lessons=32,
                   max_text_chars=1000):
    """Deterministic curation of supplied public summaries; never writes new advice.

    confirmed_evaluations must be independently validated supporting evaluations,
    not merely IDs of failures. Counterexamples block promotion. No score can
    bypass public provenance or automatically promote unsupported hypotheses.
    """
    from dataclasses import replace
    if max_lessons < 1 or max_text_chars < 1:
        raise ValueError('lesson bounds must be positive')
    result, seen = [], set()
    for lesson in lessons:
        if not lesson.public:
            continue
        if not all((lesson.family, lesson.source_task_id, lesson.observation_ids, lesson.action_ids,
                    lesson.evaluation_ids, lesson.evidence_ids, lesson.preconditions,
                    lesson.generator_version, lesson.evaluator_version)):
            raise ValueError('lesson provenance and versions required')
        if not set(lesson.evidence_ids) <= set(available_evidence_ids):
            raise ValueError('unavailable lesson evidence')
        if not lesson.text.strip() or len(lesson.text) > max_text_chars:
            raise ValueError('lesson text exceeds bound or is empty')
        digest = canonical_hash([lesson.family, ' '.join(lesson.text.casefold().split()), lesson.preconditions])
        if digest in seen:
            continue
        seen.add(digest)
        status = 'confirmed' if set(lesson.evaluation_ids) <= set(confirmed_evaluations) and not lesson.counterexamples else 'candidate'
        result.append(replace(lesson, status=status))
        if len(result) >= max_lessons:
            break
    return tuple(result)


@dataclass(frozen=True)
class LessonSnapshot:
    version: str
    digest: str
    lessons: tuple[Lesson, ...]

    def retrieve(self, family, task_id, *, include_candidates=False, limit=8):
        if limit < 0:
            raise ValueError('negative retrieval limit')
        # Even if metadata forgot to flag solution code, obvious RTL is excluded.
        def safe(lesson):
            code = re.search(r'\b(module|endmodule|always_ff|always_comb)\b|```', lesson.text)
            return lesson.source_task_id == task_id or not (lesson.contains_solution or code)
        return tuple(l for l in self.lessons if l.public and l.family == family and safe(l)
                     and (include_candidates or l.status == 'confirmed'))[:limit]


class LessonStore:
    def __init__(self, max_lessons=32):
        if max_lessons < 1:
            raise ValueError('positive memory bound required')
        self.max_lessons = max_lessons
        self._lessons = {}
        self._frozen = False

    def add(self, lesson):
        if self._frozen:
            raise RuntimeError('evaluation memory is frozen')
        if not lesson.public or len(lesson.text) > 1000 or lesson.status not in ('candidate', 'confirmed'):
            raise ValueError('invalid/public bounded lesson required')
        if not all((lesson.lesson_id, lesson.text.strip(), lesson.family, lesson.source_task_id,
                    lesson.observation_ids, lesson.action_ids, lesson.evaluation_ids,
                    lesson.evidence_ids, lesson.preconditions, lesson.generator_version,
                    lesson.evaluator_version)):
            raise ValueError('lesson provenance and versions required')
        if lesson.lesson_id in self._lessons:
            if self._lessons[lesson.lesson_id] != lesson:
                raise ValueError('lesson IDs are immutable')
            return
        if len(self._lessons) >= self.max_lessons:
            raise ValueError('memory capacity reached')
        self._lessons[lesson.lesson_id] = lesson

    def freeze(self, path, *, version):
        if not version:
            raise ValueError('memory version required')
        lessons = tuple(self._lessons[k] for k in sorted(self._lessons))
        payload = {'version': version, 'lessons': [asdict(l) for l in lessons]}
        digest = canonical_hash(payload)
        with Path(path).open('x', encoding='utf-8') as stream:
            json.dump(dict(payload, digest=digest), stream, sort_keys=True)
        self._frozen = True
        return LessonSnapshot(version, digest, lessons)


def load_lesson_snapshot(path, *, expected_version, max_lessons=32):
    """Load an explicitly pinned immutable evaluation memory with integrity check."""
    text = Path(path).read_text(encoding='utf-8')
    if len(text) > max_lessons * 16000:
        raise ValueError('memory artifact exceeds bounded size')
    payload = json.loads(text)
    digest = payload.pop('digest', None)
    if payload.get('version') != expected_version or digest != canonical_hash(payload):
        raise ValueError('memory version or digest mismatch')
    if len(payload['lessons']) > max_lessons:
        raise ValueError('memory capacity exceeded')
    store = LessonStore(max_lessons)
    for item in payload['lessons']:
        store.add(Lesson(**item))
    return LessonSnapshot(expected_version, digest, tuple(store._lessons.values()))
