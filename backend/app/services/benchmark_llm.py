"""The other half of the benchmark: the full RAG + LLM path.

`benchmark.py` measures the offline rule engine — deterministic, free, and safe
to run from an endpoint. This module measures what actually decides a verdict in
production, which is neither deterministic nor free, and that difference drives
every design choice here.

**Why there is no route for this.** A scored run makes one embedding call and one
classification call per case. At 52 cases that is ~104 API calls against free-tier
keys, so an HTTP endpoint would be a cost amplifier reachable by anyone holding a
session. It is a CLI, it defaults to a dry run, and it refuses to spend without
being told to.

**Why results are cached.** Re-running a benchmark after changing an unrelated
file should cost nothing. The cache is keyed on the message, the language, the
prompt version and the model, so any change that could alter a verdict misses the
cache and the case is scored again. `PROMPT_VERSION` has been stamped on every
classification since #18 precisely so this key is honest.

**Why leakage is checked rather than assumed.** ARCHITECTURE and
AGENT-BUILD-PLAN §00 both say the benchmark corpus must be held out of the
pattern database, or the system is graded on its own notes. Exact-text comparison
is too weak a check: retrieval works on cosine similarity, so a paraphrase of a
corpus case sitting in `scam_patterns` leaks just as effectively as a copy. This
module therefore uses the *same retrieval the pipeline uses* and flags any case
whose nearest pattern is close enough to be effectively the same text. Leaked
cases are reported and excluded from the headline figures rather than quietly
inflating them.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import asdict, dataclass, field

from app.services import llm, rag
from app.services.benchmark import LANGUAGES, load_corpus

#: Models that may legitimately have produced a cached verdict. The provider
#: ladder means the model is not known until after the call — Groq answers
#: unless it errors, then Gemini does — so the cache cannot be keyed on it.
#: Instead the model is stored with the record and checked on read: a verdict
#: from a model this code no longer uses is discarded rather than trusted.
KNOWN_MODELS = frozenset({llm.GROQ_MODEL, llm.GEMINI_MODEL})

#: A retrieved pattern at or above this cosine similarity is, for grading
#: purposes, the same text as the case. Empirically the seeded corpus tops out
#: around 0.77 against unrelated patterns and a true near-duplicate lands above
#: 0.95, so this sits in a wide gap rather than on a boundary.
LEAK_SIMILARITY = 0.95

#: Gitignored. Deleting it costs money, not correctness.
CACHE_PATH = pathlib.Path(__file__).resolve().parents[2] / ".benchmark_cache.json"

#: The last scored run, committed. Written by `scripts/run_llm_benchmark.py
#: --out` and read by the dashboard route — a scored run costs API quota, so the
#: UI reads a result a human deliberately produced rather than triggering one.
#: Lives beside the corpus at the repo root, not under frontend/, for the reason
#: in testdata/README.md and because it must not be statically served: see
#: `load_report`.
REPORT_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "testdata" / "benchmark" / "llm-latest.json"
)

#: Verdicts that count as "this is a scam" when scoring against `label`.
SCAM_VERDICTS = {"suspicious", "high_risk"}


@dataclass(frozen=True)
class LlmLanguageBenchmark:
    """Deliberately mirrors `benchmark.LanguageBenchmark` field-for-field where
    the meaning is the same, so the dashboard can render both halves with one
    component instead of two that drift apart."""

    language: str
    total_cases: int
    scam_cases: int
    benign_cases: int
    scored_cases: int
    leaked_cases: int
    true_positives: int
    false_negatives: int
    false_positives: int
    true_negatives: int
    precision: float | None
    recall: float | None
    missed_cases: list[dict] = field(default_factory=list)
    # Itemised for the same reason as missed_cases, and not an afterthought:
    # ARCHITECTURE accepts over-warning as the safer failure, but "accepted"
    # only means anything if we can name which benign messages trip it. A
    # precision figure alone cannot tell you whether the cost is one odd edge
    # case or every bank alert in the country.
    false_positive_cases: list[dict] = field(default_factory=list)
    leaked_case_ids: list[str] = field(default_factory=list)


def _ratio(numerator: int, denominator: int) -> float | None:
    """Mirrors the offline half deliberately: None rather than 0.0 when
    undefined, because "no cases" and "measured, and terrible" are different
    claims. Defined here rather than imported, since the offline module's copy
    is private and importing across that line would couple the two."""
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _cache_key(text: str, language: str, prompt_version: str) -> str:
    """Deliberately excludes the model — the provider ladder decides that at
    call time, so it cannot go in a key computed beforehand. `_usable` checks it
    on the way out instead."""
    raw = f"{prompt_version}\x1f{language}\x1f{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _usable(record: dict) -> bool:
    """A cached verdict counts only if the prompt and the model that produced it
    are still ones this code would use. Otherwise it is a measurement of a
    system we no longer ship."""
    return (
        record.get("prompt_version") == llm.PROMPT_VERSION
        and record.get("model") in KNOWN_MODELS
    )


def load_cache(path: pathlib.Path = CACHE_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt cache is a performance problem, never a correctness one.
        return {}


def save_cache(cache: dict, path: pathlib.Path = CACHE_PATH) -> None:
    path.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")


def corpus_digest(corpus: list[dict]) -> str:
    """Short fingerprint of the corpus a run was scored against.

    Over case ids and text rather than the raw file, so reformatting the JSONL
    or reordering rows does not read as a content change — the question this
    answers is "were these the same cases?", not "was the file byte-identical?".
    Twelve hex characters: enough to distinguish corpus states in a report
    header, short enough to sit in one without dominating it.
    """
    joined = "\x1f".join(
        f"{case['id']}\x1e{case['text']}" for case in sorted(corpus, key=lambda c: c["id"])
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def load_report(path: pathlib.Path | None = None) -> dict | None:
    """The last committed run, or None if nobody has produced one yet.

    **Why this is a route and not a bundled import.** The obvious way to get a
    committed artifact into a dashboard is to import it at build time, or drop
    it in `frontend/public/`. Both would serve it unauthenticated from a public
    site, and `missed_cases` is a list of messages that evade our detector —
    a map of what to send to get past it. The offline half is already behind
    `get_current_user`; publishing this half statically would make the more
    sensitive of the two the one with no gate at all.

    Reading the file from an authenticated route costs nothing, spends no
    quota, and keeps both halves reachable the same way, so one component can
    render them without caring which is which.
    """
    source = path or REPORT_PATH
    if not source.exists():
        return None
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A malformed artifact must not take the dashboard down with it — the
        # offline half still renders, and the UI says this one is unavailable.
        return None


def classify_case(case: dict, cache: dict) -> dict:
    """One case through the real pipeline. Returns the scored record and mutates
    `cache`. Retrieval always runs — it is the leakage check as well as the
    prompt context, and it is the cheap half."""
    patterns = rag.retrieve_similar_patterns(case["text"], case["language"], pool=llm.BATCH)
    top_similarity = max((p.similarity for p in patterns), default=0.0)

    context = rag.format_context_block(patterns)
    # Probe the cache with the identity the classifier would report. This is
    # done before calling it, so a hit costs nothing, and it means changing
    # PROMPT_VERSION invalidates every entry — which is correct, because the
    # prompt is part of what produced the verdict.
    key = _cache_key(case["text"], case["language"], llm.PROMPT_VERSION)

    if key in cache and _usable(cache[key]):
        record = dict(cache[key])
        record["cached"] = True
    else:
        # Batch pool: a benchmark run must never be the reason a live scan
        # gets rate-limited. It measures the same code path either way.
        classification = llm.classify_message(
            case["text"], case["language"], context, llm.BATCH
        )
        record = {
            "verdict": classification.result["verdict"],
            "risk_score": classification.result["risk_score"],
            "provider": classification.provider,
            "model": classification.model,
            "prompt_version": classification.prompt_version,
        }
        cache[key] = record
        record = dict(record)
        record["cached"] = False

    record["top_similarity"] = round(top_similarity, 4)
    record["leaked"] = top_similarity >= LEAK_SIMILARITY
    return record


def score_language(language: str, results: list[tuple[dict, dict]]) -> LlmLanguageBenchmark:
    """`results` is (case, record) for one language."""
    scored = [(case, rec) for case, rec in results if not rec["leaked"]]
    leaked = [case for case, rec in results if rec["leaked"]]

    tp = fn = fp = tn = 0
    missed: list[dict] = []
    false_positives: list[dict] = []

    for case, record in scored:
        predicted_scam = record["verdict"] in SCAM_VERDICTS
        actually_scam = case["label"] == "scam"

        if actually_scam and predicted_scam:
            tp += 1
        elif actually_scam:
            fn += 1
            # What to fix, not just how bad it is — same rationale as the
            # offline half's missed_cases.
            missed.append(
                {
                    "id": case["id"],
                    "text": case["text"],
                    "verdict": record["verdict"],
                    "risk_score": record["risk_score"],
                    "status": case.get("status"),
                    "note": case.get("note"),
                }
            )
        elif predicted_scam:
            fp += 1
            false_positives.append(
                {
                    "id": case["id"],
                    "text": case["text"],
                    "verdict": record["verdict"],
                    "risk_score": record["risk_score"],
                    "note": case.get("note"),
                }
            )
        else:
            tn += 1

    return LlmLanguageBenchmark(
        language=language,
        total_cases=len(results),
        scam_cases=sum(1 for case, _ in results if case["label"] == "scam"),
        benign_cases=sum(1 for case, _ in results if case["label"] == "benign"),
        scored_cases=len(scored),
        leaked_cases=len(leaked),
        true_positives=tp,
        false_negatives=fn,
        false_positives=fp,
        true_negatives=tn,
        precision=_ratio(tp, tp + fp),
        recall=_ratio(tp, tp + fn),
        missed_cases=missed,
        false_positive_cases=false_positives,
        leaked_case_ids=[case["id"] for case in leaked],
    )


def estimate(cases: list[dict], cache: dict) -> dict:
    """What a run would cost, without spending anything.

    Exact for classification, a lower bound overall: retrieval embeds every case
    whether or not its verdict is cached, because the embedding is also the
    leakage check."""
    keys = [_cache_key(c["text"], c["language"], llm.PROMPT_VERSION) for c in cases]
    uncached = sum(1 for key in keys if key not in cache or not _usable(cache[key]))
    return {
        "cases": len(cases),
        "cached": len(cases) - uncached,
        "classification_calls": uncached,
        "embedding_calls": len(cases),
    }


def run(
    *,
    confirm_cost: bool = False,
    path: pathlib.Path | None = None,
    languages: list[str] | None = None,
    max_calls: int | None = None,
    cache_path: pathlib.Path = CACHE_PATH,
) -> dict:
    """Score the corpus through the real pipeline.

    Defaults to a dry run. `confirm_cost=True` is the deliberate act of spending
    API quota, and `max_calls` bounds it — a runaway benchmark on a free tier is
    a self-inflicted outage of the product itself, since it shares the keys.
    """
    corpus = load_corpus(path)
    cases = [c for c in corpus if not languages or c["language"] in languages]
    cache = load_cache(cache_path)

    if not confirm_cost:
        return {"dry_run": True, "estimate": estimate(cases, cache)}

    budget = estimate(cases, cache)["classification_calls"]
    if max_calls is not None and budget > max_calls:
        raise RuntimeError(
            f"would make {budget} classification calls, limit is {max_calls}. "
            f"Raise max_calls or narrow --languages."
        )

    by_language: dict[str, list[tuple[dict, dict]]] = {}
    api_calls = cache_hits = 0

    try:
        for case in cases:
            record = classify_case(case, cache)
            if record["cached"]:
                cache_hits += 1
            else:
                api_calls += 1
            by_language.setdefault(case["language"], []).append((case, record))
    finally:
        # Persist whatever was earned even if a later case fails, so a crash
        # halfway through does not throw away calls already paid for.
        save_cache(cache, cache_path)

    languages_out = [
        asdict(score_language(code, by_language.get(code, []))) for code in LANGUAGES
    ]
    leaked_total = sum(lang["leaked_cases"] for lang in languages_out)

    return {
        "dry_run": False,
        "languages": languages_out,
        "run": {
            "api_calls": api_calls,
            "cache_hits": cache_hits,
            # Which models actually answered, observed rather than assumed —
            # the ladder may have fallen to Gemini for some cases and not
            # others, and a reader comparing two runs needs to see that.
            "models": sorted(
                {rec["model"] for records in by_language.values() for _, rec in records}
            ),
            "prompt_version": llm.PROMPT_VERSION,
            # What this run was measured against. Without it a committed report
            # goes stale invisibly: cases get added, the numbers keep rendering,
            # and they quietly describe a corpus that no longer exists. A figure
            # silently out of date is worse than none, because it looks
            # maintained.
            #
            # Deliberately not a CI failure. Re-running costs API quota, so
            # blocking the build on every corpus edit would discourage adding
            # cases — the opposite of what the corpus is for. Visible, not
            # blocking.
            "corpus_rows": len(corpus),
            "scored_rows": len(cases),
            "corpus_digest": corpus_digest(corpus),
        },
        "leakage": {
            "leaked_cases": leaked_total,
            "threshold": LEAK_SIMILARITY,
            # Stated rather than implied: a reader seeing precision 0.9 deserves
            # to know whether anything was excluded to get there.
            "held_out": leaked_total == 0,
        },
    }
