"""
stats_analysis.py
=================
Statistical significance testing and hypothesis validation for Perishable Agentic AI.

Performs:
  1. Welch's t-test (two-sample unequal variance)
  2. Wilcoxon signed-rank test (non-parametric paired test across seeds)
  3. Cohen's d effect size calculation
  4. 95% Bootstrap Confidence Intervals for all metrics
  5. Formatted Markdown and CSV summary tables ready for NeurIPS camera-ready submission.

USAGE
-----
    python stats_analysis.py --checkpoint-dir final_output/ablation/checkpoints \
                             --out-dir final_output/ablation/stats
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from scipy import stats


CONFIG = {
    "seed_key": "trial_id",
    "condition_key": "condition",
}


def load_checkpoints(checkpoint_dir: Path) -> pd.DataFrame:
    files = sorted(checkpoint_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No .json checkpoints found in {checkpoint_dir}")

    rows = []
    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            condition = data.get("condition")
            trial_id = data.get("trial_id")

            if not condition:
                stem = fp.stem.replace("metrics_", "")
                parts = stem.split("_T")
                condition = parts[0] if parts else "Unknown"
                trial_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

            metrics = data.get("final_metrics", data)
            pcr = metrics.get("pcr", metrics.get("PCR", 0.0))
            profit = metrics.get("total_profit", metrics.get("Total Profit", 0.0))
            waste = metrics.get("waste_loss", metrics.get("Waste Loss", 0.0))
            true_net = metrics.get("true_net_profit", metrics.get("True Net Profit", profit - waste))
            items_sold = metrics.get("items_sold", metrics.get("Items Sold", 0))

            rows.append({
                "condition": condition,
                "trial_id": trial_id,
                "pcr": float(pcr),
                "total_profit": float(profit),
                "waste_loss": float(waste),
                "true_net_profit": float(true_net),
                "items_sold": int(items_sold),
            })
        except Exception as e:
            print(f"  [WARN] Skipping malformed {fp.name}: {e}", file=sys.stderr)

    return pd.DataFrame(rows)


def cohen_d(x: np.ndarray, y: np.ndarray) -> float:
    """Calculate Cohen's d effect size between two groups."""
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return 0.0
    vx, vy = np.var(x, ddof=1), np.var(y, ddof=1)
    pooled_sd = np.sqrt(((nx - 1) * vx + (ny - 1) * vy) / (nx + ny - 2))
    if pooled_sd == 0:
        return 0.0
    return float((np.mean(x) - np.mean(y)) / pooled_sd)


def bootstrap_ci(arr: np.ndarray, n_boot: int = 2000, ci: float = 0.95) -> tuple[float, float]:
    """Compute 95% bootstrap confidence interval."""
    if len(arr) < 2:
        return (float(arr[0]), float(arr[0])) if len(arr) == 1 else (0.0, 0.0)
    boot_means = [np.mean(np.random.choice(arr, size=len(arr), replace=True)) for _ in range(n_boot)]
    alpha = (1.0 - ci) / 2.0
    low = np.percentile(boot_means, alpha * 100)
    high = np.percentile(boot_means, (1.0 - alpha) * 100)
    return (float(low), float(high))


