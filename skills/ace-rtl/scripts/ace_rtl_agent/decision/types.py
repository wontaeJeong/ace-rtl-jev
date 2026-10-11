"""Shared versioned contracts. Unknown measurements are never invented."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import difflib
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Mapping

SCHEMA_VERSION = 'ace-decision-1'
FOCUS_STATUSES = ('persists', 'observed_resolved', 'masked', 'not_executed', 'unknown')
ACTION_KINDS = ('repair_with_template', 'reflect_focused', 'reflect_deep', 'switch_focus',
                'gather_evidence', 'rollback_best', 'fresh_start', 'retry_evaluator')


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate_target(path: str) -> str:
    normalized = path.replace('\\', '/')
    parsed = PurePosixPath(normalized)
    if not normalized or parsed.is_absolute() or '..' in parsed.parts or ':' in normalized or normalized != parsed.as_posix():
        raise ValueError('target must be a canonical relative manifest path')
    return normalized


class FrozenDict(dict):
    """JSON-compatible immutable map; constructor copies caller-owned values."""
    def _immutable(self, *args, **kwargs):
        raise TypeError('contract maps are immutable')
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable

    def __reduce__(self):
        # Spawn/Queue transport must reconstruct through the copying constructor,
        # not pickle's incremental __setitem__ protocol.
        return (type(self),(dict(self),))


def _freeze(value):
    if isinstance(value, dict):
        return FrozenDict((key, _freeze(item)) for key,item in value.items())
    if isinstance(value, (list,tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class Serializable:
    def __post_init__(self):
        for item in fields(self):
            object.__setattr__(self,item.name,_freeze(getattr(self,item.name)))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TaskContract(Serializable):
    task_id: str
    cid: str = ''
    category: str = ''
    task_kind: str = 'unknown'
    spec_hash: str = ''
    mutable_targets: tuple[str, ...] = ()
    immutable_context: Mapping[str, str] = field(default_factory=dict)
    required_services: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    allowed_strategies: tuple[str, ...] = ACTION_KINDS
    specification: str = ''
    schema_version: str = SCHEMA_VERSION
    initial_targets: Mapping[str, str] = field(default_factory=dict)



@dataclass(frozen=True)
class CandidateBundle(Serializable):
    candidate_id: str
    parent_candidate_id: str | None
    episode_id: str
    files: Mapping[str, str]
    raw_hash: str
    normalized_hash: str
    tested_hash: str
    file_hashes: Mapping[str, str] = field(default_factory=dict)
    changed_files: tuple[str, ...] = ()
    diffs: Mapping[str, str] = field(default_factory=dict)
    normalization_actions: tuple[str, ...] = ()
    normalized_files: Mapping[str, str] = field(default_factory=dict)
    raw_files: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, files: Mapping[str, str], *, episode_id: str, parent=None,
               raw_files: Mapping[str, str] | None = None, normalization_actions=()):
        clean = {validate_target(name): content for name, content in files.items()}
        previous = parent.files if parent else {}
        changed = tuple(sorted(name for name in set(clean) | set(previous) if clean.get(name) != previous.get(name)))
        diffs = {name: ''.join(difflib.unified_diff(previous.get(name, '').splitlines(True),
                        clean.get(name, '').splitlines(True), fromfile=name, tofile=name)) for name in changed}
        digest = canonical_hash(clean)
        raw = dict(raw_files) if raw_files is not None else dict(clean)
        return cls(digest, parent.candidate_id if parent else None, episode_id, clean,
                   canonical_hash(raw), digest, digest,
                   {k: hashlib.sha256(v.encode()).hexdigest() for k, v in clean.items()},
                   changed, diffs, tuple(normalization_actions),dict(clean),raw)


@dataclass(frozen=True)
class Evidence(Serializable):
    evidence_id: str
    source: str
    kind: str
    text: str = ''
    public: bool = True
    candidate_id: str | None = None
    observation_id: str | None = None
    values: Mapping[str, Any] = field(default_factory=dict)
    truncated: bool = False
    availability: str = 'available'


@dataclass(frozen=True)
class Observation(Serializable):
    observation_id: str
    version: int
    task_id: str
    attempt: int
    episode_id: str
    iteration: int
    tested_hash: str
    evaluator_status: str = 'UNKNOWN'
    evaluation_validity: str = 'unknown'
    diagnostic_completeness: str = 'unknown'
    services: Mapping[str, Any] = field(default_factory=dict)
    executed_checks: tuple[str, ...] = ()
    passed_checks: tuple[str, ...] = ()
    failed_checks: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    metrics: Mapping[str, float | int | None] = field(default_factory=dict)
    metric_comparability_key: str | None = None
    evidence_ids: tuple[str, ...] = ()
    budget_snapshot: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION
    # Derived diagnostic interpretations do not overwrite raw service facts.
    inferences: Mapping[str, Any] = field(default_factory=dict)
    metric_availability: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProposedAction(Serializable):
    action_id: str
    observation_id: str
    action_kind: str
    target_ids: tuple[str, ...] = ()
    error_id: str | None = None
    hypothesis_id: str | None = None
    strategy_id: str | None = None
    eligibility: tuple[str, ...] = ()
    preconditions: Mapping[str, Any] = field(default_factory=dict)
    observation_version: int = 0
    tested_hash: str = ''


@dataclass(frozen=True)
class DecisionRecord(Serializable):
    decision_id: str
    observation_id: str
    answers: Mapping[str, Any] = field(default_factory=dict)
    requested_model: str = ''
    resolved_model: str | None = None
    schema_version: str = SCHEMA_VERSION
    policy_version: str = 'policy-1'
    chosen_action: ProposedAction | None = None
    abstention_reason: str | None = None
    fallback_reason: str | None = None
    latency_seconds: float | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectRecord(Serializable):
    effect_id: str
    before_observation_id: str | None
    after_observation_id: str
    action_id: str | None
    changed_files: tuple[str, ...] = ()
    focus_status: str = 'unknown'
    newly_reached_failures: tuple[str, ...] = ()
    confirmed_regressions: tuple[str, ...] = ()
    metric_delta: Mapping[str, float | int] = field(default_factory=dict)
    comparable: bool = False
    outcome: str = 'unknown'
