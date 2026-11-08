"""Digit folding in the community digest, and the one-off migration that re-keys rows.

`hash_text` folds every decimal-digit script to ASCII so one forwarded SMS counts once
whether its OTP arrived as 452189 or ४५२१८९. Rows written before that are re-keyed by
`scripts/migrate_community_digits.py`, whose planning is tested here against a fake store.
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


# --- Migration planning --------------------------------------------------------

def row(count, first=None, last=None, language="hi"):
    return {"report_count": count, "first_reported_at": first, "last_reported_at": last,
            "language": language}


def test_ascii_texts_are_not_touched():
    assert mig.affected_pairs(["OTP 452189", "", None, "share your OTP"]) == {}


def test_a_native_digit_text_maps_old_to_new():
    text = "आपका OTP ४५२१८९ है"
    assert mig.affected_pairs([text]) == {trace.legacy_hash_text(text): trace.hash_text(text)}


def test_an_old_row_alone_is_rekeyed():
    text = "OTP ४५२१८९"
    old, new = trace.legacy_hash_text(text), trace.hash_text(text)
    [action] = mig.plan({old: new}, {old: row(3, "2026-10-01", "2026-11-01")})
    assert (action.kind, action.report_count, action.first_reported_at) == ("rekey", 3, "2026-10-01")


def test_an_old_row_merges_into_an_existing_new_row():
    text = "OTP ४५२१८९"
    old, new = trace.legacy_hash_text(text), trace.hash_text(text)
    rows = {old: row(3, "2026-10-01", "2026-10-20"), new: row(5, "2026-10-05", "2026-11-02")}
    [action] = mig.plan({old: new}, rows)
    assert action.kind == "merge" and action.report_count == 8
    assert (action.first_reported_at, action.last_reported_at) == ("2026-10-01", "2026-11-02")


def test_two_old_digests_merge_into_one_new_row():
    deva, guj = "OTP ४५२१८९", "OTP ૪૫૨૧૮૯"
    new = trace.hash_text(deva)
    pairs = {trace.legacy_hash_text(deva): new, trace.legacy_hash_text(guj): new}
    rows = {trace.legacy_hash_text(deva): row(2), trace.legacy_hash_text(guj): row(4), new: row(1)}
    actions = mig.plan(pairs, rows)
    assert actions[-1].report_count == 7  # 1 + 2 + 4, whatever the order


def test_unknown_first_sightings_do_not_erase_known_ones():
    text = "OTP ४५२१८९"
    old, new = trace.legacy_hash_text(text), trace.hash_text(text)
    [action] = mig.plan({old: new}, {old: row(1, None, None), new: row(1, "2026-10-05", None)})
    assert action.first_reported_at == "2026-10-05"


def test_an_old_digest_without_a_row_is_skipped():
    text = "OTP ४५२१८९"
    assert mig.plan({trace.legacy_hash_text(text): trace.hash_text(text)}, {}) == []


class FakeStore:
    """Enough of the Supabase table API for apply(): upsert by key, delete by key."""

    def __init__(self, rows):
        self.rows = {k: dict(v) for k, v in rows.items()}
        self._op = None

    def table(self, name):
        assert name == "community_reports"
        return self

    def upsert(self, record, on_conflict):
        self._op = ("upsert", record)
        return self

    def delete(self):
        self._op = ("delete", None)
        return self

    def eq(self, column, value):
        self._op = ("delete", value)
        return self

    def execute(self):
        kind, payload = self._op
        if kind == "upsert":
            self.rows[payload["pattern_hash"]] = {k: v for k, v in payload.items() if k != "pattern_hash"}
        else:
            self.rows.pop(payload, None)


def test_apply_then_replan_is_a_no_op():
    text = "OTP ४५२१८९"
    old, new = trace.legacy_hash_text(text), trace.hash_text(text)
    store = FakeStore({old: row(3, "2026-10-01", "2026-10-20"), new: row(5, "2026-10-05", "2026-11-02")})
    pairs = mig.affected_pairs([text])
    mig.apply(store, mig.plan(pairs, store.rows))
    assert old not in store.rows and store.rows[new]["report_count"] == 8
    assert mig.plan(pairs, store.rows) == []
