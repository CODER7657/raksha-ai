"""Digit folding in the community digest, and the one-off migration that re-keys rows.

`hash_text` folds every decimal-digit script to ASCII so one forwarded SMS counts once
whether its OTP arrived as 452189 or ४५२१८९. Rows written before that are re-keyed by
`scripts/migrate_community_digits.py`, tested here against an in-memory fake client.
"""

import importlib.util
import pathlib
import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services import trace

_path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "migrate_community_digits.py"
_spec = importlib.util.spec_from_file_location("migrate_community_digits", _path)
mig = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mig  # @dataclass resolves the module through sys.modules
_spec.loader.exec_module(mig)

SCRIPTS = {  # ASCII digit -> the same digit in another script
    "devanagari": "०१२३४५६७८९",
    "gujarati": "૦૧૨૩૪૫૬૭૮૯",
    "bengali": "০১২৩৪৫৬৭৮৯",
    "tamil": "௦௧௨௩௪௫௬௭௮௯",
    "telugu": "౦౧౨౩౪౫౬౭౮౯",
}
TEXT = "OTP ४५२१८९"
OLD, NEW = trace.legacy_hash_text(TEXT), trace.hash_text(TEXT)


@pytest.mark.parametrize("script", SCRIPTS)
def test_an_otp_in_any_digit_script_counts_as_the_same_message(script):
    native = "Your OTP is 452189".translate(str.maketrans("0123456789", SCRIPTS[script]))
    assert trace.hash_text(native) == trace.hash_text("Your OTP is 452189")


@settings(max_examples=200, deadline=None, derandomize=True)
@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=200))
def test_ascii_digests_never_change(text):
    """Existing rows for messages with only ASCII digits keep their key."""
    if all(not c.isdecimal() or c.isascii() for c in text):
        assert trace.hash_text(text) == trace.legacy_hash_text(text)


@settings(max_examples=200, deadline=None, derandomize=True)
@given(st.text(max_size=200), st.sampled_from(list(SCRIPTS.values())))
def test_folding_is_the_same_as_writing_the_digits_in_ascii(text, digits):
    swapped = text.translate(str.maketrans("0123456789", digits))
    assert trace.hash_text(swapped) == trace.hash_text(text)


def test_the_audit_digest_keeps_its_old_meaning():
    """Audit records are hash-chained; their digest normalisation does not change."""
    assert trace.audit_digest("OTP ४५२१८९") != trace.audit_digest("OTP 452189")


# --- Migration ---------------------------------------------------------------


def row(count, first=None, last=None, language="hi"):
    return {
        "report_count": count,
        "first_reported_at": first,
        "last_reported_at": last,
        "language": language,
    }


def test_ascii_texts_are_not_touched():
    pairs, read = mig.affected_pairs(["OTP 452189", "", None, "share your OTP"])
    assert pairs == {} and read == 4


def test_a_native_digit_text_maps_old_to_new():
    pairs, _ = mig.affected_pairs([TEXT])
    assert pairs == {OLD: NEW}


def test_an_old_row_alone_is_rekeyed():
    [action] = mig.plan({OLD: NEW}, {OLD: row(3, "2026-10-01", "2026-11-01")})
    assert (action.kind, action.report_count, action.first_reported_at) == ("rekey", 3, "2026-10-01")


def test_an_old_row_merges_into_an_existing_new_row():
    rows = {OLD: row(3, "2026-10-01", "2026-10-20"), NEW: row(5, "2026-10-05", "2026-11-02")}
    [action] = mig.plan({OLD: NEW}, rows)
    assert action.kind == "merge" and action.report_count == 8
    assert (action.first_reported_at, action.last_reported_at) == ("2026-10-01", "2026-11-02")


def test_an_unknown_first_sighting_stays_unknown():
    """Migration 0014: NULL means older than 0014. An all-time count with a recent first
    sighting would invent a velocity, so NULL wins on either side."""
    [a] = mig.plan({OLD: NEW}, {OLD: row(40, None, "2026-10-01"), NEW: row(2, "2026-11-08", "2026-11-08")})
    assert a.first_reported_at is None and a.report_count == 42
    [b] = mig.plan({OLD: NEW}, {OLD: row(2, "2026-11-08", None), NEW: row(40, None, "2026-10-01")})
    assert b.first_reported_at is None


def test_two_old_digests_merge_into_one_new_row():
    guj = "OTP ૪૫૨૧૮૯"
    pairs = {OLD: NEW, trace.legacy_hash_text(guj): NEW}
    rows = {OLD: row(2), trace.legacy_hash_text(guj): row(4), NEW: row(1)}
    assert mig.plan(pairs, rows)[-1].report_count == 7


