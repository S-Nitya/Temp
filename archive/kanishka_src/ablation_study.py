import asyncio
import os
import json
import random
import argparse
import pandas as pd
import numpy as np
from datetime import datetime

from kanishka_src.environment import AsyncHiveEnvironment, N_BUYERS
from kanishka_src.agents import RiskReader, StrategicBrain, TacticalOrchestrator, Spokesperson, Buyer, DummyRiskReader
from kanishka_src.config import HIVE_CONFIG
from kanishka_src.main import calculate_metrics

# DummyRiskReader is imported from agents.py where it is now defined
# (bluffing=5, walk_away=5 neutral baseline — not falsely optimistic 0,0)

class DummyStrategicBrain(StrategicBrain):
    """Ablated Strategic Brain that provides no dynamic pricing or floor adjustments."""
    async def act(self, intel, inventory, chaos_events, current_hour, max_hours):
        return {
            "strategy_directive": "STATIC_HOLD (StrategicBrain Ablated)",
            # By not returning 'quotes' or 'floor_prices', the environment keeps them static at their initial values.
        }

# --- CUSTOM ENVIRONMENT BUILDERS ---

class BlindOrchestratorEnvironment(AsyncHiveEnvironment):
    """Environment where the MAS has NO RiskReader."""
    def __init__(self, inventory_data, exp_type, model_map, buyer_model):
        super().__init__(inventory_data, exp_type, "MAS", model_map, buyer_model=buyer_model)
        dummy_reader = DummyRiskReader(model_map.get('tactical_negotiator'))
        spokesperson = Spokesperson(model_map.get('tactical_negotiator'))
        self.orchestrator = TacticalOrchestrator(model_map.get('tactical_negotiator'), dummy_reader, spokesperson)

class BrainlessEnvironment(AsyncHiveEnvironment):
    """Environment where the MAS has NO StrategicBrain."""
    def __init__(self, inventory_data, exp_type, model_map, buyer_model):
        super().__init__(inventory_data, exp_type, "MAS", model_map, buyer_model=buyer_model)
        self.brain = DummyStrategicBrain(model_map.get('strategic_brain'))

# --- MAIN EXECUTION ---