def run_statistical_analysis(df: pd.DataFrame, out_dir: Path, ref_condition: str = "Full_MAS"):
    out_dir.mkdir(parents=True, exist_ok=True)
    conditions = df["condition"].unique().tolist()
    if ref_condition not in conditions and conditions:
        ref_condition = conditions[0]

    print(f"\n============================================================")
    print(f" STATISTICAL SIGNIFICANCE REPORT (Reference: {ref_condition})")
    print(f"============================================================\n")

    summary_rows = []
    for cond in conditions:
        sub = df[df["condition"] == cond]
        pcr_vals = sub["pcr"].values
        profit_vals = sub["total_profit"].values
        waste_vals = sub["waste_loss"].values
        sold_vals = sub["items_sold"].values

        pcr_ci = bootstrap_ci(pcr_vals)
        profit_ci = bootstrap_ci(profit_vals)

        summary_rows.append({
            "Condition": cond,
            "N": len(sub),
            "PCR_Mean": np.mean(pcr_vals),
            "PCR_Std": np.std(pcr_vals, ddof=1) if len(pcr_vals) > 1 else 0.0,
            "PCR_95_CI": f"[{pcr_ci[0]:.3f}, {pcr_ci[1]:.3f}]",
            "Profit_Mean": np.mean(profit_vals),
            "Profit_Std": np.std(profit_vals, ddof=1) if len(profit_vals) > 1 else 0.0,
            "Profit_95_CI": f"[{profit_ci[0]:.1f}, {profit_ci[1]:.1f}]",
            "Waste_Mean": np.mean(waste_vals),
            "Items_Sold_Mean": np.mean(sold_vals),
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(out_dir / "summary_statistics.csv", index=False)

    # Pairwise hypothesis tests against reference condition
    ref_sub = df[df["condition"] == ref_condition].sort_values("trial_id")
    ref_pcr = ref_sub["pcr"].values
    ref_profit = ref_sub["total_profit"].values

    test_rows = []
    for cond in conditions:
        if cond == ref_condition:
            continue
        sub = df[df["condition"] == cond].sort_values("trial_id")
        pcr_vals = sub["pcr"].values
        profit_vals = sub["total_profit"].values

        # Welch's t-test
        t_pcr, p_welch_pcr = stats.ttest_ind(ref_pcr, pcr_vals, equal_var=False) if len(ref_pcr) > 1 and len(pcr_vals) > 1 else (0.0, 1.0)
        t_prof, p_welch_prof = stats.ttest_ind(ref_profit, profit_vals, equal_var=False) if len(ref_profit) > 1 and len(profit_vals) > 1 else (0.0, 1.0)

        # Wilcoxon signed-rank test
        try:
            w_pcr, p_wilc_pcr = stats.wilcoxon(ref_pcr, pcr_vals) if len(ref_pcr) == len(pcr_vals) and len(ref_pcr) >= 5 else (0.0, 1.0)
        except Exception:
            w_pcr, p_wilc_pcr = (0.0, 1.0)

        # Effect sizes
        d_pcr = cohen_d(ref_pcr, pcr_vals)
        d_prof = cohen_d(ref_profit, profit_vals)

        test_rows.append({
            "Comparison": f"{ref_condition} vs {cond}",
            "Delta_PCR": np.mean(ref_pcr) - np.mean(pcr_vals),
            "Welch_p_PCR": p_welch_pcr,
            "Wilcoxon_p_PCR": p_wilc_pcr,
            "Cohen_d_PCR": d_pcr,
            "Delta_Profit": np.mean(ref_profit) - np.mean(profit_vals),
            "Welch_p_Profit": p_welch_prof,
            "Cohen_d_Profit": d_prof,
        })

    test_df = pd.DataFrame(test_rows)
    test_df.to_csv(out_dir / "hypothesis_tests.csv", index=False)

    # Markdown export for paper
    md_table = "### 📊 Empirical Summary Table ($N$ Trials)\n\n"
    md_table += summary_df.to_markdown(index=False) + "\n\n"
    md_table += "### 🔬 Hypothesis Testing vs " + ref_condition + "\n\n"
    md_table += test_df.to_markdown(index=False) + "\n"

    (out_dir / "paper_table.md").write_text(md_table, encoding="utf-8")
    print(md_table.encode("ascii", "replace").decode("ascii"))
    print(f"\nSaved statistical artifacts to: {out_dir}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("final_output/ablation/checkpoints"))
    parser.add_argument("--out-dir", type=Path, default=Path("final_output/ablation/stats"))
    parser.add_argument("--ref-condition", type=str, default="Full_MAS")
    args = parser.parse_args()

    df = load_checkpoints(args.checkpoint_dir)
    print(f"Loaded {len(df)} trials across {df['condition'].nunique()} conditions.")
    run_statistical_analysis(df, args.out_dir, args.ref_condition)


if __name__ == "__main__":
    main()
