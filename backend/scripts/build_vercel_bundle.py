"""Assemble the directory the backend is deployed from.

The function is built from `backend/` alone, but several read-only routes read
the repository's `testdata/` (the labelled corpus, the committed benchmark run,
the review queues). This copies `backend/` without what a deploy must never
carry (tests, local caches, `.env` files) and puts `testdata/` inside it, where
`app.core.paths` looks first.

    python scripts/build_vercel_bundle.py OUT_DIR

OUT_DIR is created. If it already exists it must be a bundle this script made
(it holds a marker file), so a typo cannot delete an unrelated directory.
"""

import argparse
import pathlib
import shutil
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
MARKER = ".raksha-bundle"

#: Never deployed, at any depth. `.env*` above all: the function reads its
#: secrets from the platform, and a stray local key file must not become a
#: public artifact.
EXCLUDE_EVERYWHERE = ["__pycache__", "*.pyc", ".env*", ".pytest_cache", ".ruff_cache"]
#: Never deployed, but only at the top of backend/: a runtime package that
#: happens to be called `scripts` or `tests` deeper down must still ship.
EXCLUDE_AT_ROOT = {
    "tests", "scripts", ".venv", "venv", ".vercel", ".benchmark_cache.json",
    "requirements-dev.txt", "pytest.ini", "ruff.toml",
}
#: Kept, although `.env*` would match it: it holds names, not values.
KEEP = {".env.example"}


def _ignorer(backend: pathlib.Path):
    root = backend.resolve()
    everywhere = shutil.ignore_patterns(*EXCLUDE_EVERYWHERE)

    def ignore(directory: str, names: list[str]) -> set[str]:
        skipped = set(everywhere(directory, names))
        if pathlib.Path(directory).resolve() == root:
            skipped |= EXCLUDE_AT_ROOT & set(names)
        return skipped - KEEP

    return ignore


def build(out: pathlib.Path, backend: pathlib.Path = BACKEND, repo: pathlib.Path = REPO) -> pathlib.Path:
    out = out.resolve()
    testdata = repo / "testdata"
    for source in (backend.resolve(), testdata.resolve()):
        if out == source or source in out.parents or out in source.parents:
            raise ValueError(f"refusing to build into or around a source directory: {out}")
    if out.exists():
        if not (out / MARKER).exists():
            raise ValueError(f"{out} exists and is not a bundle made by this script")
        shutil.rmtree(out)

    shutil.copytree(backend, out, ignore=_ignorer(backend))
    if not testdata.is_dir():
        raise FileNotFoundError(f"no testdata directory at {testdata}")
    shutil.copytree(testdata, out / "testdata", ignore=shutil.ignore_patterns("__pycache__"))
    (out / MARKER).write_text("made by scripts/build_vercel_bundle.py\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        out = build(args.out)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    files = sum(1 for p in out.rglob("*") if p.is_file())
    print(f"bundle: {out} ({files} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
