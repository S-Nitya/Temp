import os
import sys
import json
import traceback
import pandas as pd
from typing import List, Dict

# To run as a module: python -m src.architecture_04_listing_agent
try:
    from .config import ProductConfig
    from .environment import NegotiationEnvironment
except ImportError:
    from config import ProductConfig
    from environment import NegotiationEnvironment

def log(msg):
    print(msg, flush=True)

def main():
    architectures = ["Single_Agent", "Listing_Agent"]
    environments = ["Normal", "Asymmetric_Info", "Adversarial"]
    N_TRIALS = 20 # Defaults to 20 per cell as per paper specs
    
    # Allow overriding N_TRIALS for testing purposes
    if os.getenv("N_TRIALS_TEST"):
        N_TRIALS = int(os.getenv("N_TRIALS_TEST"))

    config = ProductConfig(
        base_cost=20.0,
        retail_price=80.0,
        true_expiry=10,
        transit_time=2,
        holding_cost=2.0
    )

    all_results: List[Dict] = []
    all_transcripts: List[Dict] = []

    total_runs = len(architectures) * len(environments) * N_TRIALS
    log(f"{'='*70}")
    log(f"  TIME IS MONEY: Architecture 04 (Listing Agent — No-Formula CMA)")
    log(f"  Matrix: {len(architectures)} Architectures x {len(environments)} Environments x {N_TRIALS} Trials = {total_runs} runs")
    log(f"  Provider: {os.getenv('LLM_PROVIDER', 'openrouter')}")
    log(f"  Key Innovation: Appraiser reasons qualitatively — no injected floor price")
    log(f"{'='*70}")
    
    current_run = 0

    for arch in architectures:
        for env in environments:
            log(f"\n--- {arch} | {env} ---")
            for trial in range(1, N_TRIALS + 1):
                current_run += 1
                log(f"[{current_run}/{total_runs}] {arch} / {env} / Trial {trial} ...")
                
                try:
                    sim_env = NegotiationEnvironment(
                        config=config,
                        architecture=arch,
                        env_type=env,
                        max_rounds=10,
                        buyer_budget=100.0
                    )
                    
                    result, transcript = sim_env.run()
                    result["Trial"] = trial
                    
                    all_results.append(result)
                    
                    all_transcripts.append({
                        "Architecture": arch,
                        "Environment": env,
                        "Trial": trial,
                        "Result": result,
                        "Transcript": transcript
                    })
                    
                    log(f"  -> {result['Outcome']} | Eff: {result['Efficiency']:.2f} | Price: ${result['Final_Price']:.0f} | Tokens: {result['Total_Tokens']} | {result['Latency_Seconds']:.1f}s")
                    
                except Exception as e:
                    log(f"  -> ERROR: {e}")
                    traceback.print_exc()
                    sys.stdout.flush()
                    # Record failed trial
                    all_results.append({
                        "Architecture": arch,
                        "Environment": env,
                        "Trial": trial,
                        "Outcome": f"ERROR: {str(e)[:50]}",
                        "Success": 0,
                        "Failed_Logistics": 0,
                        "Efficiency": 0.0,
                        "Final_Price": 0.0,
                        "Agreed_Round": 0,
                        "Total_Tokens": 0,
                        "Latency_Seconds": 0.0
                    })
                
                # Incremental save after each trial to prevent data loss
                os.makedirs("output", exist_ok=True)
                pd.DataFrame(all_results).to_csv("output/simulation_results_04.csv", index=False)

    # Final output generation
    os.makedirs("output", exist_ok=True)
    
    df = pd.DataFrame(all_results)
    df.to_csv("output/simulation_results_04.csv", index=False)
    log("\nResults saved to output/simulation_results_04.csv")

    with open("output/research_transcripts_04.json", "w") as f:
        json.dump(all_transcripts, f, indent=4)
    log("Transcripts saved to output/research_transcripts_04.json")

    log(f"\n{'='*70}")
    log("  SIMULATION RESULTS (MEANS)")
    log(f"{'='*70}")
    pivot = df.pivot_table(
        index=["Architecture"],
        columns=["Environment"],
        values=["Success", "Failed_Logistics", "Efficiency", "Total_Tokens", "Latency_Seconds"],
        aggfunc="mean"
    ).round(2)
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    log(str(pivot))
    log(f"{'='*70}\n")

if __name__ == "__main__":
    main()
