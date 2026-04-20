"""Score all 7 full-experiment runs + compute noise floor + McNemar's test.

Runs:
  I0 x5: full_i0_run1 .. full_i0_run5  (null distribution)
  I1c x1: full_i1c                      (paragraph reorder)
  I1d x1: full_i1d                      (markdown strip)

Outputs:
  outputs/mini/full_scored/per_run_results.json   -- per-task binary outcomes
  outputs/mini/full_scored/summary.json           -- resolve rates, noise floor, McNemar
  outputs/mini/full_scored/checkpoint_report.md   -- paper checkpoint report
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Harness helpers
# ---------------------------------------------------------------------------

def preds_to_jsonl(preds_path: Path, out_path: Path, model_tag: str) -> list[str]:
    """Convert preds.json -> JSONL for swebench harness. Returns list of instance_ids."""
    with preds_path.open("r", encoding="utf-8") as f:
        preds = json.load(f)
    instance_ids = []
    with out_path.open("w", encoding="utf-8") as f:
        for iid, rec in preds.items():
            if not rec.get("model_patch"):
                continue
            f.write(json.dumps({
                "instance_id": iid,
                "model_patch": rec["model_patch"],
                "model_name_or_path": model_tag,
            }) + "\n")
            instance_ids.append(iid)
    return instance_ids


def run_harness(pred_file: Path, run_id: str, max_workers: int = 2, timeout: int = 1200) -> int:
    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", "princeton-nlp/SWE-bench_Verified",
        "--predictions_path", str(pred_file),
        "--run_id", run_id,
        "--max_workers", str(max_workers),
        "--timeout", str(timeout),
    ]
    print(f"\n>>> {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, check=False).returncode


def parse_reports(run_id: str, model_tag: str, instance_ids: list[str]) -> dict[str, bool]:
    """Returns {instance_id: resolved_bool}."""
    logs_dir = Path("logs/run_evaluation") / run_id / model_tag.replace("/", "__")
    results: dict[str, bool] = {}
    for iid in instance_ids:
        report_path = logs_dir / iid / "report.json"
        if not report_path.exists():
            results[iid] = False
            continue
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            instance_report = data.get(iid, {})
            # Resolved = all FAIL_TO_PASS tests now pass
            f2p = instance_report.get("tests_status", {}).get("FAIL_TO_PASS", {})
            resolved = bool(f2p.get("success")) and not f2p.get("failure")
            results[iid] = resolved
        except Exception as e:
            print(f"  WARN: {report_path}: {e}", file=sys.stderr)
            results[iid] = False
    return results


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def resolve_rate(outcomes: dict[str, bool]) -> float:
    if not outcomes:
        return 0.0
    return sum(outcomes.values()) / len(outcomes) * 100


def majority_vote(runs: list[dict[str, bool]], task_ids: list[str]) -> dict[str, bool]:
    """For each task, return True if resolved in majority of runs."""
    result = {}
    for iid in task_ids:
        votes = [r.get(iid, False) for r in runs]
        result[iid] = sum(votes) > len(votes) / 2
    return result


def mcnemar_test(baseline: dict[str, bool], treatment: dict[str, bool]) -> dict:
    """McNemar's test: baseline vs treatment on shared tasks.
    Returns b (baseline pass, treatment fail), c (baseline fail, treatment pass), p-value.
    """
    import math
    common = sorted(set(baseline) & set(treatment))
    b = sum(1 for iid in common if baseline[iid] and not treatment[iid])  # pass->fail
    c = sum(1 for iid in common if not baseline[iid] and treatment[iid])  # fail->pass
    n_discordant = b + c
    # McNemar's exact (sign test) p-value for small counts, chi-sq for large
    if n_discordant == 0:
        p_value = 1.0
        statistic = 0.0
    elif n_discordant < 25:
        # Exact binomial: P(X <= min(b,c)) * 2, X ~ Binomial(n, 0.5)
        def binom_cdf(k, n):
            p = 0.0
            coef = 1.0
            for i in range(k + 1):
                if i > 0:
                    coef *= (n - i + 1) / i
                p += coef * (0.5 ** n)
            return p
        p_value = min(1.0, 2 * binom_cdf(min(b, c), n_discordant))
        statistic = None
    else:
        # Chi-squared with continuity correction
        statistic = (abs(b - c) - 1) ** 2 / (b + c)
        # chi2 CDF approximation (1 df)
        def chi2_sf(x):
            return 1 - math.erf(math.sqrt(x / 2))
        p_value = chi2_sf(statistic)

    delta_pp = resolve_rate(treatment) - resolve_rate(baseline)
    return {
        "n_common": len(common),
        "b_pass_fail": b,
        "c_fail_pass": c,
        "n_discordant": n_discordant,
        "delta_pp": round(delta_pp, 2),
        "p_value": round(p_value, 4),
        "significant_p05": p_value < 0.05,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--skip-harness", action="store_true", help="Skip harness, parse existing reports")
    args = ap.parse_args()

    base = Path("outputs/mini")
    scored_dir = base / "full_scored"
    scored_dir.mkdir(parents=True, exist_ok=True)

    runs_config = [
        ("i0_run1", base / "full_i0_run1/preds.json", "ob1-full-i0r1"),
        ("i0_run2", base / "full_i0_run2/preds.json", "ob1-full-i0r2"),
        ("i0_run3", base / "full_i0_run3/preds.json", "ob1-full-i0r3"),
        ("i0_run4", base / "full_i0_run4/preds.json", "ob1-full-i0r4"),
        ("i0_run5", base / "full_i0_run5/preds.json", "ob1-full-i0r5"),
        ("i1c",     base / "full_i1c/preds.json",     "ob1-full-i1c"),
        ("i1d",     base / "full_i1d/preds.json",     "ob1-full-i1d"),
    ]

    # Step 1: Convert + run harness
    jsonl_dir = scored_dir / "jsonl"
    jsonl_dir.mkdir(exist_ok=True)

    all_instance_ids: dict[str, list[str]] = {}
    for run_name, preds_path, model_tag in runs_config:
        jsonl_path = jsonl_dir / f"{run_name}.jsonl"
        ids = preds_to_jsonl(preds_path, jsonl_path, model_tag)
        all_instance_ids[run_name] = ids
        print(f"{run_name}: {len(ids)} predictions -> {jsonl_path}")

    if not args.skip_harness:
        for run_name, _, model_tag in runs_config:
            print(f"\n=== Scoring {run_name} ===", flush=True)
            jsonl_path = jsonl_dir / f"{run_name}.jsonl"
            run_harness(jsonl_path, f"full_{run_name}", args.max_workers, args.timeout)
    else:
        print("Skipping harness (--skip-harness), parsing existing reports...")

    # Step 2: Parse reports
    print("\n=== Parsing reports ===")
    outcomes: dict[str, dict[str, bool]] = {}
    for run_name, _, model_tag in runs_config:
        outcomes[run_name] = parse_reports(
            f"full_{run_name}", model_tag, all_instance_ids[run_name]
        )
        rr = resolve_rate(outcomes[run_name])
        resolved = sum(outcomes[run_name].values())
        total = len(outcomes[run_name])
        print(f"  {run_name}: {resolved}/{total} = {rr:.1f}%")

    # Step 3: Noise floor analysis (I0 runs)
    i0_names = ["i0_run1", "i0_run2", "i0_run3", "i0_run4", "i0_run5"]
    i0_runs = [outcomes[n] for n in i0_names]
    i0_rates = [resolve_rate(r) for r in i0_runs]

    all_task_ids = sorted(set().union(*[set(r.keys()) for r in i0_runs]))

    noise_floor = max(i0_rates) - min(i0_rates)
    mean_rate = sum(i0_rates) / len(i0_rates)
    variance = sum((r - mean_rate) ** 2 for r in i0_rates) / len(i0_rates)
    std_rate = variance ** 0.5

    # Per-task flip count across 5 I0 runs
    flip_counts = {}
    for iid in all_task_ids:
        outcomes_list = [r.get(iid, False) for r in i0_runs]
        n_resolved = sum(outcomes_list)
        flip_counts[iid] = n_resolved  # 0=never resolved, 5=always resolved, 1-4=sometimes
    unstable = {iid: c for iid, c in flip_counts.items() if 0 < c < 5}
    always_resolved = {iid for iid, c in flip_counts.items() if c == 5}
    never_resolved = {iid for iid, c in flip_counts.items() if c == 0}

    print(f"\n=== I0 Noise Floor ===")
    for i, (name, rate) in enumerate(zip(i0_names, i0_rates)):
        print(f"  {name}: {rate:.1f}%")
    print(f"  Mean: {mean_rate:.1f}%  Std: {std_rate:.1f}pp  Noise floor (max-min): {noise_floor:.1f}pp")
    print(f"  Tasks always resolved (5/5): {len(always_resolved)}")
    print(f"  Tasks never resolved  (0/5): {len(never_resolved)}")
    print(f"  Tasks unstable (1-4/5):      {len(unstable)}")
    print(f"  Instability rate: {len(unstable)/len(all_task_ids)*100:.1f}%")

    # Step 4: McNemar's test (majority vote baseline vs I1c, I1d)
    mv_baseline = majority_vote(i0_runs, all_task_ids)
    mv_rate = resolve_rate(mv_baseline)
    print(f"\n=== Majority Vote Baseline ===")
    print(f"  Resolved: {sum(mv_baseline.values())}/{len(mv_baseline)} = {mv_rate:.1f}%")

    print(f"\n=== McNemar's Tests ===")
    mcnemar_i1c = mcnemar_test(mv_baseline, outcomes["i1c"])
    mcnemar_i1d = mcnemar_test(mv_baseline, outcomes["i1d"])

    for name, mc in [("I1c", mcnemar_i1c), ("I1d", mcnemar_i1d)]:
        sig = "SIGNIFICANT" if mc["significant_p05"] else "not significant"
        print(f"  {name}: delta={mc['delta_pp']:+.1f}pp  b={mc['b_pass_fail']} c={mc['c_fail_pass']}  p={mc['p_value']:.4f} ({sig})")

    # Step 5: Save JSON summary
    summary = {
        "i0_resolve_rates": {n: round(r, 2) for n, r in zip(i0_names, i0_rates)},
        "i0_mean_pp": round(mean_rate, 2),
        "i0_std_pp": round(std_rate, 2),
        "i0_noise_floor_pp": round(noise_floor, 2),
        "n_tasks": len(all_task_ids),
        "n_always_resolved": len(always_resolved),
        "n_never_resolved": len(never_resolved),
        "n_unstable": len(unstable),
        "instability_rate_pct": round(len(unstable) / len(all_task_ids) * 100, 1),
        "majority_vote_rate_pp": round(mv_rate, 2),
        "i1c_resolve_rate_pp": round(resolve_rate(outcomes["i1c"]), 2),
        "i1d_resolve_rate_pp": round(resolve_rate(outcomes["i1d"]), 2),
        "mcnemar_i1c": mcnemar_i1c,
        "mcnemar_i1d": mcnemar_i1d,
    }
    (scored_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Per-run outcomes
    (scored_dir / "per_run_results.json").write_text(
        json.dumps({k: {iid: int(v) for iid, v in r.items()} for k, r in outcomes.items()}, indent=2),
        encoding="utf-8"
    )

    # Step 6: Checkpoint report
    i1c_rr = resolve_rate(outcomes["i1c"])
    i1d_rr = resolve_rate(outcomes["i1d"])

    # Checkpoint decision
    p_i1c = mcnemar_i1c["p_value"]
    p_i1d = mcnemar_i1d["p_value"]
    min_p = min(p_i1c, p_i1d)
    if min_p < 0.05:
        checkpoint = "ALIVE"
        checkpoint_desc = "p < 0.05 for at least one ablation. Proceed to paper draft."
    elif min_p < 0.15:
        checkpoint = "AMBIGUOUS"
        checkpoint_desc = "p = 0.05-0.15. Consider I1e contingency or expanding n."
    else:
        checkpoint = "DEAD"
        checkpoint_desc = "p > 0.15. Interface ablation signal below noise. Reassess design."

    report_md = f"""# Full Experiment Checkpoint Report

