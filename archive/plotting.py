"""
plotting.py
===========
Publication-grade vector figures for the Perishable Agentic AI paper.

Generates three figures as separate PDF + SVG files (vector, not raster --
required by most NeurIPS/ICML/AAMAS camera-ready pipelines):

  Figure 1 -- Dynamic Yield Curves
      Price decay trajectory over time (T=0..10) for MAS vs. LinearDecay,
      per item or averaged across the catalog.

  Figure 2 -- Inventory Survival Curves
      % of unsold inventory remaining over time, one line per condition,
      Kaplan-Meier-style step curve.

  Figure 3 -- PCR / Net Profit Boxplots
      Boxplots (with individual trial points overlaid) comparing Profit
      Capture Ratio and True Net Profit across all conditions.

USAGE
-----
    python plotting.py --checkpoint-dir final_output/ablation/checkpoints \
                        --out-dir final_output/ablation/figures \
                        --conditions Full_MAS LinearDecay_Baseline No_RiskReader No_StrategicBrain
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# --------------------------------------------------------------------------
# CONFIG -- matches ablation_study.py checkpoint JSON structure.
# --------------------------------------------------------------------------
CONFIG = {
    "condition_key": "condition",
    "trial_id_key": "trial_id",
    "metrics_container_key": "final_metrics",
    "price_trajectory_key": "price_trajectory",       # list of {hour, item, price}
    "inventory_trajectory_key": "inventory_trajectory", # list of {hour, pct_unsold}
}

CONDITION_STYLE = {
    "Full_MAS": {"label": "Full MAS (Ours)", "color": "#2C7BB6", "linestyle": "-"},
    "LinearDecay_Baseline": {"label": "Linear Decay (OR Baseline)", "color": "#D7191C", "linestyle": "--"},
    "No_RiskReader": {"label": "No RiskReader (Ablated)", "color": "#FDAE61", "linestyle": "-."},
    "No_StrategicBrain": {"label": "No StrategicBrain (Ablated)", "color": "#ABD9E9", "linestyle": "-."},
    "SINGLE_MODEL": {"label": "Single Monolithic LLM", "color": "#808080", "linestyle": ":"},
}
DEFAULT_STYLE = {"color": "#333333", "linestyle": "-"}


def style_for(cond: str) -> dict:
    s = CONDITION_STYLE.get(cond, DEFAULT_STYLE)
    return {"label": s.get("label", cond), "color": s["color"], "linestyle": s.get("linestyle", "-")}


def set_pub_style():
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.3)
    plt.rcParams.update({
        "font.family": "serif",
        "svg.fonttype": "none",   # keep text editable in vector output
        "pdf.fonttype": 42,       # embed as TrueType, not Type 3 (journal requirement)
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
    })


def load_all(checkpoint_dir: Path) -> list[dict]:
    files = sorted(checkpoint_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No .json checkpoints found in {checkpoint_dir}")
    out = []
    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            # Normalize legacy flat checkpoints if needed
            if "condition" not in data:
                stem = fp.stem.replace("metrics_", "")
                parts = stem.split("_T")
                data["condition"] = parts[0] if parts else "Unknown"
                data["trial_id"] = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            if "final_metrics" not in data:
                data["final_metrics"] = {
                    "pcr": data.get("PCR", data.get("pcr", 0.0)),
                    "total_profit": data.get("Total Profit", data.get("total_profit", 0.0)),
                    "waste_loss": data.get("Waste Loss", data.get("waste_loss", 0.0)),
                    "true_net_profit": data.get("True Net Profit", data.get("true_net_profit", 0.0)),
                    "items_sold": data.get("Items Sold", data.get("items_sold", 0)),
                }
            out.append(data)
        except json.JSONDecodeError as e:
            print(f"  [WARN] skipping malformed {fp.name}: {e}", file=sys.stderr)
    return out


def save_fig(fig, out_dir: Path, name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.svg", bbox_inches="tight")
    print(f"  wrote {out_dir / (name + '.pdf')} and .svg")


# --------------------------------------------------------------------------
# Figure 1: Dynamic Yield Curves
# --------------------------------------------------------------------------
def figure1_yield_curves(records: list[dict], conditions: list[str], out_dir: Path):
    rows = []
    for rec in records:
        cond = rec.get(CONFIG["condition_key"])
        if cond not in conditions:
            continue
        traj = rec.get(CONFIG["price_trajectory_key"])
        if not traj:
            continue
        trial_id = rec.get(CONFIG["trial_id_key"])
        for point in traj:
            rows.append({
                "condition": cond, "trial_id": trial_id,
                "hour": point["hour"], "price": point["price"], "item": point.get("item", "ALL"),
            })

    if not rows:
        print("  [SKIP] Figure 1: no price_trajectory data found in checkpoints. "
              "Add per-timestep price logging to environment.py to enable this figure.")
        return

    df = pd.DataFrame(rows)
    agg = df.groupby(["condition", "hour"], as_index=False)["price"].agg(["mean", "std"]).reset_index()

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for cond in conditions:
        sub = agg[agg["condition"] == cond].sort_values("hour")
        if sub.empty:
            continue
        s = style_for(cond)
        ax.plot(sub["hour"], sub["mean"], label=s["label"], color=s["color"], linestyle=s["linestyle"], linewidth=2)
        ax.fill_between(sub["hour"], sub["mean"] - sub["std"], sub["mean"] + sub["std"],
                         color=s["color"], alpha=0.15)

    ax.set_xlabel("Time (hours since market open)")
    ax.set_ylabel("Mean asking price ($)")
    ax.set_title("Figure 1: Dynamic Yield Curves")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    save_fig(fig, out_dir, "figure1_yield_curves")
    plt.close(fig)


# --------------------------------------------------------------------------
# Figure 2: Inventory Survival Curves
# --------------------------------------------------------------------------
def figure2_survival_curves(records: list[dict], conditions: list[str], out_dir: Path):
    rows = []
    for rec in records:
        cond = rec.get(CONFIG["condition_key"])
        if cond not in conditions:
            continue
        traj = rec.get(CONFIG["inventory_trajectory_key"])
        if not traj:
            continue
        trial_id = rec.get(CONFIG["trial_id_key"])
        for point in traj:
            rows.append({"condition": cond, "trial_id": trial_id,
                         "hour": point["hour"], "pct_unsold": point["pct_unsold"]})

    if not rows:
        print("  [SKIP] Figure 2: no inventory_trajectory data found in checkpoints. "
              "Add per-timestep inventory logging to environment.py to enable this figure.")
        return

    df = pd.DataFrame(rows)
    agg = df.groupby(["condition", "hour"], as_index=False)["pct_unsold"].agg(["mean", "std"]).reset_index()

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for cond in conditions:
        sub = agg[agg["condition"] == cond].sort_values("hour")
        if sub.empty:
            continue
        s = style_for(cond)
        ax.step(sub["hour"], sub["mean"] * 100, where="post",
                 label=s["label"], color=s["color"], linestyle=s["linestyle"], linewidth=2)
        ax.fill_between(sub["hour"], (sub["mean"] - sub["std"]) * 100, (sub["mean"] + sub["std"]) * 100,
                         step="post", color=s["color"], alpha=0.15)

    ax.set_xlabel("Time (hours since market open)")
    ax.set_ylabel("Unsold inventory (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Figure 2: Inventory Survival Curves")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    save_fig(fig, out_dir, "figure2_survival_curves")
    plt.close(fig)


# --------------------------------------------------------------------------
# Figure 3: PCR / Net Profit Boxplots
# --------------------------------------------------------------------------
def figure3_boxplots(records: list[dict], conditions: list[str], out_dir: Path):
    rows = []
    for rec in records:
        cond = rec.get(CONFIG["condition_key"])
        if cond not in conditions:
            continue
        metrics = rec.get(CONFIG["metrics_container_key"], rec) if CONFIG["metrics_container_key"] else rec
        row = {"condition": cond}
        row.update(metrics)
        rows.append(row)

    if not rows:
        print("  [SKIP] Figure 3: no final_metrics found in checkpoints.")
        return

    df = pd.DataFrame(rows)
    df["condition"] = pd.Categorical(df["condition"], categories=conditions, ordered=True)
    palette = {c: style_for(c)["color"] for c in conditions}

    metric_specs = [("pcr", "Profit Capture Ratio"), ("total_profit", "True Net Profit ($)")]
    available = [(m, lbl) for m, lbl in metric_specs if m in df.columns]
    if not available:
        print("  [SKIP] Figure 3: expected 'pcr'/'total_profit' fields not found -- "
              "check CONFIG['metrics_container_key'] or your final_metrics keys.")
        return

    fig, axes = plt.subplots(1, len(available), figsize=(6.5 * len(available), 4.5))
    if len(available) == 1:
        axes = [axes]

    for ax, (metric, label) in zip(axes, available):
        sns.boxplot(data=df, x="condition", y=metric, hue="condition", palette=palette,
                    ax=ax, width=0.55, showfliers=False, legend=False)
        sns.stripplot(data=df, x="condition", y=metric, ax=ax, color="black",
                      size=3, alpha=0.5, jitter=0.15)
        ax.set_xlabel("")
        ax.set_ylabel(label)
        ax.set_xticks(range(len(conditions)))
        ax.set_xticklabels([style_for(c)["label"] for c in conditions], rotation=25, ha="right")
        if metric == "pcr":
            ax.axhline(1.0, color="gray", linestyle=":", linewidth=1)

    fig.suptitle("Figure 3: PCR and Net Profit Across Conditions")
    fig.tight_layout()
    save_fig(fig, out_dir, "figure3_boxplots")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("final_output/ablation/checkpoints"))
    parser.add_argument("--out-dir", type=Path, default=Path("final_output/ablation/figures"))
    parser.add_argument("--conditions", type=str, nargs="+",
                         default=["Full_MAS", "LinearDecay_Baseline", "No_RiskReader",
                                  "No_StrategicBrain", "SINGLE_MODEL"])
    args = parser.parse_args()

    set_pub_style()
    records = load_all(args.checkpoint_dir)
    print(f"Loaded {len(records)} checkpoint records.")

    print("Generating Figure 1 (yield curves)...")
    figure1_yield_curves(records, args.conditions, args.out_dir)

    print("Generating Figure 2 (survival curves)...")
    figure2_survival_curves(records, args.conditions, args.out_dir)

    print("Generating Figure 3 (boxplots)...")
    figure3_boxplots(records, args.conditions, args.out_dir)


if __name__ == "__main__":
    main()
