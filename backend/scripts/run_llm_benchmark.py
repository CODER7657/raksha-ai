"""Run the RAG + LLM benchmark from the command line.

A CLI rather than an endpoint because a scored run spends API quota on the same
free-tier keys production uses — an HTTP route would let anyone with a session
exhaust the product's own budget.

    python scripts/run_llm_benchmark.py                     # dry run, costs nothing
    python scripts/run_llm_benchmark.py --run               # spend, all languages
    python scripts/run_llm_benchmark.py --run --languages en hi
    python scripts/run_llm_benchmark.py --run --max-calls 20

Dry run is the default on purpose. It reports how many classification calls a
real run would make after the cache, so the cost is known before it is incurred.
"""

import argparse
import json
import pathlib
import sys

# Run from anywhere: `python scripts/run_llm_benchmark.py` puts scripts/ on the
# path, not backend/, so `app.` would not resolve. pytest.ini fixes this for
# tests via `pythonpath`; a plain script has no such help.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services import benchmark_llm


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="actually spend API quota")
    parser.add_argument("--languages", nargs="*", help="limit to these language codes")
    parser.add_argument("--max-calls", type=int, help="refuse to run above this many calls")
    parser.add_argument("--json", action="store_true", help="raw JSON instead of a summary")
    args = parser.parse_args()

    result = benchmark_llm.run(
        confirm_cost=args.run,
        languages=args.languages,
        max_calls=args.max_calls,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if result["dry_run"]:
        estimate = result["estimate"]
        print("DRY RUN — nothing was spent\n")
        print(f"  cases                 {estimate['cases']}")
        print(f"  already cached        {estimate['cached']}")
        print(f"  classification calls  {estimate['classification_calls']}")
        print(f"  embedding calls       {estimate['embedding_calls']}")
        print("\nRe-run with --run to score.")
        return 0

    print(f"models: {', '.join(result['run']['models']) or 'none'}   "
          f"prompt: {result['run']['prompt_version']}   "
          f"api calls: {result['run']['api_calls']}   "
          f"cache hits: {result['run']['cache_hits']}\n")

    header = f"{'lang':<6}{'cases':>7}{'scored':>8}{'leaked':>8}{'precision':>11}{'recall':>9}"
    print(header)
    print("-" * len(header))
    for lang in result["languages"]:
        if lang["total_cases"] == 0:
            continue
        precision = "—" if lang["precision"] is None else f"{lang['precision']:.3f}"
        recall = "—" if lang["recall"] is None else f"{lang['recall']:.3f}"
        print(
            f"{lang['language']:<6}{lang['total_cases']:>7}{lang['scored_cases']:>8}"
            f"{lang['leaked_cases']:>8}{precision:>11}{recall:>9}"
        )

    leakage = result["leakage"]
    print()
    if leakage["held_out"]:
        print(f"held out: yes — no case within {leakage['threshold']} similarity of a stored pattern")
    else:
        print(
            f"WARNING: {leakage['leaked_cases']} case(s) are effectively present in "
            f"scam_patterns and were excluded. The corpus is not held out; figures "
            f"above cover only the remainder."
        )

    missed = [(lang["language"], case) for lang in result["languages"] for case in lang["missed_cases"]]
    if missed:
        print(f"\nmissed scams ({len(missed)}) — these cost recall:")
        for language, case in missed[:15]:
            print(f"  [{language}] {case['id']:<34} -> {case['verdict']} ({case['risk_score']})")

    # Printed alongside the misses, not buried: over-warning is the accepted
    # failure direction, but a reviewer still has to see what is being warned
    # about to judge whether the cost is acceptable.
    warned = [
        (lang["language"], case)
        for lang in result["languages"]
        for case in lang["false_positive_cases"]
    ]
    if warned:
        print(f"\nbenign messages warned about ({len(warned)}) — these cost precision:")
        for language, case in warned[:15]:
            print(f"  [{language}] {case['id']:<34} -> {case['verdict']} ({case['risk_score']})")
            print(f"           {case['text'][:74]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
