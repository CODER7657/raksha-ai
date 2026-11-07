"""Model ids live in exactly one place.

#45 fixed a retired `gemini-1.5-flash` in `llm.py`. It did not fix the identical
literal in `chat.py`, because nothing connected the two — so the scanner got its
fallback back and the chat assistant silently kept running without one.

That is the failure this file exists to prevent. A model id repeated in two
modules is a model id that will be updated in one of them.
"""

import pathlib
import re

import pytest

from app.services import llm

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
LLM_MODULE = APP / "services" / "llm.py"

#: Anything that looks like a provider model id. Deliberately loose — a new
#: provider with a different naming scheme should trip this and be added to the
#: constants rather than quietly slipping through.
MODEL_LITERAL = re.compile(r"[\"'](?:gemini|llama|gpt|claude|mistral|mixtral|whisper)-[\w.-]+[\"']")

#: Prose in a docstring naming a retired model is documentation, not a call.
#: Only executable string literals matter, so comment and docstring lines are
#: excluded by looking for the id inside an assignment or call argument.
SKIP_LINE = re.compile(r"^\s*(#|\*|\"\"\"|'''|[A-Za-z ,.`—-]*(retired|was|used to|see #))")


def python_sources() -> list[pathlib.Path]:
    return [p for p in APP.rglob("*.py") if p != LLM_MODULE]


@pytest.mark.parametrize("path", python_sources(), ids=lambda p: p.name)
def test_no_module_hardcodes_a_model_id(path: pathlib.Path):
    offenders = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if SKIP_LINE.match(line):
            continue
        if MODEL_LITERAL.search(line):
            offenders.append(f"{path.name}:{number}: {line.strip()}")

    assert not offenders, (
        "model ids belong in app/services/llm.py as GROQ_MODEL / GEMINI_MODEL, "
        "imported from there:\n  " + "\n  ".join(offenders)
    )


def test_the_constants_are_the_ones_everything_imports():
    """A sanity check on the constants themselves, so this file fails loudly if
    someone empties them rather than passing by having nothing to find."""
    assert llm.GROQ_MODEL and llm.GEMINI_MODEL and llm.GROQ_STT_MODEL
    assert not llm.GEMINI_MODEL.endswith("-latest"), (
        "a floating alias moves verdicts underneath a stamped PROMPT_VERSION"
    )
    assert not llm.GROQ_MODEL.endswith("-latest")