> Generated after full 7-run experiment (n=100, SWE-bench-Verified)
> Model: openrouter/anthropic/claude-sonnet-4-5 (mini-swe-agent v2.2.8)

---

## Checkpoint Decision: {checkpoint}

**{checkpoint_desc}**

---

## I0 Null Distribution (5 identical runs)

| Run | Resolve Rate |
|-----|-------------|
| run1 | {i0_rates[0]:.1f}% |
| run2 | {i0_rates[1]:.1f}% |
| run3 | {i0_rates[2]:.1f}% |
| run4 | {i0_rates[3]:.1f}% |
| run5 | {i0_rates[4]:.1f}% |
| **Mean** | **{mean_rate:.1f}%** |
| **Std** | **{std_rate:.1f} pp** |
| **Noise floor (max-min)** | **{noise_floor:.1f} pp** |

### Per-task stability (n={len(all_task_ids)} tasks)

| Category | Count | % |
|----------|-------|---|
| Always resolved (5/5 runs) | {len(always_resolved)} | {len(always_resolved)/len(all_task_ids)*100:.1f}% |
| Never resolved (0/5 runs) | {len(never_resolved)} | {len(never_resolved)/len(all_task_ids)*100:.1f}% |
| Unstable (1-4/5 runs) | {len(unstable)} | {len(unstable)/len(all_task_ids)*100:.1f}% |

