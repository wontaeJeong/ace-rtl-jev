#!/usr/bin/env python3
"""Experimental stdlib offline tooling. Never contacts models or enables runtime.

Examples:
  python decision_offline.py train --data rows.jsonl --output stump.json \
      --question-version q1 --model-version m1 --policy-version p1
  python decision_offline.py evaluate --data rows.jsonl --artifact stump.json

Rows require family/task/action IDs, executed=true, linked before/action/effect/
next observation IDs, valid evaluation, next evaluator status, and numeric
decision-time allowlisted features. Missing metrics are null, not zero. Final
evaluation filters to the family split saved at training; unknown/unseen families
are not silently substituted. This small pipeline does not establish E2E gains.
"""
import argparse
import json
from pathlib import Path

from ace_rtl_agent.decision.offline import build_examples, grouped_split, train_policy, evaluate_policy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    train = commands.add_parser('train')
    train.add_argument('--data', required=True)
    train.add_argument('--output', required=True)
    for version in ('question', 'model', 'policy'):
        train.add_argument('--' + version + '-version', required=True)
    train.add_argument('--test-fraction', type=float, default=.25)
    train.add_argument('--seed', default='ace-offline-1')
    evaluate = commands.add_parser('evaluate')
    evaluate.add_argument('--data', required=True)
    evaluate.add_argument('--artifact', required=True)
    args = parser.parse_args(argv)
    try:
        with Path(args.data).open(encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        examples, rejected = build_examples(rows)
        if args.command == 'train':
            development, held_out = grouped_split(examples, args.test_fraction, seed=args.seed)
            artifact = train_policy(development, question_version=args.question_version,
                                    model_version=args.model_version, policy_version=args.policy_version)
            artifact['held_out_families'] = sorted({r.family for r in held_out})
            artifact['split_seed'] = args.seed
            artifact['data_requirements'] = 'Executed actions, valid linked next evaluations, decision-only features, design families'
            with Path(args.output).open('x', encoding='utf-8') as stream:
                json.dump(artifact, stream, sort_keys=True, indent=2, allow_nan=False)
            result = {'train_count': len(development), 'held_out_count': len(held_out),
                      'rejected_count': len(rejected), 'production_ready': False}
        else:
            artifact = json.loads(Path(args.artifact).read_text(encoding='utf-8'))
            held_out = tuple(r for r in examples if r.family in artifact['held_out_families'])
            if not held_out:
                raise ValueError('no rows from saved held-out families')
            result = evaluate_policy(artifact, held_out)
            result['rejected_count'] = len(rejected)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
