import pandas as pd
import asyncio
import time
import json
import os
from .config import HIVE_CONFIG, MAX_HOURS, SIM_CLOCK_TICK
from .environment import AsyncHiveEnvironment
from .visualizer import generate_research_visualizations
from rich.console import Console
from rich.panel import Panel

console = Console()

async def main_async():
    console.print("[bold blue]=== THE AUTONOMOUS HIVE: RESEARCH ENGINE ===[/bold blue]")
    
    # Load Data
    try:
        df_prod = pd.read_csv("perishable_goods_management.csv")
        inventory = df_prod[df_prod['days_until_expiry'] >= 3].sample(5).to_dict('records')
    except Exception as e:
        console.print(f"[red]Error loading inventory: {e}[/red]")
        return

    # Initialize Environment
    env = AsyncHiveEnvironment(inventory, "Deep_Research_SOTA")
    
    # Run simulation
    results = await env.run()
    
    # Save Raw Data
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "session_research_data.json"), "w") as f:
        json.dump(results, f, indent=4)

    # Final Review (Post-Mortem)
    console.print("\n[yellow][Phase] Reflection (Deep Research Analysis)...[/yellow]")
    review = await env.critic.review(results)
    
    # Print Detailed Report
    console.print(Panel(
        f"[bold green]SESSION COMPLETE[/bold green]\n"
        f"Items Sold: {results['sold_count']}/{results['total_items']}\n"
        f"Final Grade: {review.get('final_grade', 'N/A')}\n\n"
        f"[bold cyan]Executive Summary:[/bold cyan]\n{review.get('executive_summary', 'No summary available.')}\n\n"
        f"[bold magenta]Research Notes:[/bold magenta]\n{review.get('research_notes', 'No notes available.')}",
        title="Hive Post-Mortem Analysis",
        expand=False
    ))

    # Print SWOT
    swot = review.get('swot_analysis', {})
    if swot:
        console.print("\n[bold yellow]SWOT Analysis:[/bold yellow]")
        for category, items in swot.items():
            console.print(f"  [bold]{category.upper()}:[/bold] {', '.join(items) if isinstance(items, list) else items}")

    console.print(f"\n[dim]Full raw data saved to {os.path.join(output_dir, 'session_research_data.json')}[/dim]")
    
    # Generate Research Charts
    generate_research_visualizations(pd.DataFrame([results]))

if __name__ == "__main__":
    asyncio.run(main_async())
