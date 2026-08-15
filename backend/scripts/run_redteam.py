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

from app.services import agent_control, evasion_queue, redteam
from app.services.benchmark import load_corpus


def verify_queue(detector: str) -> int:
    """Close what is already fixed, and report what a fix is not pinned by.

    Run this before opening the queue. Three of its first entries were closed by
    #46 and sat there for days looking as urgent as the day they were found — a
    queue that only grows is a queue nobody reads.
    """
    records = evasion_queue.load()
    if not records:
        print("Queue is empty.")
        return 0

    before = evasion_queue.summary(records)
    detect = redteam.DETECTORS[detector]
    updated, changed = evasion_queue.verify(records, detect, detector=detector)

    if changed:
        evasion_queue.save(updated)
        print(f"Closed {len(changed)} evasion(s) the {detector} detector now catches:\n")
        for record in changed:
            print(f"  {record['id']}  [{record['strategy']}]  {record['text'][:66]}")
        print()
    else:
        print(f"Nothing newly caught by the {detector} detector.\n")

    after = evasion_queue.summary(updated)
    print(
        f"open {after['open']}   fixed {after['fixed']}   "
        f"wontfix {after['wontfix']}   (was open {before['open']})"
    )

    loose = evasion_queue.unpinned(updated, load_corpus())
    if loose:
        print(
            f"\n{len(loose)} fixed evasion(s) have no corpus row holding the fix "
            f"in place. The bug can return and nothing will notice:"
        )
        for record in loose:
            print(f"  {record['id']}  {record['text'][:66]}")
        print(
            "\nAdd each as a corpus row, or set resolution.corpus_id if one exists."
        )
    return 0


AGENT_ID = "a6_redteam"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="actually spend model calls")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="re-check open evasions against the detector each was found "
             "against, close the ones now caught, and exit. Free for the rules "
             "detector; costs a classification per entry for the full one.",
    )
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

    if args.verify:
        return verify_queue(args.detector)

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

    # The kill switch, checked before anything is spent (#32 D). An operator who
    # stopped this agent in the console expects it stopped everywhere, including
    # for someone running it by hand from a terminal. An estimate is never
    # blocked: finding out what a run would cost is not spending.
    decision = agent_control.may_run(AGENT_ID, estimate["max_model_calls_per_round"])
    if not decision.allowed:
        print(f"\nREFUSED: {decision.reason}")
        agent_control.record_run(AGENT_ID, "blocked", 0, {"reason": decision.reason})
        return 1

    stats = redteam.run(
        seeds,
        confirm_cost=True,
        strategies=strategies,
        variants_per_strategy=args.variants,
        max_model_calls=args.budget,
        max_rounds=args.rounds,
        detector=args.detector,
    )

    # Recorded after the fact with what it actually cost, not what it planned.
    # The estimate is an upper bound; the console should show spend, not intent.
    agent_control.record_run(
        AGENT_ID,
        "ok",
        stats.model_calls,
        {"detector": stats.detector, "rounds": stats.rounds, "evaded": stats.evaded},
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
