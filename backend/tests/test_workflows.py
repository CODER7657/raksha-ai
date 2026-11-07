"""Pins the deploy-config fixes in .github/workflows, which nothing else runs.

A workflow is only exercised on GitHub, after merge, on its own schedule. The
feed refresh failed 35 nights running (GH006: it pushed to protected master)
before anyone read a log, so the properties that fix it are asserted here,
where a PR that undoes one goes red the same day.
"""

import http.server
import os
import pathlib
import re
import shutil
import subprocess
import threading
from typing import ClassVar

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


# --- supabase-keep-alive.yml -------------------------------------------------
#
# Supabase pauses a free project after 7 days idle. The schedule and the query
# are pinned below, and the step's own shell script is run against a local
# fake so its pass, warn and fail paths are exercised rather than read.


@pytest.fixture(scope="module")
def supabase_keep_alive():
    return _load("supabase-keep-alive.yml")


def _cron_day_step(cron: str) -> int:
    _minute, _hour, day, month, weekday = cron.split()
    assert (month, weekday) == ("*", "*"), "only a day-of-month step is reasoned about here"
    return 1 if day == "*" else int(day.removeprefix("*/"))


def test_supabase_ping_runs_well_inside_the_7_day_pause(supabase_keep_alive):
    (entry,) = supabase_keep_alive["on"]["schedule"]
    step = _cron_day_step(entry["cron"])
    # Two dropped runs in a row must still land before day 7.
    assert 3 * step < 7 + 3, f"every {step} days leaves no room for missed runs"
    assert step <= 3
    assert "workflow_dispatch" in supabase_keep_alive["on"]


def test_supabase_ping_needs_no_token_permissions(supabase_keep_alive):
    assert supabase_keep_alive["permissions"] == {}


def test_supabase_ping_reads_credentials_from_secrets(supabase_keep_alive):
    env = _step(supabase_keep_alive, "ping", "Query the database")["env"]
    assert env == {
        "SUPABASE_URL": "${{ secrets.SUPABASE_URL }}",
        "SUPABASE_ANON_KEY": "${{ secrets.SUPABASE_ANON_KEY }}",
    }


def test_supabase_ping_sends_the_key_in_headers_only(supabase_keep_alive):
    run = _step(supabase_keep_alive, "ping", "Query the database")["run"]
    url_lines = [line for line in run.splitlines() if "/rest/v1/" in line]
    assert url_lines and all("SUPABASE_ANON_KEY" not in line for line in url_lines)
    assert not re.search(r"echo[^\n]*SUPABASE_ANON_KEY", run), "the key must never be echoed"


def _find_bash() -> str | None:
    """bash as on the runner. On Windows, `bash` on PATH is often WSL's
    launcher, which cannot see this checkout, so Git's own bash is preferred."""
    if os.name == "nt" and (git := shutil.which("git")):
        candidate = pathlib.Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if candidate.exists():
            return str(candidate)
    return shutil.which("bash")


BASH = _find_bash()
SHELL = BASH and shutil.which("curl")


class _FakeSupabase(http.server.BaseHTTPRequestHandler):
    status = 200
    body = b'[{"id":1}]'
    seen: ClassVar[list] = []

    def do_GET(self):
        type(self).seen.append((self.path, self.headers.get("apikey"), self.headers.get("Authorization")))
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *_args):
        pass


@pytest.fixture
def fake_supabase():
    _FakeSupabase.seen = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeSupabase)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def _run_ping(workflow: dict, env: dict, tmp_path) -> subprocess.CompletedProcess:
    script = _step(workflow, "ping", "Query the database")["run"]
    # Drop retries so the failure cases finish in seconds, not 30.
    script = script.replace("--retry 3 --retry-delay 10 --retry-all-errors", "")
    path = tmp_path / "ping.sh"
    path.write_text(script, encoding="utf-8", newline="\n")
    full_env = {**os.environ, "RUNNER_TEMP": tmp_path.as_posix(), **env}
    return subprocess.run(
        [BASH, "-e", path.as_posix()], env=full_env, capture_output=True, text=True, timeout=60, check=False
    )