async def run_ablation_study(num_trials: int):
    # Load and clean inventory
    df_prod = pd.read_csv("perishable_goods_management.csv")
    cols = ['product_name', 'selling_price', 'cost_price', 'days_until_expiry', 'spoilage_risk', 'daily_demand', 'quality_grade']
    sampled_df = df_prod[df_prod['days_until_expiry'] >= 3].sample(15, random_state=42)
    master_inventory = sampled_df[cols].to_dict('records')
    
    # Remove Vaccines outlier for fairness
    master_inventory = [i for i in master_inventory if i['product_name'] != 'Vaccines']

    output_dir = "kanishka_output/Ablation_Study"
    checkpoint_dir = os.path.join(output_dir, "checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)

    print(f"=== STARTING MAS ABLATION STUDY ({num_trials} TRIALS) ===")
    
    model_map = {k: "Llama-70B-GR" for k in HIVE_CONFIG.keys()}
    buyer_model = "Llama-70B-NV"
    
    configs = ["Full_MAS", "No_RiskReader", "No_StrategicBrain"]
    trial_results = {cfg: [] for cfg in configs}
    
    # Load any existing checkpoints from disk
    print("Checking for existing checkpoints...")
    for trial in range(1, num_trials + 1):
        for cfg in configs:
            metrics_path = os.path.join(checkpoint_dir, f"metrics_{cfg}_T{trial}.json")
            if os.path.exists(metrics_path):
                try:
                    with open(metrics_path, "r") as f:
                        metrics = json.load(f)
                    trial_results[cfg].append((trial, metrics))
                    print(f"  [Loaded Checkpoint] Loaded Trial {trial} {cfg}: Profit ${metrics['Total Profit']:.2f}")
                except Exception as e:
                    print(f"  [Warning] Failed to load checkpoint {metrics_path}: {e}")

    # Helper to check if a specific run is already completed
    def is_completed(cfg_name, trial_idx):
        return any(t == trial_idx for t, _ in trial_results[cfg_name])

    for trial in range(1, num_trials + 1):
        trial_seed = 42 + trial
        
        # Helper to run a specific environment setup
        async def run_env(env_class, mode, exp_name, cfg_name):
            if is_completed(cfg_name, trial):
                return
            
            # Seed right before initialization to ensure identical buyer configs
            random.seed(trial_seed)
            env = env_class(master_inventory.copy(), exp_name, model_map, buyer_model) if env_class != AsyncHiveEnvironment else \
                  AsyncHiveEnvironment(master_inventory.copy(), exp_name, mode="MAS", model_map=model_map, buyer_model=buyer_model)
            
            res = None
            async for checkpoint in env.run():
                res = checkpoint
            metrics = calculate_metrics(res)
            
            # Save checkpoints immediately
            metrics_path = os.path.join(checkpoint_dir, f"metrics_{cfg_name}_T{trial}.json")
            raw_path = os.path.join(checkpoint_dir, f"raw_{cfg_name}_T{trial}.json")
            
            with open(metrics_path, "w") as f:
                json.dump(metrics, f, indent=4)
            with open(raw_path, "w") as f:
                try:
                    json.dump(res, f, indent=4)
                except Exception as e:
                    print(f"Warning: Raw serialization failed: {e}")
            
            trial_results[cfg_name].append((trial, metrics))
            print(f"   [Saved Checkpoint] Trial {trial} {cfg_name} complete")

        # Run 1: Full MAS (Baseline)
        if not is_completed("Full_MAS", trial):
            print(f"\n--- TRIAL {trial}/{num_trials} | [Full MAS] Running... ---")
            await run_env(AsyncHiveEnvironment, "MAS", f"Full_MAS_T{trial}", "Full_MAS")
            loaded_m = next(m for t, m in trial_results["Full_MAS"] if t == trial)
            print(f"   Profit: ${loaded_m['Total Profit']:.2f} | Waste: ${loaded_m['Waste Loss']:.2f} | PCR: {loaded_m['PCR']:.3f}")

        # Run 2: No RiskReader
        if not is_completed("No_RiskReader", trial):
            print(f"\n--- TRIAL {trial}/{num_trials} | [No RiskReader] Running... ---")
            await run_env(BlindOrchestratorEnvironment, "MAS", f"No_RiskReader_T{trial}", "No_RiskReader")
            loaded_m = next(m for t, m in trial_results["No_RiskReader"] if t == trial)
            print(f"   Profit: ${loaded_m['Total Profit']:.2f} | Waste: ${loaded_m['Waste Loss']:.2f} | PCR: {loaded_m['PCR']:.3f}")

        # Run 3: No StrategicBrain
        if not is_completed("No_StrategicBrain", trial):
            print(f"\n--- TRIAL {trial}/{num_trials} | [No StrategicBrain] Running... ---")
            await run_env(BrainlessEnvironment, "MAS", f"No_StrategicBrain_T{trial}", "No_StrategicBrain")
            loaded_m = next(m for t, m in trial_results["No_StrategicBrain"] if t == trial)
            print(f"   Profit: ${loaded_m['Total Profit']:.2f} | Waste: ${loaded_m['Waste Loss']:.2f} | PCR: {loaded_m['PCR']:.3f}")

    # --- AGGREGATION & STATISTICS ---
    summary_rows = []
    
    print("\n" + "="*70)
    print(f"{'Configuration':<25} | {'Mean Profit':<12} | {'Profit Std':<10} | {'Mean Waste':<10} | {'Waste Std':<9}")
    print("="*70)

    for cfg in configs:
        cfg_runs = sorted(trial_results[cfg], key=lambda x: x[0])
        cfg_runs = cfg_runs[:num_trials]
        
        profits = [r[1]["Total Profit"] for r in cfg_runs]
        wastes = [r[1]["Waste Loss"] for r in cfg_runs]
        pcrs = [r[1]["PCR"] for r in cfg_runs]
        items_sold = [r[1]["Items Sold"] for r in cfg_runs]
        ees = [r[1]["EE"] for r in cfg_runs]
        
        mean_profit = np.mean(profits)
        std_profit = np.std(profits)
        mean_waste = np.mean(wastes)
        std_waste = np.std(wastes)
        mean_pcr = np.mean(pcrs)
        mean_ee = np.mean(ees)
        mean_sold = np.mean(items_sold)
        
        print(f"{cfg:<25} | ${mean_profit:<11.2f} | ${std_profit:<9.2f} | ${mean_waste:<9.2f} | ${std_waste:<8.2f}")
        
        summary_rows.append({
            "Configuration": cfg,
            "Mean Profit": mean_profit,
            "Profit StdDev": std_profit,
            "Mean Waste": mean_waste,
            "Waste StdDev": std_waste,
            "Mean PCR": mean_pcr,
            "Mean EE": mean_ee,
            "Mean Items Sold": mean_sold
        })
    print("="*70)

    # Save to CSV
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(f"{output_dir}/benchmarking_ablation_summary.csv", index=False)
    
    # Save raw trial data as JSON (for all trials run/loaded)
    formatted_raw = {cfg: [r[1] for r in sorted(trial_results[cfg], key=lambda x: x[0])[:num_trials]] for cfg in configs}
    with open(f"{output_dir}/raw_trial_data.json", "w") as f:
        json.dump(formatted_raw, f, indent=4)
        
    print(f"\n[SUCCESS] Ablation study complete! Saved summary to {output_dir}/benchmarking_ablation_summary.csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MAS Ablation Study with Checkpointing")
    parser.add_argument("--trials", type=int, default=5, help="Number of trials to run")
    args = parser.parse_args()
    
    asyncio.run(run_ablation_study(args.trials))
