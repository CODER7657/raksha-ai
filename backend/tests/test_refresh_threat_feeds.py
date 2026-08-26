"""The feed refresh job (#115 §1, `PHASE-2-PLAN.md` §01).

`threat_feeds.py` had tests; the script that fills its lists had none. That is
the wrong way round — the loader reads a file and cannot be wrong about much,
while the fetchers parse third-party formats that change without telling us,
and a parser that quietly stops matching is indistinguishable from a quiet
internet.

Nothing here touches the network. The fetchers are replaced or fed fixture text,
because a test that depends on URLhaus being up tells you about URLhaus.

## The failure this file exists for

`lookup()` returning `[]` means "no feed listed this URL". An emptied list is
therefore not a broken feature — it is a **clean bill of health issued to every
URL on the scan path**, and it looks identical to a quiet day. The refresh job
is the only place that can cause it, so the guard belongs here and so does the
test that proves the guard fires.
"""

import pathlib

import pytest

from app.services import threat_feeds
from scripts import refresh_threat_feeds as refresh_job


@pytest.fixture(autouse=True)
def isolated_feed_dir(tmp_path, monkeypatch):
    """Never write to the repository's real lists from a test."""
    monkeypatch.setattr(threat_feeds, "FEED_DIR", tmp_path)
    threat_feeds.reset_cache()
    yield tmp_path
    threat_feeds.reset_cache()


def _write_list(directory: pathlib.Path, feed: str, count: int) -> None:
    body = "# existing\n" + "\n".join(f"{i:064x}" for i in range(count)) + "\n"
    (directory / f"{feed}.txt").write_text(body, encoding="utf-8")


# --- the guard -------------------------------------------------------------


def test_an_empty_fetch_does_not_overwrite_a_working_list(isolated_feed_dir, monkeypatch):
    """The defect this guard was written for.

    A feed answering 200 with an empty body — down, rate-limited, or reformatted
    so the parser matches nothing — used to write zero digests over a working
    list and return a success count of 0. Detection stopped and the exit code
    said everything was fine.
    """
    _write_list(isolated_feed_dir, "urlhaus", 3)
    monkeypatch.setitem(refresh_job.FETCHERS, "urlhaus", list)

    result = refresh_job.refresh("urlhaus")

    assert result == -1, "an empty fetch over a working list must report as skipped"
    assert refresh_job.existing_count("urlhaus") == 3, "the working list was destroyed"


def test_allow_empty_is_required_to_empty_a_list(isolated_feed_dir, monkeypatch):
    """The control. A guard that refused unconditionally would pass the test
    above while making a genuinely-empty feed impossible to record."""
    _write_list(isolated_feed_dir, "urlhaus", 3)
    monkeypatch.setitem(refresh_job.FETCHERS, "urlhaus", list)

    result = refresh_job.refresh("urlhaus", allow_empty=True)

    assert result == 0
    assert refresh_job.existing_count("urlhaus") == 0


def test_an_empty_fetch_over_an_empty_list_is_not_refused(isolated_feed_dir, monkeypatch):
    """A fresh clone has empty lists. Refusing there would mean the first run
    could never succeed — the guard protects data, and there is none to lose."""
    monkeypatch.setitem(refresh_job.FETCHERS, "urlhaus", list)

    assert refresh_job.refresh("urlhaus") == 0


def test_a_fetch_that_raises_leaves_the_file_untouched(isolated_feed_dir, monkeypatch):
    """The path that always worked, pinned so the new guard cannot displace it."""
    _write_list(isolated_feed_dir, "openphish", 5)

    def boom():
        raise RuntimeError("connection reset")

    monkeypatch.setitem(refresh_job.FETCHERS, "openphish", boom)

    assert refresh_job.refresh("openphish") == -1
    assert refresh_job.existing_count("openphish") == 5


def test_a_real_refresh_replaces_the_list(isolated_feed_dir, monkeypatch):
    """The control for every test above: they would all pass with `refresh`
    permanently refusing to write anything."""
    _write_list(isolated_feed_dir, "urlhaus", 2)
    monkeypatch.setitem(
        refresh_job.FETCHERS,
        "urlhaus",
        lambda: ["http://evil.example/login", "http://evil.example/pay"],
    )

    assert refresh_job.refresh("urlhaus") == 2
    assert refresh_job.existing_count("urlhaus") == 2

    written = (isolated_feed_dir / "urlhaus.txt").read_text(encoding="utf-8")
    assert threat_feeds.digest_for("http://evil.example/login") in written


# --- what gets stored ------------------------------------------------------


