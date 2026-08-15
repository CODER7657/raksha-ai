"""Run the A6 red-team loop against seeds from the shared corpus.

    python scripts/run_redteam.py                          # estimate only
    python scripts/run_redteam.py --run --seeds en-kyc-otp-lock-001
    python scripts/run_redteam.py --run --strategies obfuscation paraphrase --budget 40

Seeds come from `testdata/rule_corpus.jsonl` and are restricted to cases the
system currently gets right — rewriting something already missed teaches nothing.

Evasions are appended to `testdata/evasions.jsonl` for review. Nothing here
writes to the pattern database: a generated scam approved as a pattern is the
poisoning path AGENT-LAYER.md §03 exists to prevent.
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services import redteam
from app.services.benchmark import load_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="actually spend model calls")
    parser.add_argument("--seeds", nargs="*", help="corpus case ids to attack")
    parser.add_argument("--strategies", nargs="*", choices=list(redteam.STRATEGIES))
    parser.add_argument("--variants", type=int, default=3, help="variants per strategy")
    parser.add_argument("--budget", type=int, default=200, help="max model calls")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument(
        "--detector",
        choices=sorted(redteam.DETECTORS),
        default="rules",
        help="which layer to attack: rules (on-device, free) or full (what a "
             "website user gets). Defaults to rules — it is cheaper and it is "
             "the layer the full pipeline hides.",
    )
    args = parser.parse_args()

    corpus = load_corpus()
    seeds = [
        case
        for case in corpus
        if case["label"] == "scam"
        and case.get("status") == "enforced"  # only attack what we currently catch
        and (not args.seeds or case["id"] in args.seeds)
    ]
    if not seeds:
        print("no matching seeds", file=sys.stderr)
        return 1

    strategies = args.strategies or list(redteam.STRATEGIES)
    estimate = redteam.estimate(seeds, strategies, args.variants)

    print(f"seeds: {len(seeds)}   strategies: {len(strategies)}   detector: {args.detector}")
    print(f"per round, at most: {estimate['max_model_calls_per_round']} model calls")

    if not args.run:
        print("\nestimate only — re-run with --run to spend.")
        return 0

    stats = redteam.run(
        seeds,
        confirm_cost=True,
        strategies=strategies,
        variants_per_strategy=args.variants,
        max_model_calls=args.budget,
        max_rounds=args.rounds,
        detector=args.detector,
    )

    print(
        f"\nrounds {stats.rounds}   model calls {stats.model_calls}\n"
        f"generated {stats.generated}   "
        f"still-a-scam {stats.preserved}   "
        f"dropped by judge {stats.discarded_by_judge}   "
        f"unparseable {stats.schema_failures}   "
        f"duplicates {stats.duplicates}\n"
        f"detected {stats.detected}   EVADED {stats.evaded}"
    )

    if stats.evasions:
        print("\nevasions:")
        for evasion in stats.evasions:
            print(f"  [{evasion.strategy}] verdict={evasion.verdict} ({evasion.risk_score})")
            print(f"      {evasion.text[:100]}")
            print(f"      judge: {evasion.judge_reason}")

    written = redteam.write_evasions(stats)
    print(f"\n{written} new evasion(s) written to {redteam.EVASIONS_PATH.name} for review")
    if written:
        print("Nothing was added to scam_patterns. A human decides what becomes a corpus row.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
