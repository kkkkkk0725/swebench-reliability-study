"""Build manifest for P4-generic K=3 run.

Selects up to N tasks ranked by baseline strength (5/5 > 4/5), with repo
diversity within each tier.

Usage:
    python -m src.build_p4_manifest --n 30
    python -m src.build_p4_manifest --n 23
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
TASKS_FILE = ROOT / "data" / "swebench_full.jsonl"
BASELINE_FILE = ROOT / "outputs" / "mini" / "full_scored" / "per_run_results.json"
BASELINE_RUNS = ["i0_run1", "i0_run2", "i0_run3", "i0_run4", "i0_run5"]

P4_GENERIC_TEXT = "There is a bug in this repository. Identify and fix it so the tests pass."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="Target number of tasks")
    ap.add_argument("--out", type=str, default="outputs/p4_generic_manifest.json")
    args = ap.parse_args()

    # Load baseline counts
    d = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    all_ids = set()
    for r in BASELINE_RUNS:
        all_ids.update(d[r].keys())
    baseline_count = {iid: sum(d[r].get(iid, 0) for r in BASELINE_RUNS) for iid in all_ids}

    # Load task texts (for hashing + repo)
    tasks_by_id = {}
    with TASKS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line)
            tasks_by_id[t["instance_id"]] = t

    # Select strongest candidates with repo diversity
    candidates = []
    for iid, bc in baseline_count.items():
        if iid not in tasks_by_id:
            continue
        if bc < 4:
            continue
        candidates.append({
            "instance_id": iid,
            "repo": tasks_by_id[iid]["repo"],
            "baseline_success_count": bc,
            "baseline_success_rate": round(bc / 5, 3),
        })

    # Tier-based ordering with repo diversity round-robin within tier
    candidates.sort(key=lambda c: (-c["baseline_success_count"], c["repo"], c["instance_id"]))

    by_tier = {5: [], 4: []}
    for c in candidates:
        by_tier[c["baseline_success_count"]].append(c)

    selected = []

    def round_robin(pool: list[dict]) -> list[dict]:
        """Interleave by repo to maximize diversity."""
        from collections import defaultdict, deque
        by_repo = defaultdict(deque)
        for c in pool:
            by_repo[c["repo"]].append(c)
        out = []
        repo_keys = sorted(by_repo.keys(), key=lambda r: -len(by_repo[r]))
        while any(by_repo[r] for r in repo_keys):
            for r in repo_keys:
                if by_repo[r]:
                    out.append(by_repo[r].popleft())
        return out

    # Tier 5/5 first, repo-interleaved
    for c in round_robin(by_tier[5]):
        if len(selected) >= args.n:
            break
        selected.append(c)
    if len(selected) < args.n:
        for c in round_robin(by_tier[4]):
            if len(selected) >= args.n:
                break
            selected.append(c)

    # Build full manifest entries
    tasks_out = []
    for c in selected:
        t = tasks_by_id[c["instance_id"]]
        original = t["problem_statement"]
        tasks_out.append({
            "instance_id": c["instance_id"],
            "repo": c["repo"],
            "baseline_success_count": c["baseline_success_count"],
            "baseline_success_rate": c["baseline_success_rate"],
            "selected_condition": "P4-generic",
            "original_problem_statement_hash": hashlib.sha256(original.encode("utf-8")).hexdigest()[:16],
            "p4_problem_statement_hash": hashlib.sha256(P4_GENERIC_TEXT.encode("utf-8")).hexdigest()[:16],
            "original_length": len(original),
            "p4_length": len(P4_GENERIC_TEXT),
        })

    # Repo distribution
    repo_dist: dict[str, int] = {}
    for t in tasks_out:
        repo_dist[t["repo"]] = repo_dist.get(t["repo"], 0) + 1

    # Bucket distribution
    bucket_dist = {"5/5": 0, "4/5": 0}
    for t in tasks_out:
        bucket_dist[f"{t['baseline_success_count']}/5"] += 1

    manifest = {
        "generated": "2026-04-25",
        "purpose": (
            "P4-generic K=3 positive control. Replaces entire problem_statement "
            "with a generic 'fix the bug' prompt to test whether the written "
            "issue channel is part of the agent's effective observation channel."
        ),
        "protocol": {
            "perturbation": "P4-generic: replace problem_statement with generic prompt",
            "replacement_text": P4_GENERIC_TEXT,
            "n_tasks": len(tasks_out),
            "k_repeats": 3,
            "total_calls": len(tasks_out) * 3,
            "estimated_cost_usd_at_057": round(len(tasks_out) * 3 * 0.57, 2),
            "estimated_cost_usd_at_114": round(len(tasks_out) * 3 * 1.14, 2),
        },
        "selection_rule": (
            "All baseline 5/5 with repo round-robin diversity, then 4/5 if needed. "
            f"Target n={args.n}."
        ),
        "bucket_distribution": bucket_dist,
        "repo_distribution": dict(sorted(repo_dist.items(), key=lambda x: -x[1])),
        "analysis_plan": {
            "primary": "task-level sign test on per-task deltas (baseline_rate - p4_rate)",
            "secondary": "Wilcoxon signed-rank on nonzero deltas",
            "do_not_use": "run-level paired McNemar (run_i pairing not valid)",
        },
        "tasks": tasks_out,
    }

    out_path = ROOT / args.out
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Selected {len(tasks_out)} tasks; bucket: {bucket_dist}")
    print(f"Estimated cost: ${manifest['protocol']['estimated_cost_usd_at_057']:.2f} (at $0.57/call) "
          f"or ${manifest['protocol']['estimated_cost_usd_at_114']:.2f} (at $1.14/call)")
    print()
    print("Repo distribution:")
    for r, n in manifest["repo_distribution"].items():
        print(f"  {r}: {n}")


if __name__ == "__main__":
    main()
