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

def display_results(exp_name, metrics_mas, metrics_single, metrics_human, metrics_historical):
    table = Table(title=f"4-Way Benchmark (with Historical): {exp_name}")
    table.add_column("Metric", style="bold white")
    table.add_column("Kanishka MAS", style="cyan")
    table.add_column("Single-Model", style="yellow")
    table.add_column("Baseline (CSV Pricing)", style="magenta")
    table.add_column("Actual Historical", style="green")

    for metric in ["PCR", "IV", "EE", "Total Profit", "Waste Loss", "Items Sold"]:
        m_val = metrics_mas.get(metric, 0)
        s_val = metrics_single.get(metric, 0)
        h_val = metrics_human.get(metric, 0)
        hist_val = metrics_historical.get(metric, 0)
        
        fmt = lambda v: f"{v:.3f}" if metric in ["PCR", "IV", "EE"] else (f"${v:.2f}" if metric != "Items Sold" else str(int(v)))
        
        if metric in ["PCR", "IV", "EE", "Items Sold"]:
            table.add_row(metric, fmt(m_val), fmt(s_val), fmt(h_val), "N/A")
        else:
            table.add_row(metric, fmt(m_val), fmt(s_val), fmt(h_val), fmt(hist_val))
    console.print(table)

async def main_async():
    console.print("[bold blue]=== THE AUTONOMOUS HIVE: 3-WAY BENCHMARK ENGINE ===[/bold blue]")
    
    # 1. Load Data
    try:
        df_prod = pd.read_csv("perishable_goods_management.csv")
        cols = ['product_name', 'selling_price', 'cost_price', 'days_until_expiry', 
                'spoilage_risk', 'daily_demand', 'quality_grade']
        sampled_df = df_prod[df_prod['days_until_expiry'] >= 3].sample(15, random_state=42)
        experiment_inventory = sampled_df[cols].to_dict('records')
        
        metrics_historical = {
            "Total Profit": float(sampled_df['profit'].sum()),
            "Waste Loss": float(sampled_df['waste_cost'].sum()),
            "PCR": 0.0, "IV": 0.0, "EE": 0.0, "Items Sold": 0
        }
    except Exception as e:
        console.print(f"[red]Error loading inventory: {e}[/red]")
        return

    # 2. Experiment Configurations
    EXPERIMENTS = [
        {
            "name": "Gemini 3.1 Pro Limit Test",
            "model_map": {k: "Gemini-3.1-Pro" for k in HIVE_CONFIG.keys()},
            "buyer_model": "Gemini-3.1-Pro"
        }
        # {
        #     "name": "Full Llama-70B Dominance",
        #     "model_map": {k: "Llama-70B-GR" for k in HIVE_CONFIG.keys()},
        #     "buyer_model": "Llama-70B-NV"
        # }
    ]

    all_results = []
    from .agents import Buyer

    for config in EXPERIMENTS:
        console.print(Panel(f"Running 3-Way Benchmark: {config['name']}", style="bold yellow"))
        
        # PRE-GENERATE SHARED BUYERS for scientific fairness across all 3 runs
        random.seed(42)
        shared_buyers_config = []
        personalities = ["ESSENTIAL", "CALCULATED", "IMPULSE"]
        for i in range(1, N_BUYERS + 1):
            shopping_list = random.sample([item['product_name'] for item in experiment_inventory], k=random.randint(2, 3))
            personality = random.choice(personalities)
            total_target_val = sum(next(item['selling_price'] for item in experiment_inventory if item['product_name'] == name) for name in shopping_list)
            budget = total_target_val * random.uniform(0.9, 1.2)
            shared_buyers_config.append({"id": i, "budget": budget, "list": shopping_list, "personality": personality})

        # Output dir
        safe_name = config['name'].replace(" ", "_").replace("(", "").replace(")", "")
        exp_output_dir = os.path.join("kanishka_output", safe_name)
        os.makedirs(exp_output_dir, exist_ok=True)

        def make_buyers(buyer_model):
            return [Buyer(b['id'], buyer_model, b['budget'], b['list'], b['personality']) for b in shared_buyers_config]

        # ── A. Kanishka's MAS (TacticalOrchestrator) ─────────────────────────────
        console.print("[cyan]Running: Kanishka MAS (TacticalOrchestrator)...[/cyan]")
        env_mas = AsyncHiveEnvironment(experiment_inventory, config['name'], mode="MAS",
                                      model_map=config['model_map'], buyer_model=config['buyer_model'])
        env_mas.buyers = make_buyers(config['buyer_model'])
        env_mas.histories = {b['id']: [] for b in shared_buyers_config}
        env_mas.buyer_targets = {b['id']: None for b in shared_buyers_config}
        res_mas = None
        async for checkpoint in env_mas.run():
            res_mas = checkpoint
            with open(os.path.join(exp_output_dir, "checkpoint_mas.json"), "w") as f:
                json.dump(checkpoint, f, indent=4)
        metrics_mas = calculate_metrics(res_mas)

        # ── B. Single-Model MAS (Pure LLM, no architecture) ──────────────────────
        console.print("[yellow]Running: Single-Model (No Architecture)...[/yellow]")
        env_single = AsyncHiveEnvironment(experiment_inventory, config['name'], mode="SINGLE_MODEL",
                                         model_map=config['model_map'], buyer_model=config['buyer_model'])
        env_single.buyers = make_buyers(config['buyer_model'])
        env_single.histories = {b['id']: [] for b in shared_buyers_config}
        env_single.buyer_targets = {b['id']: None for b in shared_buyers_config}
        res_single = None
        async for checkpoint in env_single.run():
            res_single = checkpoint
            with open(os.path.join(exp_output_dir, "checkpoint_single.json"), "w") as f:
                json.dump(checkpoint, f, indent=4)
        metrics_single = calculate_metrics(res_single)

        # ── C. Human Baseline (Static CSV Price) ─────────────────────────────────
        console.print("[magenta]Running: Human Baseline (Static CSV Price)...[/magenta]")
        env_human = AsyncHiveEnvironment(experiment_inventory, config['name'], mode="BASELINE_CSV",
                                        model_map=config['model_map'], buyer_model=config['buyer_model'])
        env_human.buyers = make_buyers(config['buyer_model'])
        env_human.histories = {b['id']: [] for b in shared_buyers_config}
        env_human.buyer_targets = {b['id']: None for b in shared_buyers_config}
        res_human = None
        async for checkpoint in env_human.run():
            res_human = checkpoint
            with open(os.path.join(exp_output_dir, "checkpoint_human.json"), "w") as f:
                json.dump(checkpoint, f, indent=4)
        metrics_human = calculate_metrics(res_human)

        # ── Display + Save ────────────────────────────────────────────────────────
        display_results(config['name'], metrics_mas, metrics_single, metrics_human, metrics_historical)
        
        exp_data = {
            "experiment": config['name'],
            "metrics": {
                "kanishka_mas": metrics_mas,
                "single_model_mas": metrics_single,
                "human_baseline": metrics_human,
                "actual_historical": metrics_historical
            },
            "raw": {
                "kanishka_mas": res_mas,
                "single_model_mas": res_single,
                "human_baseline": res_human
            }
        }
        with open(os.path.join(exp_output_dir, "session_data.json"), "w") as f:
            json.dump(exp_data, f, indent=4)
        
        generate_research_visualizations(pd.DataFrame([metrics_mas, metrics_single, metrics_human]), output_dir=exp_output_dir)
        all_results.append(exp_data)
        await asyncio.sleep(2)

    # 3. Final Save
    output_dir = "kanishka_output"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "benchmarking_research_data.json"), "w") as f:
        json.dump(all_results, f, indent=4)
        
    csv_rows = []
    for res in all_results:
        row = {"Experiment": res["experiment"]}
        for model in ["kanishka_mas", "single_model_mas", "human_baseline", "actual_historical"]:
            for metric in ["Total Profit", "Waste Loss", "PCR", "IV", "EE", "Items Sold"]:
                row[f"{model}_{metric}"] = res["metrics"][model].get(metric, 0) if model in res["metrics"] else 0
        csv_rows.append(row)
    
    df_out = pd.DataFrame(csv_rows)
    df_out.to_csv(os.path.join(output_dir, "benchmarking_research_summary.csv"), index=False)

    console.print(f"\n[bold green][SUCCESS] All benchmarks complete! Saved JSON and CSV to {output_dir}/[/bold green]")

if __name__ == "__main__":
    asyncio.run(main_async())
