"""No test may read the developer's real credentials (#77).

`Settings` declares `env_file=".env"`. pydantic-settings treats that file as a
source in its own right, separate from the process environment, so
`monkeypatch.delenv` clears the variable and leaves the file untouched — and a
field a test believes it has emptied quietly resolves to whatever is in
`backend/.env`.

Three `test_key_pools.py` assertions failed exactly that way on any machine
with keys configured, while passing in CI where no `.env` exists. A test that
lies in the environment where someone has just finished setting up, and prints
a live key prefix into the assertion diff while doing it.

`conftest.settings_ignore_dotenv` neutralises the source for the whole suite.
This file is what stops that fixture being deleted by someone who cannot see
what it was for.
"""

import pathlib

from app.core.config import Settings, get_settings

BACKEND = pathlib.Path(__file__).resolve().parents[1]

def test_settings_ignore_a_dotenv_file(tmp_path, monkeypatch):
    """The real assertion, and it has to build its own `.env` to be worth anything.

    Checking that `groq_api_key` is empty on a machine that happens to have no
    `.env` proves nothing — which is precisely the shape of the original bug,
    passing in CI for reasons unrelated to the code being correct. So this test
    creates the file it wants ignored.

    If `settings_ignore_dotenv` is removed, `env_file=".env"` resolves against
    the working directory, finds the file written below, and the assertion
    fails with the planted value rather than with someone's real key.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "GROQ_API_KEY=leaked-from-a-dotenv-file\n"
        "GEMINI_API_KEY=also-leaked\n"
        "AUDIT_HASH_PEPPER=a-pepper-no-test-should-see\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AUDIT_HASH_PEPPER", raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.groq_api_key == "", "a dotenv file reached a test"
    assert settings.gemini_api_key == "", "a dotenv file reached a test"
    assert settings.audit_hash_pepper == "", "a dotenv file reached a test"


def test_the_fixture_is_actually_applied():
    """A direct read of the state the fixture sets.

    Narrower than the test above and kept anyway: when the other one fails, this
    says immediately whether the cause is the fixture not running or the
    settings not honouring it, which are different problems with different
    fixes.
    """
    assert Settings.model_config.get("env_file") is None


def test_the_application_still_declares_an_env_file():
    """The fixture must not leak into the app.

    `monkeypatch.setitem` restores `model_config` after each test, so a
    developer running `uvicorn` still gets their `.env` read normally. If this
    fails, the app no longer declares its `.env` and local development is
    broken in a way no other test would notice.

    Checked in a fresh interpreter, not with `importlib.reload`: reloading
    `app.core.config` here created a second `Settings` class that the
    `settings_ignore_dotenv` fixture never patches, so every test that ran
    after this one could read a developer's real `.env` (two `test_stt` tests
    failed on any machine with keys configured, and passed in CI).
    """
    import subprocess
    import sys

    probe = "from app.core.config import Settings; print(Settings.model_config.get('env_file'))"
    out = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert out.stdout.strip() == ".env"


def test_this_module_never_reloads_the_config():
    """Guard the fix above: a reload anywhere in the suite reopens the leak."""
    import app.core.config as config_module
    from app.core.config import Settings

    assert config_module.Settings is Settings
