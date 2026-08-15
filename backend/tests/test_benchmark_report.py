"""The committed-artifact path the dashboard reads (#50).

Scoring is a CLI because a run spends production's API quota per case. These
cover the other end: reading what it wrote, and failing softly when it has not
written anything yet.
"""

import json

from app.services import benchmark, benchmark_llm


def test_missing_report_is_none_not_an_error(tmp_path):
    """No run committed yet is a state the dashboard renders, not a failure."""
    assert benchmark_llm.load_report(tmp_path / "absent.json") is None


def test_corrupt_report_does_not_take_the_page_down(tmp_path):
    """A truncated write must not break the offline half, which is computed
    live and always available."""
    bad = tmp_path / "llm.json"
    bad.write_text('{"languages": [', encoding="utf-8")
    assert benchmark_llm.load_report(bad) is None


def test_report_round_trips(tmp_path):
    written = {"languages": [{"language": "en", "precision": 0.9565}], "run": {"models": ["groq"]}}
    path = tmp_path / "llm.json"
    path.write_text(json.dumps(written), encoding="utf-8")

    assert benchmark_llm.load_report(path) == written


def test_the_committed_report_matches_the_shape_the_dashboard_expects():
    """Guards the real artifact in testdata/, not a fixture. If a future change
    to `run()` drops a field the frontend reads, this fails here rather than as
    a blank column nobody notices."""
    report = benchmark_llm.load_report()
    if report is None:
        return  # nothing committed yet; other tests cover that path

    assert {"languages", "run", "leakage"} <= report.keys()
    assert {"models", "prompt_version"} <= report["run"].keys()

    for language in report["languages"]:
        assert {
            "language",
            "total_cases",
            "scored_cases",
            "precision",
            "recall",
            "missed_cases",
            "false_positive_cases",
        } <= language.keys()


def test_a_run_records_what_it_scored_against():
    """Without this the report goes stale invisibly — cases get added, the
    numbers keep rendering, and they describe a corpus that no longer exists.
    Deliberately not a currency check: re-running spends API quota, so failing
    the build on every corpus edit would discourage adding cases. This only
    pins that the field exists, so the drift stays *detectable*."""
    report = benchmark_llm.load_report()
    if report is None:
        return

    run = report["run"]
    assert {"corpus_rows", "scored_rows", "corpus_digest"} <= run.keys(), (
        "a run must record the corpus it measured, or staleness is undetectable"
    )
    assert run["corpus_rows"] >= run["scored_rows"]
    assert len(run["corpus_digest"]) == 12


def test_digest_tracks_content_not_formatting():
    """Reordering rows or reformatting the file must not read as a corpus
    change — the question is "were these the same cases?", not "was the file
    byte-identical?"."""
    a = [{"id": "x", "text": "one"}, {"id": "y", "text": "two"}]
    assert benchmark_llm.corpus_digest(a) == benchmark_llm.corpus_digest(list(reversed(a)))


def test_digest_changes_when_a_case_is_added_or_edited():
    base = [{"id": "x", "text": "one"}]
    assert benchmark_llm.corpus_digest(base) != benchmark_llm.corpus_digest(
        [*base, {"id": "y", "text": "two"}]
    )
    assert benchmark_llm.corpus_digest(base) != benchmark_llm.corpus_digest(
        [{"id": "x", "text": "one edited"}]
    )


def test_both_halves_itemise_false_positives_the_same_way():
    """The dashboard renders both with one component, so the field has to exist
    on both. It was a bare count on the offline half until #50."""
    offline = benchmark.run()["languages"][0]
    assert "false_positive_cases" in offline

    scored = benchmark_llm.score_language("en", [])
    assert hasattr(scored, "false_positive_cases")


def test_offline_false_positives_name_the_rules_that_fired():
    """A precision figure cannot distinguish one odd edge case from every bank
    alert in the country — the reviewer needs the text and the cause."""
    report = benchmark.run()
    warned = [c for lang in report["languages"] for c in lang["false_positive_cases"]]
    if not warned:
        return  # a corpus with no benign false positives is a valid state

    for case in warned:
        assert case["text"], "a false positive with no message text is unreviewable"
        assert case["fired_rule_ids"], "must name which rule over-warned"
