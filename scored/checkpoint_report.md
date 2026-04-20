# Full Experiment Checkpoint Report

> Generated after full 7-run experiment (n=100, SWE-bench-Verified)
> Model: openrouter/anthropic/claude-sonnet-4-5 (mini-swe-agent v2.2.8)

---

## Checkpoint Decision: DEAD

**p > 0.15. Interface ablation signal below noise. Reassess design.**

---

## I0 Null Distribution (5 identical runs)

| Run | Resolve Rate |
|-----|-------------|
| run1 | 79.8% |
| run2 | 77.3% |
| run3 | 77.0% |
| run4 | 76.0% |
| run5 | 72.0% |
| **Mean** | **76.4%** |
| **Std** | **2.5 pp** |
| **Noise floor (max-min)** | **7.8 pp** |

### Per-task stability (n=100 tasks)

| Category | Count | % |
|----------|-------|---|
| Always resolved (5/5 runs) | 66 | 66.0% |
| Never resolved (0/5 runs) | 16 | 16.0% |
| Unstable (1-4/5 runs) | 18 | 18.0% |

---

## Interface Ablation Results

| Condition | Resolve Rate | Delta vs MV baseline |
|-----------|-------------|---------------------|
| I0 majority vote (baseline) | 76.0% | -- |
| I1c (paragraph reorder) | 74.0% | -2.0 pp |
| I1d (markdown strip) | 76.0% | +0.0 pp |

---

## McNemar's Test

| Comparison | b (pass->fail) | c (fail->pass) | delta | p-value | Significant? |
|-----------|---------------|---------------|-------|---------|--------------|
| MV vs I1c | 5 | 3 | -2.0 pp | 0.7266 | no |
| MV vs I1d | 4 | 4 | +0.0 pp | 1.0000 | no |

---

## Paper Decision (per decision-log.md checkpoints)

- **Checkpoint 1 (data complete):** All 7 runs finished. I0 noise floor = 7.8 pp. Ablation deltas measured.
- **Checkpoint 2 (statistical test):** DEAD (min p = 0.7266)
- **Checkpoint 3 (paper decision):** p > 0.15. Interface ablation signal below noise. Reassess design.
