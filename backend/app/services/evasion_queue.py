"""The red-team queue, and the lifecycle it was missing.

`redteam.py` finds evasions and appends them. Nothing ever closed one — so when
#46 fixed the two rule bugs that produced the first three entries, those entries
stayed in the file looking exactly as urgent as the day they were written.

A queue that only grows gets ignored, and then a real evasion sits in it
unnoticed. Same failure as a test suite with no red.

## The lifecycle

    open      still evades the detector it was found against
    fixed     that detector now catches it
    wontfix   a human decided it is not worth chasing, with a reason

**`fixed` is decided by re-running, not by memory.** `verify()` replays every
open entry through the detector recorded on it and flips the ones that now pass.
That is the only honest way to close one: a human ticking a box records an
intention, while a replay records a fact.

`wontfix` is the opposite — it is the one transition a machine must never make,
because "not worth chasing" is a judgement about our users and our priorities.

## The shape, and why it is worth agreeing before building on it

@Hem60 renders this queue in #41 and the same decision store serves the pattern
queue in #60. The corpus schema in #33 is the precedent: settling the shape first
is what let three people work at once, and inventing two shapes a week apart is
what it avoided.

Every record carries:

    id            stable, derived from the fingerprint — safe to use as a key
    status        open | fixed | wontfix
    first_seen    ISO date, so age is visible without git archaeology
    resolution    null while open; {at, how, note, corpus_id} once closed

`resolution.how` is `verify` or `human`, which is what tells a reviewer whether
a closure was measured or asserted.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any

#: Beside `rule_corpus.jsonl`, because an accepted evasion is headed there.
QUEUE_PATH = pathlib.Path(__file__).resolve().parents[3] / "testdata" / "evasions.jsonl"

OPEN = "open"
FIXED = "fixed"
WONTFIX = "wontfix"
STATUSES = {OPEN, FIXED, WONTFIX}


def record_id(fingerprint: str) -> str:
    """Stable across runs and readable in a URL. The fingerprint already
    identifies the variant text, so this is a prefix rather than a new idea."""
    return f"ev-{fingerprint[:12]}"


def load(path: pathlib.Path = QUEUE_PATH) -> list[dict[str, Any]]:
    """Reads the queue, filling in fields older rows predate.

    Defaulting rather than failing: the first three entries were written before
    this module existed, and refusing to load them would mean the fix for a
    missing lifecycle is a queue nobody can open.
    """
    if not path.exists():
        return []

    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        record.setdefault("status", OPEN)
        record.setdefault("first_seen", None)
        record.setdefault("resolution", None)
        record.setdefault("id", record_id(record.get("fingerprint", "")))
        records.append(record)
    return records


def save(records: list[dict[str, Any]], path: pathlib.Path = QUEUE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def resolve(
    record: dict[str, Any],
    status: str,
    *,
    how: str,
    note: str = "",
    corpus_id: str | None = None,
    on: str | None = None,
) -> dict[str, Any]:
    """Close a record. Returns a new dict rather than mutating in place, so a
    caller comparing before and after has something to compare."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {sorted(STATUSES)}")
    return {
        **record,
        "status": status,
        "resolution": {
            # UTC rather than local: this queue is read by three people and a
            # CI job, and "closed on the 15th" should mean the same day to all
            # of them.
            "at": on or datetime.now(timezone.utc).date().isoformat(),
            "how": how,
            "note": note,
            "corpus_id": corpus_id,
        },
    }


def verify(
    records: list[dict[str, Any]],
    detect: Any,
    *,
    detector: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Replay every open record and close the ones now caught.

    `detect` is `(text, language) -> {"verdict": ...}` — injected rather than
    imported so this module stays testable without a model, and so the caller
    decides which detector is being asked. A record is only ever re-checked
    against the detector it was *found* against: an evasion of the offline rules
    is not resolved by the full pipeline catching it, because the rules are what
    runs on the phone.

    Returns (updated records, the ones that changed).
    """
    from app.services.redteam import SCAM_VERDICTS

    updated: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []

    for record in records:
        if record.get("status") != OPEN:
            updated.append(record)
            continue
        if detector and record.get("detector") != detector:
            updated.append(record)
            continue

        result = detect(record["text"], record["language"])
        if result["verdict"] not in SCAM_VERDICTS:
            updated.append(record)
            continue

        closed = resolve(
            record,
            FIXED,
            how="verify",
            note=(
                f"{record.get('detector', 'full')} detector now returns "
                f"{result['verdict']}"
            ),
        )
        updated.append(closed)
        changed.append(closed)

    return updated, changed


def unpinned(records: list[dict[str, Any]], corpus: list[dict[str, Any]]) -> list[dict]:
    """Fixed evasions with no corpus row holding the fix in place.

    Closing an evasion without adding a case means the bug can come back and
    nothing will notice — the queue would say `fixed` about a defect that has
    silently returned. This is the report that stops that, and it is why
    `resolution.corpus_id` exists.

    Matching is on text rather than id, since a corpus row written by hand from
    an evasion will not carry the evasion's id.
    """
    corpus_texts = {" ".join(case["text"].lower().split()) for case in corpus}
    return [
        record
        for record in records
        if record.get("status") == FIXED
        and not record.get("resolution", {}).get("corpus_id")
        and " ".join(record["text"].lower().split()) not in corpus_texts
    ]


def summary(records: list[dict[str, Any]]) -> dict[str, int]:
    """What a reviewer needs before opening the queue: how much is actually
    waiting for them, rather than how much has ever been found."""
    counts = {status: 0 for status in sorted(STATUSES)}
    for record in records:
        counts[record.get("status", OPEN)] = counts.get(record.get("status", OPEN), 0) + 1
    return counts
