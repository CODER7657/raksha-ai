"""Re-key community_reports rows after hash_text started folding digit scripts.

    python scripts/migrate_community_digits.py              # dry run: prints the plan, writes nothing
    python scripts/migrate_community_digits.py --apply      # backs up affected rows, then merges

`community_reports` holds digests, never text, so a digest cannot be recomputed from
the table itself. `scans.input_text` can: for every scan whose text contains a
non-ASCII digit, the digest before folding (`legacy_hash_text`) and after
(`hash_text`) differ. The old row is merged into the new one (counts summed, earliest
first sighting, latest last sighting) or, if no new row exists yet, simply re-keyed.

Old digests with no surviving scan row (deleted accounts cascade-delete their scans)
cannot be re-keyed and stay as they are: harmless, they just stop growing.

Run it BEFORE the code that folds digits is deployed (a backend merge is a deploy), so
no scan writes a new-style row the plan did not see. Running it twice is safe: a merged
old row no longer exists, so the second run finds nothing to do.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import asdict, dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.trace import hash_text, legacy_hash_text

PAGE = 1000


@dataclass(frozen=True)
class Action:
    kind: str  # "merge" (both rows exist) or "rekey" (only the old row exists)
    old: str
    new: str
    report_count: int
    first_reported_at: str | None
    last_reported_at: str | None
    language: str


def affected_pairs(texts) -> dict[str, str]:
    """old digest -> new digest, for texts whose digest changes when digits fold."""
    pairs: dict[str, str] = {}
    for text in texts:
        if not text or text.isascii():
            continue
        old, new = legacy_hash_text(text), hash_text(text)
        if old != new:
            pairs[old] = new
    return pairs


def _earliest(*values):
    present = [v for v in values if v]
    return min(present) if present else None


def _latest(*values):
    present = [v for v in values if v]
    return max(present) if present else None


def plan(pairs: dict[str, str], rows: dict[str, dict]) -> list[Action]:
    """What to do with each old row that exists. Several old digests can map to one new
    digest (the same SMS in ASCII and in Gujarati digits): they all merge into it."""
    merged: dict[str, dict] = {}
    actions: list[Action] = []
    for old, new in sorted(pairs.items()):
        old_row = rows.get(old)
        if old_row is None:
            continue
        target = merged.get(new) or rows.get(new)
        if target is None:
            kind, count = "rekey", old_row["report_count"]
            first, last = old_row.get("first_reported_at"), old_row.get("last_reported_at")
            language = old_row.get("language", "en")
        else:
            kind = "merge"
            count = target["report_count"] + old_row["report_count"]
            first = _earliest(target.get("first_reported_at"), old_row.get("first_reported_at"))
            last = _latest(target.get("last_reported_at"), old_row.get("last_reported_at"))
            language = target.get("language", old_row.get("language", "en"))
        merged[new] = {
            "report_count": count,
            "first_reported_at": first,
            "last_reported_at": last,
            "language": language,
        }
        actions.append(Action(kind, old, new, count, first, last, language))
    return actions


def _fetch_scan_texts(client):
    start = 0
    while True:
        rows = (
            client.table("scans").select("input_text").range(start, start + PAGE - 1).execute().data
            or []
        )
        yield from (r["input_text"] for r in rows)
        if len(rows) < PAGE:
            return
        start += PAGE


def _fetch_reports(client, digests) -> dict[str, dict]:
    found: dict[str, dict] = {}
    digests = sorted(set(digests))
    for i in range(0, len(digests), 100):
        chunk = digests[i : i + 100]
        rows = client.table("community_reports").select("*").in_("pattern_hash", chunk).execute().data
        found.update({r["pattern_hash"]: r for r in rows or []})
    return found


def apply(client, actions: list[Action]) -> None:
    """Upsert the final state of each new digest, then delete the old rows."""
    final: dict[str, Action] = {a.new: a for a in actions}  # last action per new digest is final
    for a in final.values():
        client.table("community_reports").upsert(
            {
                "pattern_hash": a.new,
                "language": a.language,
                "report_count": a.report_count,
                "first_reported_at": a.first_reported_at,
                "last_reported_at": a.last_reported_at,
            },
            on_conflict="pattern_hash",
        ).execute()
    for a in actions:
        client.table("community_reports").delete().eq("pattern_hash", a.old).execute()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument("--backup", type=pathlib.Path, default=pathlib.Path("community_digits_backup.json"))
    args = ap.parse_args(argv)

    from app.core.supabase_client import get_supabase

    client = get_supabase()
    texts = list(_fetch_scan_texts(client))
    pairs = affected_pairs(texts)
    rows = _fetch_reports(client, list(pairs) + list(pairs.values()))
    actions = plan(pairs, rows)
    print(
        f"scans read: {len(texts)}; texts whose digest changes: {len(pairs)}; "
        f"old rows found: {len(actions)} "
        f"(merge {sum(a.kind == 'merge' for a in actions)}, rekey {sum(a.kind == 'rekey' for a in actions)})"
    )
    if not args.apply:
        print("dry run: nothing written. Re-run with --apply to merge.")
        return 0
    if not actions:
        print("nothing to apply.")
        return 0
    args.backup.write_text(
        json.dumps({"rows": rows, "actions": [asdict(a) for a in actions]}, indent=1, default=str),
        encoding="utf-8",
    )
    print(f"backup written: {args.backup}")
    apply(client, actions)
    print("applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
