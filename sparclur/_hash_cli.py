"""Command-line workflow for SPARCLUR hash evidence baselines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sparclur._parser import HashComparisonPolicy, SparclurHash
from sparclur.parsers.present_parsers import get_parser, get_sparclur_parsers


def _parser_names() -> list[str]:
    return sorted(parser.get_name() for parser in get_sparclur_parsers())


def _parse_component_values(values: list[str] | None, option: str) -> dict[str, float]:
    parsed = dict()
    for value in values or []:
        component, separator, number = value.partition('=')
        if not separator or not component or not number:
            raise ValueError(f"{option} values must use COMPONENT=NUMBER")
        try:
            parsed[component] = float(number)
        except ValueError as error:
            raise ValueError(f"{option} values must use COMPONENT=NUMBER") from error
    return parsed


def _hash_document(document: str, parser_name: str) -> SparclurHash:
    if not Path(document).is_file():
        raise ValueError(f'Document not found: {document}')
    parser_class = get_parser(parser_name)
    if parser_class is None:
        raise ValueError(f'Unknown parser: {parser_name}')
    parser = parser_class(doc=document)
    return parser.sparclur_hash


def _load_evidence(path: str) -> SparclurHash:
    with open(path, encoding='utf-8') as input_file:
        return SparclurHash.from_dict(json.load(input_file))


def _write_json(path: str, value: dict[str, Any]) -> None:
    with open(path, 'w', encoding='utf-8') as output_file:
        json.dump(value, output_file, indent=2, sort_keys=True)
        output_file.write('\n')


def _print_comparison(comparison: dict[str, Any]) -> None:
    similarity = comparison['sim']
    similarity_text = 'unavailable' if similarity is None else f'{similarity:.6f}'
    print(f"Comparable: {'yes' if comparison['comparable'] else 'no'}")
    print(f'Similarity: {similarity_text}')
    print(f"Provenance match: {'yes' if comparison['provenance_match'] else 'no'}")
    for warning in comparison['warnings']:
        print(f'Warning: {warning}')
    print('Components:')
    for component, result in sorted(comparison['components'].items()):
        score = result.get('sim')
        score_text = 'unavailable' if score is None else f'{score:.6f}'
        print(
            f"  {component}: {score_text} "
            f"(left={result['left']['status']}, right={result['right']['status']})"
        )


def _create(args: argparse.Namespace) -> int:
    evidence = _hash_document(str(args.document), args.parser).to_dict()
    _write_json(args.output, evidence)
    print(f"Wrote {args.output} for {args.parser}.")
    return 0


def _compare(args: argparse.Namespace) -> int:
    weights = _parse_component_values(args.weight, '--weight')
    minimums = _parse_component_values(args.component_minimum, '--component-minimum')
    policy = HashComparisonPolicy(weights=weights, page_aggregation=args.page_aggregation)
    current = _hash_document(str(args.document), args.parser)
    baseline = _load_evidence(args.baseline)
    comparison = current.compare(baseline, policy=policy, compatibility=args.compatibility)
    _print_comparison(comparison)
    if args.output is not None:
        _write_json(args.output, comparison.to_dict())
    failures = comparison.failures(
        minimum_similarity=args.minimum_similarity,
        component_minimums=minimums,
    )
    if failures:
        for component, reason in failures.items():
            print(f'Failed {component}: {reason}', file=sys.stderr)
        return 1
    return 0


def _inspect(args: argparse.Namespace) -> int:
    evidence = _load_evidence(args.baseline)
    if args.json:
        print(json.dumps(evidence.to_dict(), indent=2, sort_keys=True))
    else:
        metadata = evidence.metadata
        parser = metadata.get('provenance', {}).get('parser', {})
        print(f"Source SHA-256: {metadata['source_sha256']}")
        print(f"Parser: {parser.get('name', 'not recorded')}")
        print(f"Schema version: {metadata['schema_version']}")
        print('Components:')
        for component, outcome in sorted(evidence.component_outcomes.items()):
            print(f"  {component}: {outcome['status']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Create and compare SPARCLUR hash baselines.')
    subparsers = parser.add_subparsers(dest='command', required=True)
    parser_names = _parser_names()

    create = subparsers.add_parser('create', help='Create a parser-output baseline JSON file.')
    create.add_argument('document', type=Path)
    create.add_argument('--parser', choices=parser_names, required=True)
    create.add_argument('--output', required=True)
    create.set_defaults(func=_create)

    compare = subparsers.add_parser('compare', help='Compare a document with a baseline JSON file.')
    compare.add_argument('document', type=Path)
    compare.add_argument('baseline')
    compare.add_argument('--parser', choices=parser_names, required=True)
    compare.add_argument('--minimum-similarity', type=float, default=1.0)
    compare.add_argument('--component-minimum', action='append')
    compare.add_argument('--weight', action='append')
    compare.add_argument('--page-aggregation', choices=['min', 'mean'], default='min')
    compare.add_argument('--compatibility', choices=['warn', 'strict', 'ignore'], default='warn')
    compare.add_argument('--output', help='Write the complete comparison evidence as JSON.')
    compare.set_defaults(func=_compare)

    inspect = subparsers.add_parser('inspect', help='Inspect a baseline JSON file.')
    inspect.add_argument('baseline')
    inspect.add_argument('--json', action='store_true', help='Print the complete evidence bundle as JSON.')
    inspect.set_defaults(func=_inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ``sparclur-hash`` command and return a process status code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (AssertionError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
