"""Re-key community_reports rows after hash_text started folding digit scripts.

    python scripts/migrate_community_digits.py              # dry run: prints the plan, writes nothing
    python scripts/migrate_community_digits.py --apply      # backs up affected rows, then merges

`community_reports` holds digests, never text, so a digest cannot be recomputed from
the table itself. `scans.input_text` can: for every scan whose text contains a
non-ASCII digit, the digest before folding (`legacy_hash_text`) and after
(`hash_text`) differ. The old row is merged into the new one (counts summed, latest
last sighting) or, if no new row exists yet, simply re-keyed.

First sightings follow migration 0014: NULL means "older than 0014, unknown". If
either side is NULL the merged row keeps NULL, because pairing an all-time count with
a recent first sighting would invent a velocity the campaign view would trust.

Order: deploy the folding code first, then run --apply, then run it again. After the
deploy no scan writes an old-style digest any more, so a second run picks up anything
written in between and then finds nothing. Applied to production on 2026-11-08
(69 scans, 1 row re-keyed); that run happened just before the deploy, so it is re-run
after it.

Limits, stated plainly. Each action re-reads both rows right before writing, so the
window for racing a live increment is one row, not the whole run. The writes are not
one transaction: if --apply is interrupted between the upsert and the delete of one
pair, a rerun counts that pair twice. Every run writes a timestamped backup that is
never overwritten, so the original counts are always recoverable. Old digests with no
surviving scan (deleted accounts cascade-delete their scans) cannot be re-keyed; they
stay as they are and stop growing.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile
import time
from dataclasses import asdict, dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.trace import hash_text, legacy_hash_text

PAGE = 1000
CHUNK = 100


@dataclass(frozen=True)
class Action:
    kind: str  # "merge" (both rows exist) or "rekey" (only the old row exists)
    old: str
    new: str
    report_count: int
    first_reported_at: str | None
    last_reported_at: str | None
    language: str


def affected_pairs(texts) -> tuple[dict[str, str], int]:
    """(old digest -> new digest for texts whose digest changes, number of texts read)."""
    pairs: dict[str, str] = {}
    read = 0
    for text in texts:
        read += 1
        if not text or text.isascii():
            continue
        old, new = legacy_hash_text(text), hash_text(text)
        if old != new:
            pairs[old] = new
    return pairs, read


def _merged_first(a: str | None, b: str | None) -> str | None:
    # NULL is "unknown, older than 0014", not "absent": it must win.
    if a is None or b is None:
        return None
    return min(a, b)


def _latest(*values: str | None) -> str | None:
    present = [v for v in values if v]
    return max(present) if present else None


def merge_rows(old_row: dict, target: dict | None) -> tuple[str, dict]:
    if target is None:
        return "rekey", {
            "report_count": old_row["report_count"],
            "first_reported_at": old_row.get("first_reported_at"),
            "last_reported_at": old_row.get("last_reported_at"),
            "language": old_row.get("language", "en"),
        }
    return "merge", {
        "report_count": target["report_count"] + old_row["report_count"],
        "first_reported_at": _merged_first(
            target.get("first_reported_at"), old_row.get("first_reported_at")
        ),
        "last_reported_at": _latest(target.get("last_reported_at"), old_row.get("last_reported_at")),
        "language": target.get("language", old_row.get("language", "en")),
    }


def plan(pairs: dict[str, str], rows: dict[str, dict]) -> list[Action]:
    """What to do with each old row that exists. Several old digests can map to one new
    digest (the same SMS in ASCII and in Gujarati digits): they all merge into it."""
    merged: dict[str, dict] = {}
    actions: list[Action] = []
    for old, new in sorted(pairs.items()):
        old_row = rows.get(old)
        if old_row is None:
            continue
        kind, state = merge_rows(old_row, merged.get(new) or rows.get(new))
        merged[new] = state
        actions.append(Action(kind, old, new, **state))
    return actions


def fetch_scan_texts(client, page: int = PAGE):
    """Every scans.input_text, in id order so pages neither skip nor repeat rows."""
    start = 0
    while True:
        rows = (
            client.table("scans")
            .select("id,input_text")
            .order("id")
            .range(start, start + page - 1)
            .execute()
            .data
            or []
        )
        yield from (r["input_text"] for r in rows)
        if len(rows) < page:
            return
        start += page


def fetch_reports(client, digests, chunk: int = CHUNK) -> dict[str, dict]:
    found: dict[str, dict] = {}
    digests = sorted(set(digests))
    for i in range(0, len(digests), chunk):
        part = digests[i : i + chunk]
        rows = client.table("community_reports").select("*").in_("pattern_hash", part).execute().data
        found.update({r["pattern_hash"]: r for r in rows or []})
    return found


def apply(client, pairs: dict[str, str]) -> list[Action]:
    """Pair by pair: re-read both rows, write the merged new row, delete the old one."""
    done: list[Action] = []
    for old, new in sorted(pairs.items()):
        rows = fetch_reports(client, [old, new])
        if old not in rows:
            continue  # already migrated, or never counted
        kind, state = merge_rows(rows[old], rows.get(new))
        client.table("community_reports").upsert(
            {"pattern_hash": new, **state}, on_conflict="pattern_hash"
        ).execute()
        client.table("community_reports").delete().eq("pattern_hash", old).execute()
        done.append(Action(kind, old, new, **state))
    return done


def backup_path(directory: pathlib.Path) -> pathlib.Path:
    path = directory / f"community_digits_backup_{time.strftime('%Y%m%dT%H%M%S')}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists; refusing to overwrite a backup")
    return path


def main(argv: list[str] | None = None, client=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument(
        "--backup-dir",
        type=pathlib.Path,
        default=pathlib.Path(tempfile.gettempdir()),
        help="where the timestamped backup goes (default: the system temp dir, outside the repo)",
    )
    args = ap.parse_args(argv)

    if client is None:
        from app.core.supabase_client import get_supabase

        client = get_supabase()
    pairs, read = affected_pairs(fetch_scan_texts(client))
    rows = fetch_reports(client, list(pairs) + list(pairs.values()))
    actions = plan(pairs, rows)
    print(
        f"scans read: {read}; texts whose digest changes: {len(pairs)}; "
        f"old rows found: {len(actions)} "
        f"(merge {sum(a.kind == 'merge' for a in actions)}, rekey {sum(a.kind == 'rekey' for a in actions)})"
    )
    if not args.apply:
        print("dry run: nothing written. Re-run with --apply to merge.")
        return 0
    if not actions:
        print("nothing to apply.")
        return 0
    path = backup_path(args.backup_dir)
    path.write_text(
        json.dumps({"rows": rows, "planned": [asdict(a) for a in actions]}, indent=1, default=str),
        encoding="utf-8",
    )
    print(f"backup written: {path}")
    done = apply(client, pairs)
    print(f"applied: {len(done)} pair(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