@pytest.mark.skipif(not SHELL, reason="needs bash and curl, as on the Actions runner")
def test_supabase_ping_passes_against_a_live_project(supabase_keep_alive, fake_supabase, tmp_path):
    _FakeSupabase.status, _FakeSupabase.body = 200, b'[{"id":1}]'
    url = f"http://127.0.0.1:{fake_supabase.server_port}/"
    result = _run_ping(supabase_keep_alive, {"SUPABASE_URL": url, "SUPABASE_ANON_KEY": "anon-test"}, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "HTTP 200" in result.stdout
    assert "::warning::" not in result.stdout
    path, apikey, auth = _FakeSupabase.seen[0]
    assert path == "/rest/v1/scam_patterns?select=id&limit=1", "trailing slash on the URL must not double up"
    assert apikey == "anon-test"
    assert auth is None, "publishable keys are not JWTs and break as a Bearer token"
    assert "anon-test" not in result.stdout + result.stderr


@pytest.mark.skipif(not SHELL, reason="needs bash and curl, as on the Actions runner")
def test_supabase_ping_warns_on_an_unseeded_project(supabase_keep_alive, fake_supabase, tmp_path):
    _FakeSupabase.status, _FakeSupabase.body = 200, b"[]\n"
    url = f"http://127.0.0.1:{fake_supabase.server_port}"
    result = _run_ping(supabase_keep_alive, {"SUPABASE_URL": url, "SUPABASE_ANON_KEY": "k"}, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "::warning::scam_patterns is empty" in result.stdout


@pytest.mark.skipif(not SHELL, reason="needs bash and curl, as on the Actions runner")
@pytest.mark.parametrize("status", [401, 503])
def test_supabase_ping_fails_on_an_error_status(supabase_keep_alive, fake_supabase, tmp_path, status):
    _FakeSupabase.status, _FakeSupabase.body = status, b"{}"
    url = f"http://127.0.0.1:{fake_supabase.server_port}"
    result = _run_ping(supabase_keep_alive, {"SUPABASE_URL": url, "SUPABASE_ANON_KEY": "k"}, tmp_path)

    assert result.returncode == 1
    assert f"Supabase answered {status}" in result.stdout


@pytest.mark.skipif(not SHELL, reason="needs bash and curl, as on the Actions runner")
def test_supabase_ping_fails_when_the_host_is_gone(supabase_keep_alive, tmp_path):
    """The shape of the original outage: the project's host stopped resolving."""
    env = {"SUPABASE_URL": "http://does-not-exist.invalid", "SUPABASE_ANON_KEY": "k"}
    result = _run_ping(supabase_keep_alive, env, tmp_path)

    assert result.returncode == 1
    assert "Supabase answered 000" in result.stdout


@pytest.mark.skipif(not SHELL, reason="needs bash and curl, as on the Actions runner")
@pytest.mark.parametrize("missing", ["SUPABASE_URL", "SUPABASE_ANON_KEY"])
def test_supabase_ping_names_a_missing_secret(supabase_keep_alive, tmp_path, missing):
    env = {"SUPABASE_URL": "http://127.0.0.1:9", "SUPABASE_ANON_KEY": "k", missing: ""}
    result = _run_ping(supabase_keep_alive, env, tmp_path)

    assert result.returncode == 1
    assert f"Missing repository secrets: {missing}" in result.stdout


# ---------- backend deploy (Vercel) ----------

@pytest.fixture
def backend_deploy() -> dict:
    return _load("backend-deploy.yml")


def _deploy_steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["deploy"]["steps"]


def test_backend_deploy_never_runs_on_pull_requests(backend_deploy):
    """A pull_request run of a same-repo branch can read VERCEL_TOKEN and runs
    the workflow as the branch wrote it; see the note in frontend-deploy.yml."""
    assert "pull_request" not in backend_deploy["on"]
    assert "pull_request_target" not in backend_deploy["on"]


def test_backend_deploy_redeploys_when_testdata_changes(backend_deploy):
    paths = backend_deploy["on"]["push"]["paths"]
    assert "backend/**" in paths and "testdata/**" in paths
    assert backend_deploy["on"]["push"]["branches"] == ["master"]


def test_backend_deploy_ships_the_bundle_not_the_checkout(backend_deploy):
    steps = _deploy_steps(backend_deploy)
    build = next(s for s in steps if "build_vercel_bundle.py" in s.get("run", ""))
    deploy = next(s for s in steps if "vercel deploy" in s.get("run", ""))
    assert steps.index(build) < steps.index(deploy)
    assert deploy["working-directory"] == "${{ runner.temp }}/bundle"
    assert "$RUNNER_TEMP/bundle" in build["run"]


def test_backend_deploy_is_health_checked_after_deploying(backend_deploy):
    steps = _deploy_steps(backend_deploy)
    deploy = next(i for i, s in enumerate(steps) if "vercel deploy" in s.get("run", ""))
    health = next(i for i, s in enumerate(steps) if "HEALTH_URL" in s.get("run", ""))
    assert health > deploy
    assert backend_deploy["jobs"]["deploy"]["env"]["HEALTH_URL"].endswith("/health")


def test_backend_deploy_has_read_only_token_permissions(backend_deploy):
    assert backend_deploy["permissions"] == {"contents": "read"}
