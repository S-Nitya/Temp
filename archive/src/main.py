import pandas as pd
import asyncio
import time
import json
import os
import random
from .config import HIVE_CONFIG, MAX_HOURS, SIM_CLOCK_TICK, N_BUYERS
from .environment import AsyncHiveEnvironment
from .visualizer import generate_research_visualizations
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def calculate_metrics(results):
    sales = results['blackboard']['sales_data']
    inventory = results['blackboard']['inventory']
    duration = results['duration']
    
    total_potential = sum(i['selling_price'] - i['cost_price'] for i in inventory)
    total_profit = sum(s['sale_price'] - s['cost_price'] for s in sales)
    
    sold_names = [s['product_name'] for s in sales]
    waste_loss = sum(i['cost_price'] for i in inventory if i['product_name'] not in sold_names)
    
    ee = (total_profit - waste_loss) / total_potential if total_potential > 0 else 0
    
    pcr_list = []
    for s in sales:
        potential = s['initial_price'] - s['cost_price']
        actual = s['sale_price'] - s['cost_price']
        pcr = actual / potential if potential > 0 else 1.0
        pcr_list.append(max(0, pcr))
    avg_pcr = sum(pcr_list) / len(pcr_list) if pcr_list else 0
    
    iv = len(sales) / (duration + 1)
    
    return {
        "PCR": avg_pcr, 
        "IV": iv, 
        "EE": ee, 
        "Total Profit": total_profit, 
        "Waste Loss": waste_loss,
        "Items Sold": len(sales)
    }

def display_results(exp_name, metrics_mas, metrics_human):
    table = Table(title=f"Experiment: {exp_name}")
    table.add_column("Metric")
    table.add_column("MAS (Hive)", style="cyan")
    table.add_column("Human Baseline", style="magenta")
    table.add_column("Improvement", style="green")

    for metric in ["PCR", "IV", "EE", "Total Profit", "Waste Loss"]:
        m_val = metrics_mas[metric]
        h_val = metrics_human[metric]
        
        if h_val != 0:
            imp = ((m_val - h_val) / abs(h_val) * 100)
            if metric == "Waste Loss": imp = -imp
        else:
            imp = 100.0 if m_val > 0 else 0.0
            if metric == "Waste Loss" and m_val == 0: imp = 100.0
            
        display_m = f"{m_val:.3f}" if metric in ["PCR", "IV", "EE"] else f"${m_val:.2f}"
        display_h = f"{h_val:.3f}" if metric in ["PCR", "IV", "EE"] else f"${h_val:.2f}"
        
        table.add_row(metric, display_m, display_h, f"{imp:+.1f}%")
    console.print(table)

async def main_async():
    console.print("[bold blue]=== THE AUTONOMOUS HIVE: MULTI-MODEL BENCHMARK ENGINE ===[/bold blue]")
    
    # 1. Load Data
    try:
        df_prod = pd.read_csv("perishable_goods_management.csv")
        cols = ['product_name', 'selling_price', 'cost_price', 'days_until_expiry', 
                'spoilage_risk', 'daily_demand', 'quality_grade']
        experiment_inventory = df_prod[df_prod['days_until_expiry'] >= 3].sample(15)[cols].to_dict('records')
    except Exception as e:
        console.print(f"[red]Error loading inventory: {e}[/red]")
        return

    # 3. Experiment Configurations
    EXPERIMENTS = [
        # --- Homogeneous Experiments ---
        {
            "name": "Full Llama-70B Dominance",
            "model_map": {k: "Llama-70B-NV" for k in HIVE_CONFIG.keys()},
            "buyer_model": "Llama-70B-NV"
        },
        {
            "name": "Llama-8B Lightweight Efficiency",
            "model_map": {k: "Llama-8B-GR" for k in HIVE_CONFIG.keys()},
            "buyer_model": "Llama-8B-GR"
        },
        {
            "name": "Mixtral-8x7B Balanced Market",
            "model_map": {k: "Mixtral-8x7B-GR" for k in HIVE_CONFIG.keys()},
            "buyer_model": "Mixtral-8x7B-GR"
        },
        # --- Heterogeneous Experiments ---
        {
            "name": "Smart Hive vs Budget Buyers (70B vs 8B)",
            "model_map": {k: "Llama-70B-NV" for k in HIVE_CONFIG.keys()},
            "buyer_model": "Llama-8B-GR"
        },
        {
            "name": "Budget Hive vs Smart Buyers (8B vs 70B)",
            "model_map": {k: "Llama-8B-GR" for k in HIVE_CONFIG.keys()},
            "buyer_model": "Llama-70B-NV"
        }
    ]

    all_results = []
    from .agents import Buyer

    for config in EXPERIMENTS:
        console.print(Panel(f"Running Experiment: {config['name']}", style="bold yellow"))
        
        # PRE-GENERATE SHARED BUYERS FOR FAIRNESS
        shared_buyers_config = []
        personalities = ["ESSENTIAL", "CALCULATED", "IMPULSE"]
        for i in range(1, N_BUYERS + 1):
            shopping_list = random.sample([item['product_name'] for item in experiment_inventory], k=random.randint(2, 3))
            personality = random.choice(personalities)
            total_target_val = sum(next(item['selling_price'] for item in experiment_inventory if item['product_name'] == name) for name in shopping_list)
            budget = total_target_val * random.uniform(0.9, 1.2)
            shared_buyers_config.append({
                "id": i, "budget": budget, "list": shopping_list, "personality": personality
            })

        # Create experiment-specific output dir
        safe_name = config['name'].replace(" ", "_").replace("(", "").replace(")", "")
        exp_output_dir = os.path.join("output", safe_name)
        os.makedirs(exp_output_dir, exist_ok=True)

        # A. Run MAS
        env_mas = AsyncHiveEnvironment(experiment_inventory, config['name'], mode="MAS", 
                                      model_map=config['model_map'], buyer_model=config['buyer_model'])
        # Inject shared buyers
        env_mas.buyers = [Buyer(b['id'], config['buyer_model'], b['budget'], b['list'], b['personality']) for b in shared_buyers_config]
        res_mas = await env_mas.run()
        metrics_mas = calculate_metrics(res_mas)
        
        # B. Run Human Baseline
        env_human = AsyncHiveEnvironment(experiment_inventory, config['name'], mode="BASELINE",
                                        model_map=config['model_map'], buyer_model=config['buyer_model'])
        # Inject EXACT SAME shared buyers
        env_human.buyers = [Buyer(b['id'], config['buyer_model'], b['budget'], b['list'], b['personality']) for b in shared_buyers_config]
        res_human = await env_human.run()
        metrics_human = calculate_metrics(res_human)
        
        # C. Output Results
        display_results(config['name'], metrics_mas, metrics_human)
        
        # Save Experiment Data
        exp_data = {
            "experiment": config['name'],
            "metrics": {"mas": metrics_mas, "human": metrics_human},
            "raw": {"mas": res_mas, "human": res_human}
        }
        with open(os.path.join(exp_output_dir, "session_data.json"), "w") as f:
            json.dump(exp_data, f, indent=4)
        
        # Generate Specific Visuals for this model combo
        generate_research_visualizations(pd.DataFrame([metrics_mas, metrics_human]), output_dir=exp_output_dir)

        all_results.append(exp_data)
        await asyncio.sleep(2)

    # 4. Final Save & Viz
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "benchmarking_research_data.json"), "w") as f:
        json.dump(all_results, f, indent=4)

    console.print(f"\n[dim]Full benchmarking results saved to {output_dir}/benchmarking_research_data.json[/dim]")

if __name__ == "__main__":
    asyncio.run(main_async())
