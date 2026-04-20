# SWE-bench Reliability Study: Anonymous Supplementary Material

Anonymous supplementary material for paper under review.

## Contents

```
src/
  score_full.py       # Scoring script: computes per-run rates, McNemar's test, flip attribution
  interfaces.py       # Interface perturbation code (I1c paragraph reorder, I1d markdown strip)

data/runs/
  full_i0_run1/preds.json   # I0 baseline run 1 (n=99 valid patches)
  full_i0_run2/preds.json   # I0 baseline run 2 (n=97 valid patches)
  full_i0_run3/preds.json   # I0 baseline run 3 (n=100 valid patches)
  full_i0_run4/preds.json   # I0 baseline run 4 (n=100 valid patches)
  full_i0_run5/preds.json   # I0 baseline run 5 (n=100 valid patches)
  full_i1c/preds.json       # I1c paragraph-reordered run (n=100 valid patches)
  full_i1d/preds.json       # I1d markdown-stripped run (n=100 valid patches)

scored/
  per_run_results.json      # Per-task binary outcomes for all 7 runs
  summary.json              # Aggregate statistics and McNemar test results
  checkpoint_report.md      # Auto-generated checkpoint report
```

## Reproducing the analysis

Evaluation requires the official SWE-bench harness (Docker). To re-score from patches:

```bash
# Score all runs and reproduce Table 1-6 + McNemar results
python src/score_full.py
```

The `scored/` directory already contains pre-computed results that can be inspected directly without re-running the harness.

## Agent and model

- Agent: mini-swe-agent v2.2.8
- Model: Claude Sonnet 4.5 via OpenRouter (temperature=0)
- Benchmark: SWE-bench-Verified, 100 tasks (seed=42 sample)