---

## Interface Ablation Results

| Condition | Resolve Rate | Delta vs MV baseline |
|-----------|-------------|---------------------|
| I0 majority vote (baseline) | {mv_rate:.1f}% | -- |
| I1c (paragraph reorder) | {i1c_rr:.1f}% | {mcnemar_i1c['delta_pp']:+.1f} pp |
| I1d (markdown strip) | {i1d_rr:.1f}% | {mcnemar_i1d['delta_pp']:+.1f} pp |

---

## McNemar's Test

| Comparison | b (pass->fail) | c (fail->pass) | delta | p-value | Significant? |
|-----------|---------------|---------------|-------|---------|--------------|
| MV vs I1c | {mcnemar_i1c['b_pass_fail']} | {mcnemar_i1c['c_fail_pass']} | {mcnemar_i1c['delta_pp']:+.1f} pp | {mcnemar_i1c['p_value']:.4f} | {'YES' if mcnemar_i1c['significant_p05'] else 'no'} |
| MV vs I1d | {mcnemar_i1d['b_pass_fail']} | {mcnemar_i1d['c_fail_pass']} | {mcnemar_i1d['delta_pp']:+.1f} pp | {mcnemar_i1d['p_value']:.4f} | {'YES' if mcnemar_i1d['significant_p05'] else 'no'} |

---

## Paper Decision (per decision-log.md checkpoints)

- **Checkpoint 1 (data complete):** All 7 runs finished. I0 noise floor = {noise_floor:.1f} pp. Ablation deltas measured.
- **Checkpoint 2 (statistical test):** {checkpoint} (min p = {min_p:.4f})
- **Checkpoint 3 (paper decision):** {checkpoint_desc}
"""

    report_path = scored_dir / "checkpoint_report.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"\n=== Report saved to {report_path} ===")
    print(f"\nCheckpoint: {checkpoint} -- {checkpoint_desc}")


if __name__ == "__main__":
    main()
