"""The trace is a contract, and this is what holds its implementations to it.

`testdata/trace_schema.json` is the specification. `trace.py` produces the
trace and `frontend/src/lib/scanResult.ts` consumes it, and until now nothing
connected the two — the schema moved three times (#68, #79, #94) and stayed
consistent only because the same person edited both sides each time.

Checked in both directions on purpose:

  * A field the backend sends and the client does not declare is invisible
    evidence. The whole point of the trace is that a decision can be reviewed,
    and evidence nobody renders is not reviewable.
  * A field the client declares and the backend never sends is a panel that is
    permanently empty, which reads to a user as "this did not happen".

Same shape as `rule_corpus.jsonl` holding the two rule engines together, and
written before the third implementation exists rather than after it disagrees
(#83 wants the Android client to mirror this).
"""

import json
import pathlib
import re

from app.services import trace as trace_service
from app.services.llm import Classification
from app.services.rag import RetrievedPattern
from app.services.rule_engine import RuleHit

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "testdata" / "trace_schema.json"
SCAN_RESULT_TS = ROOT / "frontend" / "src" / "lib" / "scanResult.ts"

SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
FIELDS = SCHEMA["fields"]


def a_full_trace() -> dict:
    """Every optional branch populated, so the assertions see the widest shape."""
    return trace_service.build_trace(
        [RuleHit(rule_id="otp_share", pattern=r"\bOTP\b", matched_text="OTP")],
        [
            RetrievedPattern(
                pattern_text="Share your OTP",
                category="otp_scam",
                similarity=0.91,
                provenance="agent",
                drafted_by="a1",
            )
        ],
        Classification(result={}, provider="groq", model="llama-3.3-70b-versatile"),
    )


# --- the backend emits what the schema describes ---------------------------


def test_every_required_field_is_emitted():
    trace = a_full_trace()
    for name, spec in FIELDS.items():
        if spec.get("required"):
            assert name in trace, (
                f"trace_schema.json marks '{name}' required and build_trace does "
                f"not emit it"
            )


def test_the_backend_emits_no_field_the_schema_does_not_describe():
    """The direction that catches an addition nobody wrote down. A field in the
    trace and not in the schema is one the client has no reason to know about."""
    trace = a_full_trace()
    undocumented = set(trace) - set(FIELDS)
    assert not undocumented, (
        f"trace.py emits {sorted(undocumented)}, which trace_schema.json does not "
        f"describe. Add it to the schema with a `why` first — if the why cannot "
        f"be written, it probably belongs in a log rather than in a trace."
    )


def test_the_degraded_path_omits_the_model_rather_than_faking_one():
    """Both providers down, offline rules alone. `model` is optional precisely
    for this, and inventing a stamp would credit a call that never happened."""
    trace = trace_service.build_trace([], [], None)

    assert "model" not in trace
    assert not FIELDS["model"].get("required"), (
        "the schema must keep `model` optional, or the degraded path violates it"
    )


def test_nested_shapes_match_the_schema():
    trace = a_full_trace()

    for name in ("offline_rules_fired", "retrieved_patterns"):
        described = set(FIELDS[name]["items"])
        for row in trace[name]:
            assert set(row) == described, (
                f"{name} rows are {sorted(row)}, schema says {sorted(described)}"
            )

    described = {
        k for k, v in FIELDS["retrieval"]["properties"].items()
        if v.get("required", True)
    }
    assert described <= set(trace["retrieval"])


def test_the_cached_trace_conforms_too():
    """The cache path builds its trace separately, so it can drift separately."""
    trace = trace_service.build_trace_from_cache([], "groq", "llama", None)

    undocumented = set(trace) - set(FIELDS)
    assert not undocumented, f"the cached trace emits undocumented {sorted(undocumented)}"

    for name, spec in FIELDS.items():
        if spec.get("required"):
            assert name in trace, f"the cached trace omits required '{name}'"

    assert trace["retrieval"]["skipped"] == "cache_hit"


# --- and the frontend declares the same thing ------------------------------


def _declared_in_interface(source: str, name: str) -> set[str]:
    body = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.DOTALL)
    assert body, f"could not find `export interface {name}` in scanResult.ts"
    return set(re.findall(r"^\s*(\w+)\??:", body.group(1), re.MULTILINE))


def test_the_frontend_declares_every_trace_field():
    """Source-text rather than a build step, matching how this codebase already
    pins cross-language contracts — `test_agent_control` reads `scan.py`, and
    `SharedStringCoverageTest` reads `strings.xml`. A generator would be more
    rigorous and would also be a build dependency between two stacks that
    deliberately do not have one."""
    declared = _declared_in_interface(SCAN_RESULT_TS.read_text(encoding="utf-8"), "ScanTrace")
    missing = set(FIELDS) - declared

    assert not missing, (
        f"scanResult.ts does not declare {sorted(missing)}. The backend sends it "
        f"and the client cannot render it, so that evidence is invisible — which "
        f"defeats the point of a trace a decision can be reviewed from."
    )


