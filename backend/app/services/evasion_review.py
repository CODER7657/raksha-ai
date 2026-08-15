"""The A6 evasion review queue (#41 §3).

The red-team loop produces variants that got past the detector. Each needs a
human decision: is this a real evasion worth pinning in the corpus, or noise?

**The reviewer's question is "is this still the same fraud?"** — and they cannot
answer it from the variant alone, so every entry is paired with the seed case it
was mutated from. An evasion without its original is an unanswerable question.

**This module handles attacker-authored text.** `text` is written by an
adversarial loop specifically to get past our detection, and a variant
containing "ignore previous instructions" is a realistic thing to find in it.
So it is treated the way `AGENT-LAYER.md` §02 treats fetched page content:
carried as data, never interpreted, and never used to build a prompt. Nothing
here calls a model. The word-level diff below is computed on tokens and
returned as structured data rather than markup, so the rendering layer has
nothing to interpret either.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import asdict, dataclass

from app.services.benchmark import load_corpus

EVASIONS_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "testdata" / "evasions.jsonl"
)

#: Only `open` entries need a decision. `fixed` closed itself when the detector
#: caught up (#53), and `wontfix` was already judged.
REVIEWABLE_STATUS = "open"

#: Split on whitespace but keep punctuation attached, so "suspension." and
#: "suspension" read as the same word moving rather than two edits. The diff is
#: a reading aid, not a merge tool.
_TOKEN = re.compile(r"\S+")


@dataclass(frozen=True)
class DiffToken:
    """One token, and whether it survived the mutation.

    Returned as data, never as HTML. The text is attacker-authored, and the one
    thing that must never happen is a variant being interpreted rather than
    displayed.
    """

    text: str
    #: "same" | "added" — added means present in the variant but not the seed.
    kind: str


def load_evasions(path: pathlib.Path | None = None) -> list[dict]:
    source = path or EVASIONS_PATH
    if not source.exists():
        return []
    return [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def open_evasions(evasions: list[dict]) -> list[dict]:
    return [e for e in evasions if e.get("status") == REVIEWABLE_STATUS]


def diff_tokens(seed_text: str, variant_text: str) -> list[dict]:
    """Which words in the variant are not in the seed.

    Deliberately a set-membership check rather than a real edit-distance diff.
    The reviewer is asking "what did the mutation change?", and for the
    strategies the loop actually uses — paraphrase, transliteration,
    code-mixing, padding — highlighting the words that are new answers that
    question. A character-level diff on a paraphrase highlights nearly
    everything and answers nothing.
    """
    seed_words = {w.lower().strip(".,!?;:\"'") for w in _TOKEN.findall(seed_text)}
    return [
        asdict(
            DiffToken(
                text=token,
                kind="same" if token.lower().strip(".,!?;:\"'") in seed_words else "added",
            )
        )
        for token in _TOKEN.findall(variant_text)
    ]


def review_card(evasion: dict, corpus_by_id: dict[str, dict]) -> dict:
    """One evasion paired with the seed it was mutated from.

    A seed that has since been deleted from the corpus yields `seed: None`
    rather than an error — the variant is still reviewable, just harder, and
    the UI says the original is missing instead of rendering a blank panel.
    """
    seed = corpus_by_id.get(evasion.get("seed_id", ""))

    return {
        **evasion,
        "seed": (
            {
                "id": seed["id"],
                "text": seed["text"],
                "language": seed["language"],
                "expected_rule_ids": seed.get("expected_rule_ids", []),
            }
            if seed
            else None
        ),
        "diff": diff_tokens(seed["text"], evasion["text"]) if seed else None,
    }


def build_queue(
    path: pathlib.Path | None = None, corpus_path: pathlib.Path | None = None
) -> dict:
    evasions = load_evasions(path)
    corpus_by_id = {case["id"]: case for case in load_corpus(corpus_path)}
    queue = open_evasions(evasions)

    return {
        "evasions": [review_card(e, corpus_by_id) for e in queue],
        "counts": {
            "open": len(queue),
            "fixed": sum(1 for e in evasions if e.get("status") == "fixed"),
            "wontfix": sum(1 for e in evasions if e.get("status") == "wontfix"),
            "total": len(evasions),
        },
        # Which mutation strategies are producing work. A strategy generating
        # nothing but noise is itself a finding (#41 §3), and it is only
        # visible in aggregate.
        "by_strategy": _count_by(queue, "strategy"),
        "decisions_persisted": False,
    }


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get(key, "unknown")] = counts.get(row.get(key, "unknown"), 0) + 1
    return dict(sorted(counts.items()))
