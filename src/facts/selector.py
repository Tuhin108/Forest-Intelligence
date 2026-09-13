"""
Deterministic, tag-based fact selection. No LLM call happens here or anywhere
in the request path -- this reads the small static facts_bank.json and picks
entries whose tags match conditions derived from the *actual* analysis output
(e.g. "this scene had a lot of overlap flags" -> tag "overlap_high").

If you later want the fuller LLM-curated batch pipeline described in the
brief document (LLM writes -> validation -> dated JSON -> app reads cache),
it's a drop-in replacement for facts_bank.json: same schema, same consumer
interface, nothing else in the app needs to change.
"""
from __future__ import annotations

import json
import os
import random
from typing import Optional

_BANK_PATH = os.path.join(os.path.dirname(__file__), "facts_bank.json")
_bank_cache = None


def _load_bank():
    global _bank_cache
    if _bank_cache is None:
        with open(_BANK_PATH, "r") as f:
            _bank_cache = json.load(f)["facts"]
    return _bank_cache


def derive_tags(metrics) -> set[str]:
    """Turn a ForestMetrics object into a set of context tags."""
    tags = {"general"}
    n = max(metrics.tree_count, 1)
    if metrics.review_flags.get("overlap", 0) / n > 0.25:
        tags.add("overlap_high")
    if metrics.review_flags.get("shadow", 0) / n > 0.20:
        tags.add("shadow_high")
    if metrics.coverage_pct >= 50:
        tags.add("coverage_high")
    else:
        tags.add("coverage_low")
    if metrics.reliability == "LOW":
        tags.add("uncertainty_high")
    return tags


def select_facts(tags: set[str], n: int = 3, seed: Optional[int] = None) -> list[dict]:
    """Pick up to n facts whose tags intersect the given context tags,
    falling back to 'general' facts if nothing more specific matches.
    Deterministic given the same seed, so repeated views of the same
    analysis show the same facts rather than shuffling every rerun."""
    bank = _load_bank()
    matches = [f for f in bank if set(f["tags"]) & tags and set(f["tags"]) != {"general"}]
    general = [f for f in bank if "general" in f["tags"]]

    rng = random.Random(seed)
    pool = matches if matches else general
    rng.shuffle(pool)
    chosen = pool[:n]
    if len(chosen) < n:
        remaining = [f for f in general if f not in chosen]
        rng.shuffle(remaining)
        chosen += remaining[: n - len(chosen)]
    return chosen


def all_categories() -> list[str]:
    bank = _load_bank()
    seen = []
    for f in bank:
        if f["category"] not in seen:
            seen.append(f["category"])
    return seen
