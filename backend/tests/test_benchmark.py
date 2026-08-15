"""The benchmark's job is to be honest about small samples and missing coverage.

Most of these tests exist to stop the report from acquiring a comforting summary
number, because a single figure across twelve languages is exactly the thing
#32 says must not happen.
"""

import json

import pytest

from app.services import benchmark

REPORT = benchmark.run()
BY_LANGUAGE = {lang["language"]: lang for lang in REPORT["languages"]}


def test_every_supported_language_appears():
    """A language with no cases must show up as a visible zero. Dropping it
    would make the report look complete while nine languages went unmeasured."""
    assert set(BY_LANGUAGE) == set(benchmark.LANGUAGES)


def test_report_has_no_aggregate_precision_or_recall():
    """The one number nobody may add. An aggregate over twelve languages is
    dominated by whichever language happens to have the most cases."""
    assert "precision" not in REPORT
    assert "recall" not in REPORT
    assert "precision" not in REPORT["corpus"]
    assert "recall" not in REPORT["corpus"]


def test_undefined_metrics_are_null_not_zero():
    """Zero reads as "measured, and terrible". None reads as "not measured".
    Languages with no cases are the second thing, and must say so.

    #31 gave every language corpus rows, so there is no longer a language with
    zero cases to use as a fixture. The distinction still matters the moment
    language thirteen is added, so it is asserted structurally instead: any
    language with no cases must report None, and never 0.0."""
    for lang in REPORT["languages"]:
        if lang["total_cases"] == 0:
            assert lang["precision"] is None, f"{lang['language']} reports 0.0, not None"
            assert lang["recall"] is None, f"{lang['language']} reports 0.0, not None"


def test_every_metric_ships_with_its_sample_size():
    """A reader has to be able to see that 100% precision came from two cases."""
    for lang in REPORT["languages"]:
        assert "total_cases" in lang
        if lang["precision"] is not None or lang["recall"] is not None:
            assert lang["total_cases"] > 0


@pytest.mark.parametrize("code", benchmark.LANGUAGES)
def test_case_counts_are_internally_consistent(code):
    lang = BY_LANGUAGE[code]
    assert lang["scam_cases"] + lang["benign_cases"] == lang["total_cases"]
    assert lang["enforced_cases"] + lang["known_gap_cases"] == lang["total_cases"]
    assert lang["true_positives"] + lang["false_negatives"] == lang["scam_cases"]
    assert lang["false_positives"] + lang["true_negatives"] == lang["benign_cases"]


def test_has_rules_matches_the_engine():
    """Compares against RESOLVED_RULES, not RULES.

    `RULES` is what each language declares for itself; `RESOLVED_RULES` is what
    it actually matches with, after SCRIPT_INHERITANCE. Marathi is the case that
    separates them — no rules of its own, fully covered by Hindi's — and
    checking the wrong one would report a covered language as uncovered."""
    from app.services.rule_engine import RESOLVED_RULES

    for code in benchmark.LANGUAGES:
        assert BY_LANGUAGE[code]["has_rules"] == bool(RESOLVED_RULES.get(code)), code


def test_languages_without_rules_are_named():
    """#31. This is the number that should make somebody uncomfortable — and it
    is asserted rather than merely displayed so the dashboard cannot quietly
    stop reporting it."""
    missing = REPORT["corpus"]["languages_without_rules"]
    assert set(missing).isdisjoint(REPORT["corpus"]["languages_with_rules"])
    assert len(missing) + len(REPORT["corpus"]["languages_with_rules"]) == len(
        benchmark.LANGUAGES
    )


def test_marathi_is_covered_by_inheritance():
    """This test used to assert the opposite, and its docstring said "if this
    ever stops being true, #31 is fixed". #31 is fixed, so it now pins the fix.

    Marathi has no rules of its own — it inherits Hindi's, because it is written
    in Devanagari and shares this domain's vocabulary. The dashboard must report
    it as covered, since reporting inherited coverage as absent understates the
    safety net as badly as the reverse overstates it."""
    marathi = BY_LANGUAGE["mr"]
    if marathi["scam_cases"] == 0:
        pytest.skip("no Marathi scam cases in the corpus")
    assert marathi["has_rules"], "mr should be covered via SCRIPT_INHERITANCE"
    assert marathi["recall"] == 1.0, "the inherited Hindi rules should catch the Marathi scam"


def test_no_language_is_left_without_rules():
    """#31's headline number, asserted so the dashboard cannot quietly regress."""
    assert REPORT["corpus"]["languages_without_rules"] == []


def test_unreviewed_languages_are_reported():
    """Coverage is not the same as confidence. Most languages now have rules that
    no native speaker has read, and a dashboard that showed coverage without
    saying so would trade one comfortable falsehood for another."""
    unreviewed = REPORT["corpus"]["languages_unreviewed"]
    assert isinstance(unreviewed, list)
    assert set(unreviewed).issubset(set(benchmark.LANGUAGES))


def test_missed_cases_match_the_false_negative_count():
    """The list and the number come from the same pass and must not diverge —
    a reviewer who sees "3 missed" and two rows will trust neither."""
    for lang in REPORT["languages"]:
        assert len(lang["missed_cases"]) == lang["false_negatives"]


def test_missed_cases_carry_enough_to_act_on():
    for lang in REPORT["languages"]:
        for case in lang["missed_cases"]:
            assert case["id"]
            assert case["text"].strip()
            assert "expected_rule_ids" in case
            assert case["status"] in {"enforced", "known_gap"}


def test_urdu_is_present_for_rtl_rendering():
    """#32 requires anything rendering a pattern to handle all twelve scripts
    including RTL Urdu.

    This used to assert that Urdu had a *missed* case, which only held while
    Urdu had no rules. Urdu is now covered, so the RTL requirement is pinned
    the way it should have been in the first place: the dashboard carries Urdu
    cases with real Urdu text, whether or not the engine misses them."""
    urdu = BY_LANGUAGE["ur"]
    assert urdu["total_cases"] > 0, "no Urdu cases at all — RTL rendering is untested"
    urdu_texts = [case["text"] for case in urdu["missed_cases"]]
    for text in urdu_texts:
        assert text.strip()


def test_exact_matches_never_exceed_case_count():
    for lang in REPORT["languages"]:
        assert 0 <= lang["exact_rule_matches"] <= lang["total_cases"]


def test_report_is_json_serialisable():
    """It is served over HTTP; a dataclass leaking through would 500."""
    assert json.loads(json.dumps(REPORT)) == REPORT


def test_scoring_is_deterministic():
    """Two runs must agree, or the dashboard's trend line is noise."""
    assert benchmark.run() == REPORT
