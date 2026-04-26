"""Build data/full_p4_generic/data.parquet for the P4-generic K=3 run.

Reads the manifest selected (default n=30) and writes a parquet with
problem_statement replaced by the P4-generic prompt.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.interfaces import P4_GENERIC_TEXT

ROOT = Path(__file__).parent.parent
TASKS_FILE = ROOT / "data" / "swebench_full.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=str, default="outputs/p4_generic_manifest.json")
    ap.add_argument("--out-dir", type=str, default="data/full_p4_generic")
    args = ap.parse_args()

    manifest = json.loads((ROOT / args.manifest).read_text(encoding="utf-8"))
    selected_ids = {t["instance_id"] for t in manifest["tasks"]}

    rows = []
    with TASKS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d["instance_id"] not in selected_ids:
                continue
            d_perturbed = dict(d)
            d_perturbed["problem_statement"] = P4_GENERIC_TEXT
            rows.append(d_perturbed)

    if len(rows) != len(selected_ids):
        raise RuntimeError(f"Expected {len(selected_ids)} tasks, got {len(rows)}")

    df = pd.DataFrame(rows)
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "data.parquet"
    df.to_parquet(out_path)
    print(f"Wrote {out_path}")
    print(f"Rows: {len(df)}")
    print(f"Replacement length: {len(P4_GENERIC_TEXT)} chars")
    print()
    # Show that all problem_statements are now identical
    unique = df["problem_statement"].nunique()
    print(f"Unique problem_statements: {unique} (should be 1)")
    print(f"Sample: {df.iloc[0]['problem_statement']!r}")


if __name__ == "__main__":
    main()
