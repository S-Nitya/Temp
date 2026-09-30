"""
Ablation Study — 4 Conditions

Conditions:
  1. Full_MAS         — Complete system (StrategicBrain + TacticalOrchestrator + RiskReader)
  2. No_RiskReader    — StrategicBrain intact, but RiskReader replaced by DummyRiskReader
  3. No_StrategicBrain — RiskReader intact, but StrategicBrain replaced by DummyStrategicBrain
  4. LinearDecay_Baseline — Pure math OR heuristic (no LLMs for pricing decisions)

Research Question:
  What is the marginal contribution of each agent to Profit Capture Ratio (PCR)?
  Does the MAS outperform traditional OR baselines?

Usage:
  python -m final_architecture.ablation_study --trials 5
  python -m final_architecture.ablation_study --trials 30  (Statistical run)
"""
import asyncio
import pandas as pd
import json
import os
import argparse
import random
from typing import Dict, Any, List

from .environment import AsyncHiveEnvironment
from .agents import DummyRiskReader, DummyStrategicBrain, RiskReader, Spokesperson, TacticalOrchestrator
from .config import FINAL_CONFIG, N_BUYERS, MAX_HOURS, GLOBAL_SEED

CHECKPOINT_DIR = os.path.join("final_output", "ablation", "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

SUMMARY_CSV = os.path.join("final_output", "ablation", "ablation_results.csv")


def save_checkpoint(
    trial: int,
    condition: str,
    metrics: Dict,
    price_traj: List = None,
    inv_traj: List = None,
    neg_log: List = None,
    item_outcomes: Dict = None,
    sales_data: List = None,
):
    path = os.path.join(CHECKPOINT_DIR, f"metrics_{condition}_T{trial}.json")
    payload = {
        "condition": condition,
        "trial_id": trial,
        "final_metrics": {
            "pcr": metrics.get("PCR", 0.0),
            "total_profit": metrics.get("Total Profit", 0.0),
            "waste_loss": metrics.get("Waste Loss", 0.0),
            "true_net_profit": metrics.get("True Net Profit", 0.0),
            "items_sold": metrics.get("Items Sold", 0),
            "instant_clears": metrics.get("Instant Clears", 0),
            "negotiated_sales": metrics.get("Negotiated Sales", 0),
            "instant_clear_rate": metrics.get("Instant Clear Rate", 0.0),
            "negotiated_sale_rate": metrics.get("Negotiated Sale Rate", 0.0),
            "pcr_list": metrics.get("pcr_list", []),
            "persuasion_events": metrics.get("Persuasion Events", 0),
            "iv": metrics.get("IV", 0.0),
            "ee": metrics.get("EE", 0.0),
        },
        "PCR": metrics.get("PCR", 0.0),
        "Total Profit": metrics.get("Total Profit", 0.0),
        "Waste Loss": metrics.get("Waste Loss", 0.0),
        "True Net Profit": metrics.get("True Net Profit", 0.0),
        "Items Sold": metrics.get("Items Sold", 0),
        "Instant Clears": metrics.get("Instant Clears", 0),
        "Negotiated Sales": metrics.get("Negotiated Sales", 0),
        "Instant Clear Rate": metrics.get("Instant Clear Rate", 0.0),
        "Negotiated Sale Rate": metrics.get("Negotiated Sale Rate", 0.0),
        "pcr_list": metrics.get("pcr_list", []),
        "sales_data": sales_data or [],
        "price_trajectory": price_traj or [],
        "inventory_trajectory": inv_traj or [],
        "negotiation_log": neg_log or [],
        "item_outcomes": item_outcomes or {},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def load_checkpoint(trial: int, condition: str) -> Dict | None:
    path = os.path.join(CHECKPOINT_DIR, f"metrics_{condition}_T{trial}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def calculate_metrics(results: Dict) -> Dict[str, Any]:
    sales     = results["blackboard"]["sales_data"]
    inventory = results["blackboard"]["inventory"]
    duration  = results["duration"]

    total_profit = sum(s["sale_price"] - s["cost_price"] for s in sales)
    sold_ids     = {s.get("item_id", s["product_name"]) for s in sales}
    waste_loss   = sum(i["cost_price"] for i in inventory if i.get("item_id", i["product_name"]) not in sold_ids)

    # PCR: per-item profit capture ratio (actual realized margin / base retail potential margin)
    pcr_list = []
    instant_count = 0
    negotiated_count = 0

    for s in sales:
        potential = s["initial_price"] - s["cost_price"]  # retail - cost
        actual    = s["sale_price"]    - s["cost_price"]  # realized - cost
        ratio     = round(actual / potential, 4) if potential > 0 else 0.0
        pcr_list.append(ratio)

        if s.get("clearance_type") == "INSTANT_CLEAR":
            instant_count += 1
        else:
            negotiated_count += 1

    avg_pcr = round(sum(pcr_list) / len(pcr_list), 4) if pcr_list else 0.0
    total_sales = len(sales)
    instant_rate = round(instant_count / total_sales, 4) if total_sales > 0 else 0.0
    negotiated_rate = round(negotiated_count / total_sales, 4) if total_sales > 0 else 0.0

    iv = len(sales) / (duration + 1)
    total_potential = sum(i["selling_price"] - i["cost_price"] for i in inventory)
    true_net_profit = total_profit - waste_loss
    ee = (total_profit - waste_loss) / total_potential if total_potential > 0 else 0.0

    return {
        "PCR":                  avg_pcr,
        "IV":                   round(iv, 4),
        "EE":                   round(ee, 4),
        "Total Profit":         round(total_profit, 2),
        "Waste Loss":           round(waste_loss, 2),
        "True Net Profit":      round(true_net_profit, 2),
        "Items Sold":           len(sales),
        "Instant Clears":       instant_count,
        "Negotiated Sales":     negotiated_count,
        "Instant Clear Rate":   instant_rate,
        "Negotiated Sale Rate": negotiated_rate,
        "pcr_list":             pcr_list,
        "Persuasion Events":    len(results["blackboard"].get("persuasion_events", [])),
        "API Errors":           results["blackboard"].get("api_errors", 0),
    }


def generate_trial_buyer_sequence(inventory: List[Dict], seed: int) -> Dict[int, Dict[str, Dict]]:
    """Pre-generate identical sequence of single-buyer encounters across periods for fair comparison."""
    rng = random.Random(seed)
    personalities = ["ESSENTIAL", "CALCULATED", "IMPULSE"]
    sequence = {}
    for period in [0, 2, 4, 6, 8]:
        sequence[period] = {}
        for item in inventory:
            item_id = item["item_id"]
            retail = item["selling_price"]
            pers = rng.choice(personalities)
            budget = round(retail * rng.uniform(0.90, 1.25), 2)
            sequence[period][item_id] = {
                "buyer_id": f"B_{period}_{item_id}",
                "personality": pers,
                "budget": budget,
                "target_item_id": item_id,
            }
    return sequence


async def run_condition(
    condition_name: str,
    inventory: List[Dict],
    trial_buyer_sequence: Dict[int, Dict[str, Dict]],
    mode: str,
    model_map: Dict,
    buyer_model: str,
    trial: int,
    ablation_type: str = "full",
):
    """Run a single trial of a single ablation condition."""
    env = AsyncHiveEnvironment(
        inventory_data=inventory,
        exp_type=f"{condition_name}_T{trial}",
        mode=mode,
        model_map=model_map,
        buyer_model=buyer_model,
    )

    # Apply ablations
    if ablation_type == "no_risk_reader":
        dummy_rr     = DummyRiskReader(model_map.get("tactical_negotiator", "Llama-8B-GR"))
        spokesperson = Spokesperson(model_map.get("tactical_negotiator", "Llama-8B-GR"))
        env.orchestrator = TacticalOrchestrator(
            model_map.get("tactical_negotiator", "Llama-8B-GR"), dummy_rr, spokesperson
        )
    elif ablation_type == "no_strategic_brain":
        env.brain = DummyStrategicBrain(model_map.get("strategic_brain", "Llama-70B-GR"))

    result = None
    async for checkpoint in env.run(trial_buyer_sequence):
        result = checkpoint

    metrics = calculate_metrics(result)
    price_traj = result["blackboard"].get("price_trajectory", [])
    inv_traj = result["blackboard"].get("inventory_trajectory", [])
    neg_log = result["blackboard"].get("negotiation_log", [])
    item_outcomes = result["blackboard"].get("item_outcomes", {})
    sales_data = result["blackboard"].get("sales_data", [])
    return metrics, price_traj, inv_traj, neg_log, item_outcomes, sales_data


async def run_ablation(n_trials: int = 5):
    print(f"=== ABLATION STUDY ({n_trials} TRIALS) ===", flush=True)
    print("Checking for existing checkpoints...", flush=True)

    # ── Load clean grocery inventory ──────────────────────────────────────────
    import pandas as pd_
    df = pd_.read_csv("perishable_goods_management.csv")
    grocery_categories = ['Produce', 'Meat', 'Dairy', 'Deli', 'Seafood', 
                           'Bakery', 'Beverages', 'Ready_to_Eat']
    clean_df = df[
        df['category'].isin(grocery_categories) &
        (df['days_until_expiry'] >= 2) &
        (df['days_until_expiry'] <= 14)
    ]
    cols = ["product_name", "category", "selling_price", "cost_price", "days_until_expiry",
            "spoilage_risk", "daily_demand", "quality_grade"]
    inventory = clean_df.sample(15, random_state=GLOBAL_SEED)[cols].to_dict("records")
    for idx, item in enumerate(inventory):
        item["item_id"] = f"{item['product_name']}_{idx+1}"

    model_map    = FINAL_CONFIG
    buyer_model  = "Llama-8B-GR"

    # ── 4 Full Benchmark Conditions ───────────────────────────────────────────
    conditions = [
        ("Full_MAS",            "MAS",          "full"),
        ("No_RiskReader",       "MAS",          "no_risk_reader"),
        ("No_StrategicBrain",   "MAS",          "no_strategic_brain"),
        ("LinearDecay_Baseline","LINEAR_DECAY",  "full"),
    ]

    all_rows = []

    for trial in range(1, n_trials + 1):
        print(f"\n{'='*50}", flush=True)
        print(f"TRIAL {trial}/{n_trials}", flush=True)

        # Pre-generate identical buyer sequence for this trial
        trial_buyer_seq = generate_trial_buyer_sequence(inventory, GLOBAL_SEED + trial)

        for condition_name, mode, ablation_type in conditions:
            # Check checkpoint
            cached = load_checkpoint(trial, condition_name)
            if cached:
                pcr_val = cached.get("final_metrics", {}).get("pcr", cached.get("PCR", 0.0))
                print(f"  [Loaded Checkpoint] {condition_name} T{trial}: PCR={pcr_val:.4f}", flush=True)
                metrics = cached
            else:
                print(f"  [{condition_name}] Running...", flush=True)
                metrics, p_traj, i_traj, neg_log, item_outcomes, sales_data = await run_condition(
                    condition_name, inventory, trial_buyer_seq,
                    mode, model_map, buyer_model, trial, ablation_type,
                )
                save_checkpoint(trial, condition_name, metrics, p_traj, i_traj, neg_log, item_outcomes, sales_data)
                print(f"  [DONE] {condition_name} T{trial}: PCR={metrics['PCR']:.4f} | Profit=${metrics['Total Profit']:.2f} | Waste=${metrics['Waste Loss']:.2f} | Sold={metrics['Items Sold']}/15 (Instant={metrics['Instant Clears']}, Neg={metrics['Negotiated Sales']})", flush=True)

            all_rows.append({
                "Trial":                trial,
                "Condition":            condition_name,
                "PCR":                  metrics.get("PCR", metrics.get("final_metrics", {}).get("pcr", 0.0)),
                "Total Profit":         metrics.get("Total Profit", metrics.get("final_metrics", {}).get("total_profit", 0.0)),
                "Waste Loss":           metrics.get("Waste Loss", metrics.get("final_metrics", {}).get("waste_loss", 0.0)),
                "True Net Profit":      metrics.get("True Net Profit", metrics.get("final_metrics", {}).get("true_net_profit", 0.0)),
                "Items Sold":           metrics.get("Items Sold", metrics.get("final_metrics", {}).get("items_sold", 0)),
                "Instant Clears":       metrics.get("Instant Clears", metrics.get("final_metrics", {}).get("instant_clears", 0)),
                "Negotiated Sales":     metrics.get("Negotiated Sales", metrics.get("final_metrics", {}).get("negotiated_sales", 0)),
                "Instant Clear Rate":   metrics.get("Instant Clear Rate", metrics.get("final_metrics", {}).get("instant_clear_rate", 0.0)),
                "Negotiated Sale Rate": metrics.get("Negotiated Sale Rate", metrics.get("final_metrics", {}).get("negotiated_sale_rate", 0.0)),
                "Persuasion Events":    metrics.get("Persuasion Events", metrics.get("final_metrics", {}).get("persuasion_events", 0)),
                "API Errors":           metrics.get("API Errors", metrics.get("final_metrics", {}).get("api_errors", 0)),
            })

    # ── Save results ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
    df_out = pd.DataFrame(all_rows)
    df_out.to_csv(SUMMARY_CSV, index=False)

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}", flush=True)
    print("ABLATION STUDY SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    summary = df_out.groupby("Condition")[["PCR", "Total Profit", "Waste Loss", "Items Sold", "Instant Clears", "Negotiated Sales", "Instant Clear Rate", "Negotiated Sale Rate", "API Errors"]].agg(["mean", "std"])
    print(summary.to_string(), flush=True)
    print(f"\nResults saved to: {SUMMARY_CSV}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(run_ablation(args.trials))
