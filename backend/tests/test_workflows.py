"""Pins the deploy-config fixes in .github/workflows, which nothing else runs.

A workflow is only exercised on GitHub, after merge, on its own schedule. The
feed refresh failed 35 nights running (GH006: it pushed to protected master)
before anyone read a log, so the properties that fix it are asserted here,
where a PR that undoes one goes red the same day.
"""

import pathlib
import re

import pytest
import yaml

WORKFLOWS = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _load(name: str) -> dict:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # PyYAML reads the bare key `on` as the boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def _steps(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def _step(workflow: dict, job: str, name: str) -> dict:
    matches = [s for s in _steps(workflow, job) if s.get("name") == name]
    assert matches, f"no step named {name!r} in {job}"
    return matches[0]


# --- refresh-threat-feeds.yml ------------------------------------------------


@pytest.fixture(scope="module")
def feeds():
    return _load("refresh-threat-feeds.yml")


def _all_run_text(workflow: dict) -> str:
    return "\n".join(s.get("run", "") for job in workflow["jobs"] for s in _steps(workflow, job))


def test_feeds_never_push_to_master(feeds):
    """Master requires a reviewed PR. A push to it can only fail."""
    run = _all_run_text(feeds)
    for line in run.splitlines():
        if "git push" in line:
            assert "BOT_BRANCH" in line, f"push without the bot branch: {line.strip()}"
            assert "master" not in line
    assert not re.search(r"^\s*git push\s*$", run, re.MULTILINE), "a bare push targets the checked-out master"


def test_feeds_use_a_dedicated_bot_branch(feeds):
    branch = feeds["env"]["BOT_BRANCH"]
    assert branch.startswith("bot/")
    assert branch not in {"master", "main"}


def test_feeds_open_or_reuse_a_pr_against_master(feeds):
    run = _step(feeds, "refresh", "Open or update the feed refresh PR")["run"]
    assert "gh pr list --head \"$BOT_BRANCH\" --base master --state open" in run
    assert "gh pr create --base master --head \"$BOT_BRANCH\"" in run
    # A refused PR must be loud, and say which setting fixes it.
    assert "Allow GitHub Actions to create and approve pull requests" in run
    assert "exit 1" in run


def test_feeds_skip_the_pr_when_nothing_changed(feeds):
    run = _step(feeds, "refresh", "Open or update the feed refresh PR")["run"]
    assert run.index("git diff --quiet -- data/feeds/") < run.index("git commit")


def test_feeds_have_exactly_the_permissions_they_need(feeds):
    assert feeds["permissions"] == {"contents": "write", "pull-requests": "write"}


def test_feeds_read_the_urlhaus_key_from_secrets_only(feeds):
    step = _step(feeds, "refresh", "Rebuild the hash lists")
    assert step["env"]["URLHAUS_AUTH_KEY"] == "${{ secrets.URLHAUS_AUTH_KEY }}"


def test_no_script_uses_the_retired_keyless_urlhaus_downloads():
    """Every urlhaus.abuse.ch/downloads/ URL has answered 410 since 2026-10-21."""
    backend = pathlib.Path(__file__).resolve().parents[1]
    for path in [*backend.glob("scripts/*.py"), *backend.glob("app/**/*.py")]:
        text = path.read_text(encoding="utf-8")
        assert "urlhaus.abuse.ch/downloads" not in text, path


# --- frontend-ci.yml ---------------------------------------------------------


@pytest.fixture(scope="module")
def frontend_ci():
    return _load("frontend-ci.yml")


def test_frontend_ci_builds_with_well_formed_env(frontend_ci):
    env = _step(frontend_ci, "build", "Build")["env"]
    assert env["VITE_API_BASE_URL"].startswith("https://")
    assert not env["VITE_API_BASE_URL"].endswith("/")
    assert env["VITE_SUPABASE_URL"].startswith("https://")
    assert env["VITE_SUPABASE_ANON_KEY"]


def test_frontend_ci_proves_the_guard_rejects_the_live_placeholder(frontend_ci):
    step = _step(frontend_ci, "build", "Build refuses a placeholder API URL")
    assert step["env"]["VITE_API_BASE_URL"] == "[SENSITIVE]"
    assert "VITE_API_BASE_URL is not an absolute URL" in step["run"]


def test_frontend_ci_runs_the_unit_tests(frontend_ci):
    assert _step(frontend_ci, "build", "Unit tests")["run"] == "npm test"


# --- keep-alive.yml ----------------------------------------------------------


def test_keep_alive_stays_off_the_actions_quota():
    """Private repo: 2,000 free Actions minutes a month, each run billed as a
    full minute. Render sleeps after 15 minutes idle, so a useful schedule is
    every 14 minutes or less — at least 3,100 runs a month, over the quota on
    its own. Warming belongs to an external pinger (see docs/DEPLOY-CHECKLIST)."""
    workflow = _load("keep-alive.yml")
    assert "schedule" not in (workflow["on"] or {})


# --- backend-ci.yml ----------------------------------------------------------


def test_backend_ci_lints_with_the_pinned_ruff():
    """An unpinned `pip install ruff` pulled 0.17.4, whose new rules failed lint
    on code nobody had touched. The version lives in requirements-dev.txt only."""
    workflow = _load("backend-ci.yml")
    install = _step(workflow, "build", "Install dependencies")["run"]
    assert "pip install -r requirements-dev.txt" in install
    for line in install.splitlines():
        if "pip install" in line:
            assert "ruff" not in line, f"ruff installed outside requirements-dev.txt: {line.strip()}"

    dev = (pathlib.Path(__file__).resolve().parents[1] / "requirements-dev.txt").read_text(encoding="utf-8")
    assert re.search(r"^ruff==\d+\.\d+\.\d+$", dev, re.MULTILINE), "ruff must be pinned exactly"
