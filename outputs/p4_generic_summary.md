# P4-generic K=3 n=30 -- Effective-Channel Ablation

Generated: 2026-04-25

## Aggregate

- Tasks: 30
- Baseline K = 5 (150 calls)
- P4 K = 2 (60 calls)
- Baseline successes: 150/150 = **100.0%**
- P4 successes: 2/60 = **3.33%**
- Aggregate delta: **+96.67 pp**

## Per-task results

| instance_id | baseline | p4 | delta_rate |
|---|---|---|---|
| `django__django-10097` | 5/5 (1.00) | 2/2 (1.00) | +0.00 |
| `sympy__sympy-13480` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `scikit-learn__scikit-learn-10297` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `astropy__astropy-14508` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `pydata__xarray-3305` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `pytest-dev__pytest-10081` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `matplotlib__matplotlib-20859` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `sphinx-doc__sphinx-7889` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `psf__requests-2931` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `django__django-11141` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `sympy__sympy-14531` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `scikit-learn__scikit-learn-13124` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `astropy__astropy-14539` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `pydata__xarray-3677` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `pytest-dev__pytest-7432` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `matplotlib__matplotlib-24970` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `sphinx-doc__sphinx-9230` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `django__django-11149` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `sympy__sympy-14711` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `scikit-learn__scikit-learn-13142` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `astropy__astropy-14995` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `pydata__xarray-4695` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `pytest-dev__pytest-7571` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `django__django-11211` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `sympy__sympy-15017` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `scikit-learn__scikit-learn-13328` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `astropy__astropy-7166` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `django__django-11292` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `sympy__sympy-16450` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |
| `scikit-learn__scikit-learn-14141` | 5/5 (1.00) | 0/2 (0.00) | +1.00 |

- Tasks with delta > 0 (baseline better, degradation): **29**
- Tasks with delta = 0: 1
- Tasks with delta < 0 (P4 better): 0
- Mean delta rate: 0.9667
- Median delta rate: 1.0

## Primary test: sign test on per-task delta signs

- Nonzero pairs: 29
- Positive (degradation): 29
- Negative (improvement): 0
- One-sided p (degradation): **0.0000**
- Two-sided p: **0.0000**

## Secondary test: Wilcoxon signed-rank on nonzero deltas

- Nonzero pairs: 29
- W+ (positive ranks): 435.0
- W- (negative ranks): 0
- z (normal approx): 4.703
- Two-sided p (normal approx): **0.0000**

## Tertiary test: exact McNemar on majority-vote pairs

- Rule: task-level: baseline_count>=3 (5-run majority) vs p4_count>=2 (all P4 runs resolved)
- b (baseline pass, P4 fail): 29
- c (baseline fail, P4 pass): 0
- exact p = **0.0000**

## Framing note

P4-generic uses K=3 perturbation runs per task. Baseline is K=5 from the main experiment. Per-task delta = baseline_rate - p4_rate. Primary test is the sign test on per-task delta signs; Wilcoxon signed-rank uses nonzero delta magnitudes. Run-level paired McNemar is intentionally not performed.
