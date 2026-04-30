# SWE-bench Reliability Study: Anonymous Supplementary Material

Anonymous supplementary material for paper under review at NeurIPS 2026.

## Contents

```
src/
  interfaces.py             # Perturbation functions (I0 baseline, I1c paragraph reorder,
                            # P4-generic effective-channel ablation)
  score_full.py             # K=5 baseline + I1c + I1d scoring (Tables 1, 3, 6, 7)
  score_p4.py               # P4-generic K=2 scoring (sign test + Wilcoxon + McNemar)
  build_p4_manifest.py      # Selects n=30 baseline-stable tasks for P4-generic
  prepare_p4_data.py        # Generates P4-perturbed parquet for the agent runner

data/runs/
  full_i0_run{1..5}/preds.json   # 5 identical I0 baseline runs
  full_i1c/preds.json            # I1c paragraph-reorder run (K=1)
  full_i1d/preds.json            # I1d markdown-strip run (K=1)
  full_p4_generic_run{1,2}/preds.json
                                 # P4-generic K=2 on n=30 baseline-5/5 subset.
                                 # Originally planned K=3; one run was aborted
                                 # partway due to compute budget and is not
                                 # included here. The size of the observed
                                 # effect (29/30 tasks degraded, sign test
                                 # p < 1.86e-9) makes the K=3 to K=2 reduction
                                 # inconsequential for the qualitative conclusion.

scored/
  per_run_results.json      # Per-task binary outcomes for the main 7 runs
  summary.json              # Aggregate statistics + I1c/I1d McNemar tests
  checkpoint_report.md      # Auto-generated main-run summary

outputs/
  p4_generic_manifest.json          # 30 selected tasks + selection criteria
  p4_generic_per_run_results.json   # Per-task outcomes for baseline + P4
  p4_generic_summary.json           # Aggregate degradation + sign test +
                                    # Wilcoxon + majority-vote McNemar
  p4_generic_summary.md             # Human-readable version
```

## Reproducing the analysis

Evaluation requires the official SWE-bench harness (Docker).

```bash
# Main 7-run analysis (Tables 1, 3, 6, 7 in the paper)
python src/score_full.py

# P4-generic positive-control analysis (Section 4.6, Appendix A)
python src/score_p4.py
```

The `scored/` and `outputs/` directories already contain pre-computed results
that can be inspected directly without re-running the harness.

## Setup

- Agent: mini-swe-agent v2.2.8
- Model: Claude Sonnet 4.5 via OpenRouter (temperature = 0)
- Benchmark: SWE-bench-Verified, 100 tasks (seed = 42 sample)
- P4-generic uses an n = 30 baseline-5/5 subset selected for full baseline reliability
