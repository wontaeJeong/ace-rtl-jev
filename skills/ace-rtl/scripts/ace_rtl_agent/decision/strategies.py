"""Closed, narrow guidance recipes and read-only diagnostic declarations.

No recipe patches RTL. A generator produces a full candidate; the real evaluator
verifies it. Diagnostics consume existing emitted public artifacts only.
"""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class RepairRecipe:
    strategy_id: str
    task_kinds: tuple[str, ...]
    evidence_pattern: str
    preconditions: tuple[str, ...]
    guidance: str
    validation: tuple[str, ...] = ('compile', 'required evaluator services')

    def to_dict(self):
        return asdict(self)


RECIPES = (
    RepairRecipe('syntax_local', ('rtl_implementation', 'rtl_optimization', 'assertion', 'coverage', 'checker'),
                 'syntax error', ('candidate compile failed', 'diagnostic names a mutable target'),
                 'Correct only the reported syntax at the declared target. Preserve the public interface and behavior; generate every target file.'),
    RepairRecipe('explicit_width', ('rtl_implementation', 'rtl_optimization'),
                 'width mismatch', ('explicit emitted width diagnostic', 'diagnostic names a mutable target'),
                 'Resolve the explicit width diagnostic using public declared widths and explicit casts/slices/extensions. Preserve signedness and public timing; generate every target file.'),
)

STRATEGIES = {recipe.strategy_id: recipe for recipe in RECIPES}


def hypothesis_candidates(evidence):
    """Closed hypotheses from observed symptoms; never verified root causes."""
    patterns={'reset_preservation':('reset','Reset behavior may not match the public contract.'),
              'width_signedness':('width','Width/signedness interpretation may explain the explicit diagnostic.'),
              'protocol_handshake':('handshake','Public ready/valid handshake sequencing may explain the symptom.'),
              'pipeline_alignment':('latency','Pipeline alignment may explain the reported public latency symptom.')}
    result={}
    for identity,(pattern,description) in patterns.items():
        matched=[e.evidence_id for e in evidence if e.kind in {'diagnostic','emitted_log','current_failure'}
                  and pattern in e.text.lower()]
        if matched:result[identity]={'description':description,'evidence_ids':matched,'verified':False}
    return result


def get_strategy_guidance(strategy_id):
    """Native generator guidance lookup, no model call and no RTL generation."""
    try:
        return STRATEGIES[strategy_id].guidance
    except KeyError:
        raise ValueError('unknown repair strategy') from None


def eligible_recipes(observation, contract, evidence):
    result = []
    for recipe in RECIPES:
        if contract.task_kind not in recipe.task_kinds:
            continue
        if recipe.strategy_id == 'syntax_local' and observation.evaluator_status != 'CANDIDATE_COMPILE':
            continue
        if any(recipe.evidence_pattern in e.text.lower() and
               any(target in e.text or target == e.values.get('target_id') for target in contract.mutable_targets)
               for e in evidence if e.kind in {'diagnostic', 'emitted_log', 'current_failure'}):
            result.append(recipe)
    return tuple(result)


def diagnostic_candidates(contract, evidence):
    """No paths inferred or tools spawned: only an allowlisted already-emitted artifact."""
    if 'inspect_public_artifact' not in contract.allowed_tools:
        return ()
    return tuple({'strategy_id': 'inspect_public_artifact', 'evidence_id': e.evidence_id,
                  'allowed_inputs': (e.evidence_id,), 'timeout_seconds': 2.0,
                  'max_chars': 8000, 'view': 'unexposed_tail', 'artifact': 'bounded_public_summary',
                  'cost': 'local read-only; no evaluator or model call'}
                 for e in evidence if e.kind in {'emitted_log', 'trace'} and e.values.get('unexposed_tail_available') is True)


def summarize_diagnostic(action, evidence):
    """Return a bounded view of supplied emitted content, never read private files."""
    wanted = action.preconditions.get('evidence_id')
    for item in evidence:
        if item.evidence_id == wanted and item.public and item.kind in {'emitted_log', 'trace'}:
            from dataclasses import replace
            from .state_builder import public_evidence
            if not public_evidence((item,)):
                break
            # Long VCD is deliberately unsupported: numeric waveform parsing is
            # the harness's responsibility; this action only selects existing text.
            if '$enddefinitions' in item.text:
                raise ValueError('raw waveform requires deterministic harness parser')
            if len(item.text) <= 8000 or item.truncated:
                raise ValueError('diagnostic has no unexposed permitted artifact content')
            return replace(item, evidence_id=item.evidence_id + ':tail', kind='diagnostic',
                           text=item.text[-8000:], truncated=True)
    raise ValueError('diagnostic has no permitted emitted artifact')
