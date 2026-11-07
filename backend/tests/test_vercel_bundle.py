"""The deploy bundle (scripts/build_vercel_bundle.py) and where testdata is found.

The bundle is what becomes a public function, so the tests that matter most are
the exclusions: a `.env` with real keys sitting in a developer's `backend/` must
not ride along, and neither must the test suite. The rest checks that the
bundle is complete enough to answer the routes that read `testdata/`, and that
the script cannot be pointed at a directory it would wrongly delete.
"""

import importlib.util
import pathlib

import pytest

from app.core import paths

BACKEND = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bundle", BACKEND / "scripts" / "build_vercel_bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


@pytest.fixture
def repo(tmp_path):
    """A miniature checkout: backend/ with things to keep and things to drop."""
    root = tmp_path / "repo"
    be = root / "backend"
    for rel, text in {
        "main.py": "app = 1\n",
        "index.py": "from main import app\n",
        "vercel.json": "{}\n",
        "requirements.txt": "fastapi\n",
        "app/__init__.py": "",
        "app/core/paths.py": "",
        "app/services/scripts/helper.py": "x = 1\n",
        "app/tests_data/fixture.json": "{}",
        ".python-version": "3.12\n",
        "data/feeds/urlhaus.txt": "abc\n",
        ".env.example": "GROQ_API_KEY=\n",
        ".env": "GROQ_API_KEY=real-secret\n",
        ".env.local": "X=1\n",
        "tests/test_x.py": "",
        "scripts/run.py": "",
        "app/__pycache__/x.cpython-313.pyc": "",
        ".pytest_cache/v": "",
        ".benchmark_cache.json": "{}",
        "requirements-dev.txt": "pytest\n",
    }.items():
        p = be / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (root / "testdata" / "benchmark").mkdir(parents=True)
    (root / "testdata" / "rule_corpus.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "testdata" / "benchmark" / "llm-latest.json").write_text("{}", encoding="utf-8")
    return root


def files(out: pathlib.Path) -> set[str]:
    return {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}


def test_bundle_has_the_app_and_testdata_and_nothing_secret(repo, tmp_path):
    out = bundle.build(tmp_path / "out", backend=repo / "backend", repo=repo)
    got = files(out)
    for needed in ["main.py", "index.py", "vercel.json", "requirements.txt", "app/core/paths.py",
                   "data/feeds/urlhaus.txt", ".env.example", ".python-version",
                   "app/services/scripts/helper.py", "app/tests_data/fixture.json",
                   "testdata/rule_corpus.jsonl", "testdata/benchmark/llm-latest.json"]:
        assert needed in got, needed
    for banned in [".env", ".env.local", "tests/test_x.py", "scripts/run.py", ".benchmark_cache.json",
                   "requirements-dev.txt", "app/__pycache__/x.cpython-313.pyc", ".pytest_cache/v"]:
        assert banned not in got, banned
    assert not any("real-secret" in (out / f).read_text(encoding="utf-8", errors="ignore") for f in got)


def test_rebuilding_replaces_an_earlier_bundle(repo, tmp_path):
    out = bundle.build(tmp_path / "out", backend=repo / "backend", repo=repo)
    (out / "stale.txt").write_text("old", encoding="utf-8")
    bundle.build(tmp_path / "out", backend=repo / "backend", repo=repo)
    assert not (out / "stale.txt").exists()


def test_refuses_to_delete_a_directory_it_did_not_make(repo, tmp_path):
    other = tmp_path / "precious"
    other.mkdir()
    (other / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not a bundle"):
        bundle.build(other, backend=repo / "backend", repo=repo)
    assert (other / "keep.txt").exists()


@pytest.mark.parametrize("where", ["backend", "backend/inside", ".", "testdata", "testdata/out"])
def test_refuses_to_build_into_or_around_a_source(repo, where):
    with pytest.raises(ValueError, match="source directory"):
        bundle.build(repo / where, backend=repo / "backend", repo=repo)


def test_missing_testdata_is_an_error(repo, tmp_path):
    import shutil

    shutil.rmtree(repo / "testdata")
    with pytest.raises(FileNotFoundError):
        bundle.build(tmp_path / "out", backend=repo / "backend", repo=repo)


def test_main_reports_errors_as_exit_1(tmp_path, capsys):
    blocker = tmp_path / "x"
    blocker.mkdir()
    assert bundle.main([str(blocker)]) == 1
    assert "not a bundle" in capsys.readouterr().err


# ---------- app.core.paths ----------

def test_testdata_beside_backend_in_a_checkout(repo):
    assert paths.testdata_dir(repo / "backend") == repo / "testdata"


def test_bundled_copy_wins(repo, tmp_path):
    out = bundle.build(tmp_path / "out", backend=repo / "backend", repo=repo)
    assert paths.testdata_dir(out) == out / "testdata"


def test_this_checkout_resolves_to_the_real_testdata():
    assert (paths.TESTDATA / "rule_corpus.jsonl").exists()