def test_the_frontend_declares_nothing_the_backend_does_not_send():
    declared = _declared_in_interface(SCAN_RESULT_TS.read_text(encoding="utf-8"), "ScanTrace")
    extra = declared - set(FIELDS)

    assert not extra, (
        f"scanResult.ts declares {sorted(extra)}, which the backend never sends. "
        f"A field the client renders and the server does not populate is a "
        f"permanently empty panel, and a user reads that as 'this did not happen'."
    )


#: Schema field -> the TypeScript interface that declares its inner shape.
#:
#: In the test rather than the schema so the contract file stays about the
#: contract. `test_every_nested_shape_has_a_typescript_interface` stops it
#: drifting in the direction that matters: a new object field with nowhere
#: named to check it.
NESTED_INTERFACES = {
    "rule_review": "RuleReview",
    "retrieval": "RetrievalCoverage",
    "model": "ModelStamp",
    "audit": "AuditRecord",
    "offline_rules_fired": "OfflineRuleHit",
    "retrieved_patterns": "RetrievedPattern",
    "link_signals": "LinkSignals",
    "sender": "SenderCheck",
}


def _nested_shape(spec: dict) -> dict | None:
    return spec.get("properties") or spec.get("items")


def test_every_nested_shape_has_a_typescript_interface():
    for name, spec in FIELDS.items():
        if _nested_shape(spec) is not None:
            assert name in NESTED_INTERFACES, (
                f"'{name}' has an inner shape and no TypeScript interface is "
                f"named for it, so nothing checks the client declares it"
            )


def test_the_frontend_declares_every_nested_field():
    """The direction the top-level check misses.

    `ScanTrace` naming `rule_review` proves the client knows the object exists.
    It proves nothing about the fields *inside* it — and that is where the schema
    actually moves. `reviewed_via`, `code_mixed_reviewed` and `provenance` were
    all added inside an object that was already declared.

    Found by deleting `reviewed_via` from the TypeScript and watching this file
    pass. A guard that only covers the outer layer reads as coverage and is not.
    """
    source = SCAN_RESULT_TS.read_text(encoding="utf-8")
    problems = []

    for name, interface in NESTED_INTERFACES.items():
        described = set(_nested_shape(FIELDS[name]) or {})
        declared = _declared_in_interface(source, interface)

        for missing in sorted(described - declared):
            problems.append(
                f"{interface} does not declare '{missing}' — the backend sends "
                f"it inside {name} and the client cannot render it"
            )
        for extra in sorted(declared - described):
            problems.append(
                f"{interface} declares '{extra}', which trace_schema.json does "
                f"not describe inside {name}"
            )

    assert not problems, "\n".join(problems)


def test_the_schema_uses_one_key_for_a_nested_shape():
    """`properties` and `fields` both appeared for the same idea, inside the
    file whose whole job is stopping two names for one concept."""
    keys = {
        key
        for spec in FIELDS.values()
        for key in ("properties", "fields")
        if key in spec
    }
    assert keys <= {"properties"}, (
        f"nested shapes are described under {sorted(keys)}; use 'properties'"
    )


def test_the_schema_explains_every_optional_field():
    """`optional` is a decision about when a legitimate verdict can lack the
    field. Left unexplained it becomes 'sometimes missing, nobody knows when',
    which is how a UI ends up rendering absence as zero."""
    for name, spec in FIELDS.items():
        if not spec.get("required"):
            assert spec.get("why"), f"'{name}' is optional and the schema does not say when"


def test_every_object_field_describes_its_shape_the_same_way():
    """`rule_review` arrived nesting its sub-shape under `fields` while
    `retrieval`, `model` and `audit` all used `properties` — two names for one
    concept, inside the file whose whole job is stopping that.

    Nothing caught it, because the other assertions read
    `FIELDS["retrieval"]["properties"]` by name rather than checking the schema
    agrees with itself. Raised on #101; added here so the next object field
    cannot pick either.
    """
    objects = {
        name: spec for name, spec in FIELDS.items() if spec.get("type") == "object"
    }
    assert objects, "no object-typed fields — has the schema shape changed?"

    wrong = {
        name: sorted(set(spec) & {"fields", "properties"})
        for name, spec in objects.items()
        if "properties" not in spec
    }
    assert not wrong, (
        f"these object fields do not use `properties` to describe their shape: {wrong}. "
        f"One name for one concept — `properties`, since it is what the rest use and "
        f"the JSON-Schema convention the file already follows."
    )
