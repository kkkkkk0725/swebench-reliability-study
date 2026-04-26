"""Interface variants: I0 (baseline) + I1 candidates + P4 positive control.

Design note: this is the SINGLE SOURCE OF TRUTH for what an "evaluation interface" is
in this experiment. Every I0 -> I1 / P4 transformation is expressed as a function here.

Conceptual split:
  - Presentation-side variants change the INPUT to the model (require new inference).
    Currently: i1c_issue_reformat, p4_generic
  - Scoring-side variants change how we EVALUATE the SAME model output.
    Currently: i1a_test_ablation, i1b_parser_leniency

Note: I1d (markdown strip) was applied directly to the issue text outside of this
module; the resulting per-task outputs are in data/runs/full_i1d/preds.json.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IssuePresentation:
    """Everything about how the task is shown to the model."""
    repo: str
    issue_text: str
    code_context: str


def present_issue_i0(task: dict[str, Any]) -> IssuePresentation:
    """Baseline presentation: issue text as-is, code context in canonical order."""
    return IssuePresentation(
        repo=task["repo"],
        issue_text=task["problem_statement"],
        code_context=_build_code_context(task, reverse=False),
    )


P4_GENERIC_TEXT = "There is a bug in this repository. Identify and fix it so the tests pass."


def present_issue_p4_generic(task: dict[str, Any]) -> IssuePresentation:
    """P4-generic: Replace the entire problem_statement with a generic prompt.

    This is an effective-channel ablation, NOT semantics-preserving. It
    removes the written issue channel entirely (no bug description, no
    repro steps, no traceback, no code, no hints). Only repository state
    and the test harness remain available.

    Used to test whether the written issue text is part of the agent's
    effective observation channel.
    """
    return IssuePresentation(
        repo=task["repo"],
        issue_text=P4_GENERIC_TEXT,
        code_context=_build_code_context(task, reverse=False),
    )


def present_issue_i1c_reformat(task: dict[str, Any]) -> IssuePresentation:
    """I1c: reverse paragraph order in issue text. Minimal, unambiguous interface change.

    Handles both LF and CRLF paragraph separators (SWE-bench often uses CRLF).
    Semantics preserved (same paragraphs, same content, same order of sentences within
    paragraph). Only paragraph order changes.
    """
    import re
    normalized = task["problem_statement"].replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p for p in re.split(r"\n\n+", normalized) if p.strip()]
    reversed_text = "\n\n".join(reversed(paragraphs))
    return IssuePresentation(
        repo=task["repo"],
        issue_text=reversed_text,
        code_context=_build_code_context(task, reverse=False),
    )


def _build_code_context(task: dict[str, Any], reverse: bool = False) -> str:
    """Render relevant code files into a single string for prompting.

    Uses retrieval-augmented context: clones the repo, identifies likely
    relevant files from issue / hints text, and returns their contents at the
    task's base_commit.
    """
    from src.repo_context import build_repo_context_for_task
    return build_repo_context_for_task(task)


# =============================================================================
# Scoring-side ablations (applied AFTER model inference)
# =============================================================================


def i1a_test_ablation(
    test_results: dict[str, bool],
    drop_fraction: float,
    seed: int,
) -> dict[str, bool]:
    """Drop a deterministic random subset of tests, return remaining test results.

    test_results: {test_name: passed?}
    returns: {test_name: passed?} with subset dropped.

    Reproducibility: seeded by (instance_id, drop_fraction, seed). Caller must pass
    a seed derived from instance_id for per-task determinism.
    """
    if not test_results:
        return {}
    n_drop = int(len(test_results) * drop_fraction)
    if n_drop <= 0:
        return dict(test_results)
    rng = random.Random(seed)
    all_tests = sorted(test_results.keys())
    to_drop = set(rng.sample(all_tests, n_drop))
    return {t: r for t, r in test_results.items() if t not in to_drop}


def resolve_rate(test_results: dict[str, bool], required_tests: set[str] | None = None) -> bool:
    """A task is 'resolved' iff all required tests pass.

    If required_tests is None, use all tests in test_results.
    Missing tests (in required but not in results) count as failures.
    """
    if required_tests is None:
        required_tests = set(test_results.keys())
    if not required_tests:
        return False
    for t in required_tests:
        if not test_results.get(t, False):
            return False
    return True
