"""Score P4-generic K=2 n=30 runs and compute task-level analysis.

Pipeline:
  1. Convert each P4 run's preds.json -> JSONL
  2. Run SWE-bench harness on each
  3. Parse reports -> per-task binary outcomes
  4. Combine with existing K=5 baseline (read from full_scored/per_run_results.json)
  5. Compute per-task baseline_rate, p4_rate, delta = baseline_rate - p4_rate
  6. PRIMARY: sign test on per-task delta signs
  7. SECONDARY: Wilcoxon signed-rank on nonzero deltas
  8. Optional: McNemar on majority-vote collapsed pairs (>=3/5 baseline vs >=2/2 p4)

Important: deliberately does NOT run run-level paired McNemar.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST_FILE = ROOT / "outputs" / "p4_generic_manifest.json"
BASELINE_FILE = ROOT / "outputs" / "mini" / "full_scored" / "per_run_results.json"
OUT_DIR = ROOT / "outputs"
JSONL_DIR = OUT_DIR / "p4_jsonl"

P4_RUNS = [
    ("p4_generic_run1", ROOT / "outputs/mini/full_p4_generic_run1/preds.json", "ob1-full-p4gr1"),
    ("p4_generic_run2", ROOT / "outputs/mini/full_p4_generic_run2/preds.json", "ob1-full-p4gr2"),
    # run3 dropped: OpenRouter credit exhausted mid-run3, only 12/30 patches generated.
    # Including the partial would bias toward earlier-finishing (easier) tasks.
    # ("p4_generic_run3", ROOT / "outputs/mini/full_p4_generic_run3/preds.json", "ob1-full-p4gr3"),
]
BASELINE_RUN_KEYS = ["i0_run1", "i0_run2", "i0_run3", "i0_run4", "i0_run5"]


# ---------------------------------------------------------------------------
# Harness helpers
# ---------------------------------------------------------------------------


def preds_to_jsonl(preds_path: Path, out_path: Path, model_tag: str) -> list[str]:
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


def run_harness(pred_file: Path, run_id: str, max_workers: int = 4, timeout: int = 1200) -> int:
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


def binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    total = 0.0
    coef = 1.0
    q = 1 - p
    for i in range(k + 1):
        if i > 0:
            coef *= (n - i + 1) / i
        total += coef * (p ** i) * (q ** (n - i))
    return total


def sign_test(pos: int, neg: int) -> dict:
    n = pos + neg
    if n == 0:
        return {
            "n_nonzero": 0,
            "pos": pos,
            "neg": neg,
            "p_one_sided_degradation": 1.0,
            "p_two_sided": 1.0,
        }
    p_one = 1 - binom_cdf(pos - 1, n) if pos > 0 else 1.0
    upper = max(pos, neg)
    p_two = min(1.0, 2 * (1 - binom_cdf(upper - 1, n))) if upper > 0 else 1.0
    return {
        "n_nonzero": n,
        "pos": pos,
        "neg": neg,
        "p_one_sided_degradation": round(p_one, 6),
        "p_two_sided": round(p_two, 6),
    }


def wilcoxon_signed_rank(deltas: list[float]) -> dict:
    """Wilcoxon signed-rank on nonzero deltas.

    Uses normal approximation with continuity correction (acceptable for n>=10).
    For smaller n, the p-value is conservative but still informative.
    """
    nonzero = [d for d in deltas if d != 0]
    n = len(nonzero)
    if n == 0:
        return {"n_nonzero": 0, "W": 0.0, "z": 0.0, "p_two_sided": 1.0}

    # Rank by absolute value (with average rank for ties)
    pairs = sorted(enumerate(nonzero), key=lambda p: abs(p[1]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(pairs[j + 1][1]) == abs(pairs[i][1]):
            j += 1
        avg_rank = (i + j + 2) / 2  # 1-indexed average
        for k in range(i, j + 1):
            ranks[pairs[k][0]] = avg_rank
        i = j + 1

    W_pos = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    W_neg = sum(r for r, d in zip(ranks, nonzero) if d < 0)
    W = min(W_pos, W_neg)

    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24
    if var == 0:
        return {"n_nonzero": n, "W": W, "W_pos": W_pos, "W_neg": W_neg,
                "z": 0.0, "p_two_sided": 1.0}
    z = (W_pos - mean) / math.sqrt(var)
    # Two-sided p via normal approximation
    p_two = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {
        "n_nonzero": n,
        "W_pos": round(W_pos, 2),
        "W_neg": round(W_neg, 2),
        "z": round(z, 4),
        "p_two_sided_normal_approx": round(p_two, 6),
    }


def exact_mcnemar(b: int, c: int) -> dict:
    n = b + c
    if n == 0:
        return {"n_discordant": 0, "b_pass_fail": b, "c_fail_pass": c, "p_value": 1.0}
    p_value = min(1.0, 2 * binom_cdf(min(b, c), n))
    return {"n_discordant": n, "b_pass_fail": b, "c_fail_pass": c, "p_value": round(p_value, 6)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--skip-harness", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    task_ids = [t["instance_id"] for t in manifest["tasks"]]
    # Effective K is the number of P4 runs we actually use (P4_RUNS), not the
    # K written in the manifest. Manifest K may be 3 if we planned K=3 but
    # only completed K=2 due to budget exhaustion.
    K_p4 = len(P4_RUNS)
    print(f"P4-generic manifest: {len(task_ids)} tasks, effective K_p4={K_p4} "
          f"(manifest K={manifest['protocol']['k_repeats']})")

    baseline_full = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    baseline_per_run: dict[str, dict[str, int]] = {
        run: {iid: int(baseline_full[run].get(iid, 0)) for iid in task_ids}
        for run in BASELINE_RUN_KEYS
    }
    baseline_count = {iid: sum(baseline_per_run[run][iid] for run in BASELINE_RUN_KEYS)
                      for iid in task_ids}

    JSONL_DIR.mkdir(parents=True, exist_ok=True)
    p4_instance_ids: dict[str, list[str]] = {}
    for run_name, preds_path, model_tag in P4_RUNS:
        if not preds_path.exists():
            print(f"  WARN: {preds_path} missing, skipping {run_name}")
            p4_instance_ids[run_name] = []
            continue
        jsonl_path = JSONL_DIR / f"{run_name}.jsonl"
        ids = preds_to_jsonl(preds_path, jsonl_path, model_tag)
        p4_instance_ids[run_name] = ids
        print(f"  {run_name}: {len(ids)} predictions")

    if not args.skip_harness:
        for run_name, _, _ in P4_RUNS:
            jsonl_path = JSONL_DIR / f"{run_name}.jsonl"
            if not jsonl_path.exists() or jsonl_path.stat().st_size == 0:
                continue
            print(f"\n=== Harness: {run_name} ===", flush=True)
            run_harness(jsonl_path, f"full_{run_name}", args.max_workers, args.timeout)

    p4_per_run: dict[str, dict[str, int]] = {}
    for run_name, _, model_tag in P4_RUNS:
        outcomes = parse_reports(f"full_{run_name}", model_tag, task_ids)
        p4_per_run[run_name] = {iid: int(outcomes.get(iid, False)) for iid in task_ids}
        resolved = sum(p4_per_run[run_name].values())
        print(f"  {run_name}: {resolved}/{len(task_ids)} resolved")

    p4_count = {iid: sum(p4_per_run[run][iid] for run in p4_per_run) for iid in task_ids}

    # Per-task table + deltas (rate-based)
    per_task = []
    deltas: list[float] = []
    for iid in task_ids:
        bc, pc = baseline_count[iid], p4_count[iid]
        b_rate = bc / 5.0
        p_rate = pc / K_p4
        delta = b_rate - p_rate
        deltas.append(delta)
        per_task.append({
            "instance_id": iid,
            "baseline_count": bc,
            "p4_count": pc,
            "baseline_rate": round(b_rate, 3),
            "p4_rate": round(p_rate, 3),
            "delta_rate": round(delta, 3),
        })

    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    zero = sum(1 for d in deltas if d == 0)
    mean_delta = sum(deltas) / len(deltas) if deltas else 0
    sorted_d = sorted(deltas)
    median_delta = sorted_d[len(sorted_d) // 2] if sorted_d else 0

    sign = sign_test(pos=pos, neg=neg)
    wilcoxon = wilcoxon_signed_rank(deltas)

    # Secondary: McNemar on majority-vote
    # baseline_resolved = bc >= 3 (majority of 5)
    # p4_resolved threshold = ceil(K_p4 / 2 + 1) for strict majority,
    # or "any success" for very small K. We use "consistently resolved" =
    # all P4 runs resolved (unambiguous resolution, robust to K change).
    p4_threshold = K_p4  # all-or-most threshold
    b = sum(1 for r in per_task if r["baseline_count"] >= 3 and r["p4_count"] < p4_threshold)
    c = sum(1 for r in per_task if r["baseline_count"] < 3 and r["p4_count"] >= p4_threshold)
    mcnemar = exact_mcnemar(b, c)

    n_p4_calls = len(task_ids) * K_p4
    n_baseline_calls = len(task_ids) * 5
    total_baseline = sum(baseline_count.values())
    total_p4 = sum(p4_count.values())

    summary = {
        "generated": "2026-04-25",
        "n_tasks": len(task_ids),
        "k_baseline": 5,
        "k_p4": K_p4,
        "total_baseline_successes": total_baseline,
        "total_p4_successes": total_p4,
        "baseline_call_count": n_baseline_calls,
        "p4_call_count": n_p4_calls,
        "baseline_aggregate_rate_pct": round(100 * total_baseline / n_baseline_calls, 2),
        "p4_aggregate_rate_pct": round(100 * total_p4 / n_p4_calls, 2),
        "delta_aggregate_pp": round(
            100 * (total_baseline / n_baseline_calls - total_p4 / n_p4_calls), 2),
        "per_task": per_task,
        "delta_summary": {
            "tasks_with_delta_positive_baseline_better": pos,
            "tasks_with_delta_zero": zero,
            "tasks_with_delta_negative_p4_better": neg,
            "mean_delta_rate": round(mean_delta, 4),
            "median_delta_rate": round(median_delta, 4),
        },
        "primary_sign_test": sign,
        "secondary_wilcoxon_signed_rank": wilcoxon,
        "tertiary_mcnemar_majority_vote": {
            **mcnemar,
            "rule": f"task-level: baseline_count>=3 (5-run majority) vs p4_count>={p4_threshold} (all P4 runs resolved)",
        },
        "framing_note": (
            "P4-generic uses K=3 perturbation runs per task. Baseline is K=5 from the "
            "main experiment. Per-task delta = baseline_rate - p4_rate. Primary test is "
            "the sign test on per-task delta signs; Wilcoxon signed-rank uses nonzero "
            "delta magnitudes. Run-level paired McNemar is intentionally not performed."
        ),
    }

    summary_path = OUT_DIR / "p4_generic_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {summary_path}")

    per_run_path = OUT_DIR / "p4_generic_per_run_results.json"
    per_run_path.write_text(json.dumps({
        "baseline": baseline_per_run,
        "p4_generic": p4_per_run,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {per_run_path}")

    md = _render_markdown(summary)
    md_path = OUT_DIR / "p4_generic_summary.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote {md_path}")

    print()
    print("=" * 60)
    print("P4-generic K=3 n=30 -- Effective-Channel Ablation Results")
    print("=" * 60)
    print(f"Baseline: {total_baseline}/{n_baseline_calls} = {summary['baseline_aggregate_rate_pct']}%")
    print(f"P4:       {total_p4}/{n_p4_calls} = {summary['p4_aggregate_rate_pct']}%")
    print(f"Delta:    {summary['delta_aggregate_pp']:+.2f} pp")
    print(f"Tasks degraded:  {pos}")
    print(f"Tasks unchanged: {zero}")
    print(f"Tasks improved:  {neg}")
    print(f"Sign test  (one-sided degradation): p = {sign['p_one_sided_degradation']:.4f}")
    print(f"Sign test  (two-sided):             p = {sign['p_two_sided']:.4f}")
    print(f"Wilcoxon   (two-sided, normal approx): p = {wilcoxon.get('p_two_sided_normal_approx', 1.0):.4f}")
    print(f"McNemar    (majority-vote, b={mcnemar['b_pass_fail']} c={mcnemar['c_fail_pass']}): p = {mcnemar['p_value']:.4f}")


def _render_markdown(s: dict) -> str:
    lines: list[str] = []
    lines.append("# P4-generic K=3 n=30 -- Effective-Channel Ablation")
    lines.append("")
    lines.append(f"Generated: {s['generated']}")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- Tasks: {s['n_tasks']}")
    lines.append(f"- Baseline K = {s['k_baseline']} ({s['baseline_call_count']} calls)")
    lines.append(f"- P4 K = {s['k_p4']} ({s['p4_call_count']} calls)")
    lines.append(f"- Baseline successes: {s['total_baseline_successes']}/{s['baseline_call_count']} = **{s['baseline_aggregate_rate_pct']}%**")
    lines.append(f"- P4 successes: {s['total_p4_successes']}/{s['p4_call_count']} = **{s['p4_aggregate_rate_pct']}%**")
    lines.append(f"- Aggregate delta: **{s['delta_aggregate_pp']:+.2f} pp**")
    lines.append("")

    lines.append("## Per-task results")
    lines.append("")
    lines.append("| instance_id | baseline | p4 | delta_rate |")
    lines.append("|---|---|---|---|")
    for r in s["per_task"]:
        lines.append(f"| `{r['instance_id']}` | {r['baseline_count']}/5 ({r['baseline_rate']:.2f}) | {r['p4_count']}/{s['k_p4']} ({r['p4_rate']:.2f}) | {r['delta_rate']:+.2f} |")
    lines.append("")
    ds = s["delta_summary"]
    lines.append(f"- Tasks with delta > 0 (baseline better, degradation): **{ds['tasks_with_delta_positive_baseline_better']}**")
    lines.append(f"- Tasks with delta = 0: {ds['tasks_with_delta_zero']}")
    lines.append(f"- Tasks with delta < 0 (P4 better): {ds['tasks_with_delta_negative_p4_better']}")
    lines.append(f"- Mean delta rate: {ds['mean_delta_rate']}")
    lines.append(f"- Median delta rate: {ds['median_delta_rate']}")
    lines.append("")

    lines.append("## Primary test: sign test on per-task delta signs")
    lines.append("")
    sign = s["primary_sign_test"]
    lines.append(f"- Nonzero pairs: {sign['n_nonzero']}")
    lines.append(f"- Positive (degradation): {sign['pos']}")
    lines.append(f"- Negative (improvement): {sign['neg']}")
    lines.append(f"- One-sided p (degradation): **{sign['p_one_sided_degradation']:.4f}**")
    lines.append(f"- Two-sided p: **{sign['p_two_sided']:.4f}**")
    lines.append("")

    lines.append("## Secondary test: Wilcoxon signed-rank on nonzero deltas")
    lines.append("")
    w = s["secondary_wilcoxon_signed_rank"]
    lines.append(f"- Nonzero pairs: {w.get('n_nonzero', 0)}")
    lines.append(f"- W+ (positive ranks): {w.get('W_pos', 0)}")
    lines.append(f"- W- (negative ranks): {w.get('W_neg', 0)}")
    lines.append(f"- z (normal approx): {w.get('z', 0)}")
    lines.append(f"- Two-sided p (normal approx): **{w.get('p_two_sided_normal_approx', 1.0):.4f}**")
    lines.append("")

    lines.append("## Tertiary test: exact McNemar on majority-vote pairs")
    lines.append("")
    mc = s["tertiary_mcnemar_majority_vote"]
    lines.append(f"- Rule: {mc['rule']}")
    lines.append(f"- b (baseline pass, P4 fail): {mc['b_pass_fail']}")
    lines.append(f"- c (baseline fail, P4 pass): {mc['c_fail_pass']}")
    lines.append(f"- exact p = **{mc['p_value']:.4f}**")
    lines.append("")

    lines.append("## Framing note")
    lines.append("")
    lines.append(s["framing_note"])
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
