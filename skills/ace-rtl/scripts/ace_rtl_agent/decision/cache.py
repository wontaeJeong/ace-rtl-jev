"""Evaluation reuse requires declared determinism and intact artifact provenance."""
from __future__ import annotations

import json
from pathlib import Path
import re

from .ledger import durable_json
from .types import canonical_hash


class EvaluationCache:
    REQUIRED_CONTEXT = ('seed', 'tool_hash', 'harness_hash', 'task_hash', 'config_hash', 'policy_version')

    def __init__(self, root):
        self.root = Path(root)

    def _key(self, candidate_hash, context):
        if context.get('deterministic') is not True or context.get('external_state_dependent'):
            return None
        if any(context.get(k) is None or context.get(k) == '' for k in self.REQUIRED_CONTEXT):
            return None
        return canonical_hash({'candidate_hash': candidate_hash, 'context': context})

    def _artifacts(self, candidate_hash, result):
        from ace_cvdp_native.processes import validate_evaluation_artifacts
        return validate_evaluation_artifacts(candidate_path=Path(result['candidate_path']),
            manifest_path=Path(result['manifest_path']), evaluation_path=Path(result['evaluation_path']),
            required_services=result.get('required_services', ()), require_pass=False,
            expected_hash=candidate_hash)

    def put(self, candidate_hash, context, result):
        key = self._key(candidate_hash, context)
        if key is None:
            return False
        try:
            hashes = self._artifacts(candidate_hash, result)
        except (OSError, ValueError, KeyError, TypeError):
            return False
        durable_json(self.root / (key + '.json'), {'result': result, 'artifacts': hashes})
        return True

    def get(self, candidate_hash, context):
        key = self._key(candidate_hash, context)
        if key is None:
            return None
        try:
            stored = json.loads((self.root / (key + '.json')).read_text())
            if self._artifacts(candidate_hash, stored['result']) != stored['artifacts']:
                return None
            return stored['result']
        except (OSError, ValueError, KeyError, TypeError):
            return None


class DecisionCache:
    """Cache raw JEV answers only; every hit must pass the current action policy."""
    def __init__(self, root):
        self.root = Path(root)

    def _key(self, state, questions, *, provider, requested_model, resolved_model, schema_version):
        # Current provider contract proves only concrete JEV versions, not mutable aliases.
        if not isinstance(resolved_model, str) or not re.fullmatch(r'jev-\d+\.\d+\.\d+', resolved_model):
            return None
        if not provider or not requested_model or not schema_version:
            return None
        return canonical_hash({'state': state, 'questions': questions, 'provider': provider,
            'requested_model': requested_model, 'resolved_model': resolved_model, 'schema_version': schema_version})

    def put(self, state, questions, result, **context):
        key = self._key(state, questions, **context)
        if key is None or not isinstance(result, dict) or not isinstance(result.get('answers'), dict):
            return False
        raw = {'answers': result['answers']}
        durable_json(self.root / (key + '.json'), {'raw': raw, 'hash': canonical_hash(raw)})
        return True

    def get(self, state, questions, **context):
        key = self._key(state, questions, **context)
        if key is None:
            return None
        try:
            stored = json.loads((self.root / (key + '.json')).read_text())
            raw = stored['raw']
            if set(raw) != {'answers'} or not isinstance(raw['answers'], dict) or canonical_hash(raw) != stored['hash']:
                return None
            return raw
        except (OSError, ValueError, TypeError, KeyError):
            return None
