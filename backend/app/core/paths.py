"""Where the backend finds the repository's `testdata/` directory.

In a checkout it sits beside `backend/`. The deployed function is built from
`backend/` alone, so the deploy bundle copies it inside (`scripts/build_vercel_bundle.py`).
A copy inside `backend/` wins when present, so a bundle never reaches outside itself.
"""

import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[2]


def testdata_dir(backend: pathlib.Path = BACKEND) -> pathlib.Path:
    bundled = backend / "testdata"
    return bundled if bundled.is_dir() else backend.parent / "testdata"


TESTDATA = testdata_dir()
