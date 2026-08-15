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

from app.services import agent_control, benchmark_llm

AGENT_ID = "llm_benchmark"


def _write_report(result: dict, path: pathlib.Path) -> None:
    """Persist a scored run so the dashboard has something to render.

    There is no endpoint for this half and there should not be one — a scored
    run spends production's own API quota, so a route would be a cost amplifier
    reachable by anyone with a session. A committed file inverts that: the
    dashboard reads a result someone deliberately produced and reviewed, the
    cost is paid once by a human at a terminal, and Render's ephemeral disk
    never enters into it.

    Committing it also makes the run auditable. `git log` on this file is the
    per-language history that a single mutable row in a table would erase, and
    a reviewer can see in a diff that recall moved before deciding whether the
    change that moved it was a good one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sorted keys and a trailing newline so a re-run produces a reviewable diff
    # rather than a reshuffled file.
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="actually spend API quota")
    parser.add_argument("--languages", nargs="*", help="limit to these language codes")
    parser.add_argument("--max-calls", type=int, help="refuse to run above this many calls")
    parser.add_argument("--json", action="store_true", help="raw JSON instead of a summary")
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        help="write the scored report here (the dashboard reads the committed copy)",
    )
    args = parser.parse_args()

    if args.run:
        # Same gate as the red-team loop: a scored run spends production's own
        # keys, so a disabled agent must not be startable from a terminal
        # either. A dry run costs nothing and is deliberately never blocked —
        # finding out what a run would cost is not spending.
        planned = benchmark_llm.estimate(
            benchmark_llm.load_corpus(), benchmark_llm.load_cache()
        )["classification_calls"]
        decision = agent_control.may_run(AGENT_ID, planned)
        if not decision.allowed:
            print(f"REFUSED: {decision.reason}")
            agent_control.record_run(AGENT_ID, "blocked", 0, {"reason": decision.reason})
            return 1

    result = benchmark_llm.run(
        confirm_cost=args.run,
        languages=args.languages,
        max_calls=args.max_calls,
    )

    if args.run:
        agent_control.record_run(
            AGENT_ID, "ok", result["run"]["api_calls"], {"models": result["run"]["models"]}
        )

    if args.out:
        if result["dry_run"]:
            print("Nothing written: --out needs --run, and a dry run has no scores.\n")
        else:
            _write_report(result, args.out)
            print(f"wrote {args.out}\n")

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