def test_urls_are_stored_only_as_digests(isolated_feed_dir, monkeypatch):
    """The repository must never carry a directory of live phishing URLs, and a
    leaked copy must not be a working target list."""
    monkeypatch.setitem(
        refresh_job.FETCHERS, "urlhaus", lambda: ["http://phish.example/steal"]
    )
    refresh_job.refresh("urlhaus")

    written = (isolated_feed_dir / "urlhaus.txt").read_text(encoding="utf-8")
    assert "phish.example" not in written
    assert "http" not in written.replace("# ", "")


def test_spellings_of_one_url_collapse_to_one_digest(isolated_feed_dir, monkeypatch):
    """Canonicalisation is applied at write time, not only at lookup. Storing
    the raw spelling would mean a listing missing the message that carries it."""
    monkeypatch.setitem(
        refresh_job.FETCHERS,
        "urlhaus",
        lambda: [
            "http://EVIL.example:80/login",
            "http://evil.example/login#fragment",
            "  http://evil.example/login  ",
        ],
    )

    assert refresh_job.refresh("urlhaus") == 1, "three spellings are one URL"


def test_the_empty_url_digest_is_never_stored(isolated_feed_dir, monkeypatch):
    """A blank line in a feed canonicalises to the empty string, whose digest
    would otherwise match every unparseable URL on the scan path."""
    monkeypatch.setitem(
        refresh_job.FETCHERS, "urlhaus", lambda: ["", "   ", "http://evil.example/x"]
    )
    refresh_job.refresh("urlhaus")

    written = (isolated_feed_dir / "urlhaus.txt").read_text(encoding="utf-8")
    assert threat_feeds.digest_for("") not in written


def test_what_is_written_is_what_the_scan_path_reads(isolated_feed_dir, monkeypatch):
    """End to end across the two halves. The writer and the loader agree on the
    format, or the feature is a no-op nobody notices."""
    url = "http://evil.example/verify"
    monkeypatch.setitem(refresh_job.FETCHERS, "urlhaus", lambda: [url])
    refresh_job.refresh("urlhaus")
    threat_feeds.reset_cache()

    assert threat_feeds.lookup(url) == ["urlhaus"]
    assert threat_feeds.lookup("http://harmless.example/") == []


# --- the parsers -----------------------------------------------------------


def test_urlhaus_csv_is_parsed_from_the_third_column(monkeypatch):
    """URLhaus ships a commented CSV and the URL is column three. Pinned because
    a column moving is exactly the change that yields zero rows and no error."""
    body = (
        "# Dumped at 2026-08-26\n"
        '# id,dateadded,url,url_status\n'
        '"1","2026-08-26","http://evil.example/a","online"\n'
        '"2","2026-08-26","http://evil.example/b","online"\n'
    )
    monkeypatch.setattr(refresh_job, "_fetch", lambda url: body)

    assert refresh_job.fetch_urlhaus() == ["http://evil.example/a", "http://evil.example/b"]


def test_urlhaus_ignores_comments_and_short_rows(monkeypatch):
    monkeypatch.setattr(
        refresh_job, "_fetch", lambda url: "# header\n\n\"1\",\"2026\"\n\"2\",\"x\",\"http://ok.example/\"\n"
    )

    assert refresh_job.fetch_urlhaus() == ["http://ok.example/"]


def test_openphish_is_one_url_per_line(monkeypatch):
    monkeypatch.setattr(
        refresh_job,
        "_fetch",
        lambda url: "http://a.example/1\n\n  http://b.example/2  \n",
    )

    assert refresh_job.fetch_openphish() == ["http://a.example/1", "http://b.example/2"]


# --- the feeds that need credentials ---------------------------------------


@pytest.mark.parametrize(
    ("feed", "variable"),
    [("safebrowsing", "GOOGLE_SAFE_BROWSING_API_KEY"), ("phishtank", "PHISHTANK_APP_KEY")],
)
def test_a_keyed_feed_names_the_variable_it_wants(feed, variable):
    """Two of the four cannot run without credentials. Failing with the name of
    the missing variable is the difference between a five-minute fix and an
    afternoon — and skipping is not the same as succeeding with nothing."""
    with pytest.raises(RuntimeError) as excinfo:
        refresh_job.FETCHERS[feed]()

    assert variable in str(excinfo.value)


def test_a_keyed_feed_skips_rather_than_empties(isolated_feed_dir):
    """The credential path reaches the same protection as the empty path. A
    feed nobody has keys for must not erase whatever it last held."""
    _write_list(isolated_feed_dir, "phishtank", 4)

    assert refresh_job.refresh("phishtank") == -1
    assert refresh_job.existing_count("phishtank") == 4