def test_an_old_digest_without_a_row_is_skipped():
    assert mig.plan({OLD: NEW}, {}) == []


class _Result:
    def __init__(self, data):
        self.data = data


class FakeStore:
    """The slice of the Supabase client the script uses, over two in-memory tables."""

    def __init__(self, reports=None, scans=None, fail_delete=False):
        self.reports = {k: dict(v) for k, v in (reports or {}).items()}
        self.scans = list(scans or [])
        self.fail_delete = fail_delete
        self.calls = []

    def table(self, name):
        return _Query(self, name)


class _Query:
    def __init__(self, store, name):
        self.store, self.name, self.op, self.args = store, name, "select", {}

    def select(self, columns):
        return self

    def order(self, column):
        self.args["order"] = column
        return self

    def range(self, start, end):
        self.args["range"] = (start, end)
        return self

    def in_(self, column, values):
        self.args["in"] = list(values)
        return self

    def upsert(self, record, on_conflict):
        self.op, self.args["record"] = "upsert", record
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, column, value):
        self.args["eq"] = value
        return self

    def execute(self):
        s = self.store
        s.calls.append((self.name, self.op, dict(self.args)))
        if self.name == "scans":
            assert self.args.get("order") == "id", "pages must be ordered"
            start, end = self.args["range"]
            rows = [{"id": i, "input_text": t} for i, t in enumerate(s.scans)]
            return _Result(rows[start : end + 1])
        if self.op == "upsert":
            record = dict(self.args["record"])
            s.reports[record.pop("pattern_hash")] = record
            return _Result(None)
        if self.op == "delete":
            if s.fail_delete:
                raise ConnectionError("network dropped")
            s.reports.pop(self.args["eq"], None)
            return _Result(None)
        wanted = self.args.get("in", [])
        return _Result([{"pattern_hash": k, **v} for k, v in s.reports.items() if k in wanted])


def test_scans_are_paged_in_id_order_without_skips():
    texts = [f"msg {i}" for i in range(2500)]
    store = FakeStore(scans=texts)
    assert list(mig.fetch_scan_texts(store, page=1000)) == texts
    ranges = [c[2]["range"] for c in store.calls if c[0] == "scans"]
    assert ranges == [(0, 999), (1000, 1999), (2000, 2999)]


def test_report_lookups_are_chunked():
    digests = [f"{i:064x}" for i in range(250)]
    store = FakeStore(reports={d: row(1) for d in digests[:3]})
    assert set(mig.fetch_reports(store, digests, chunk=100)) == set(digests[:3])
    assert len(store.calls) == 3


def test_apply_merges_and_a_second_run_is_a_no_op():
    store = FakeStore({OLD: row(3, "2026-10-01", "2026-10-20"), NEW: row(5, "2026-10-05", "2026-11-02")})
    pairs, _ = mig.affected_pairs([TEXT])
    assert len(mig.apply(store, pairs)) == 1
    assert OLD not in store.reports and store.reports[NEW]["report_count"] == 8
    assert mig.apply(store, pairs) == []


def test_apply_rereads_rows_so_a_live_increment_is_kept():
    """A report that lands after planning is not overwritten: apply reads again."""
    store = FakeStore({OLD: row(3), NEW: row(5)})
    pairs, _ = mig.affected_pairs([TEXT])
    store.reports[NEW]["report_count"] = 7  # two live reports after planning
    mig.apply(store, pairs)
    assert store.reports[NEW]["report_count"] == 10


def test_an_interrupted_apply_surfaces_the_error():
    store = FakeStore({OLD: row(3), NEW: row(5)}, fail_delete=True)
    pairs, _ = mig.affected_pairs([TEXT])
    with pytest.raises(ConnectionError):
        mig.apply(store, pairs)


def test_dry_run_writes_nothing(tmp_path, capsys):
    store = FakeStore({OLD: row(3)}, scans=[TEXT, "plain"])
    assert mig.main(["--backup-dir", str(tmp_path)], client=store) == 0
    assert "old rows found: 1" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())
    assert not [c for c in store.calls if c[1] in ("upsert", "delete")]


def test_apply_writes_a_backup_and_never_overwrites_one(tmp_path, monkeypatch):
    store = FakeStore({OLD: row(3)}, scans=[TEXT])
    assert mig.main(["--apply", "--backup-dir", str(tmp_path)], client=store) == 0
    [backup] = list(tmp_path.iterdir())
    assert backup.name.startswith("community_digits_backup_")
    stamp = backup.stem.removeprefix("community_digits_backup_")
    monkeypatch.setattr(mig.time, "strftime", lambda fmt: stamp)
    with pytest.raises(FileExistsError):
        mig.backup_path(tmp_path)
