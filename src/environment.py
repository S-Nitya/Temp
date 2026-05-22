import asyncio
import time
import random
import re
import json
from typing import Dict, List, Any
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

from .agents import (
    Buyer, IntelligenceHub, StrategicBrain, TacticalNegotiator,
    IntegrityWatchdog, ChaosInjector, PostMortemCritic
)
from .config import MAX_HOURS, SIM_CLOCK_TICK, N_BUYERS, HIVE_CONFIG

console = Console()

class AsyncHiveEnvironment:
    def __init__(self, inventory_data: List[Dict[str, Any]], exp_type: str):
        self.inventory = inventory_data
        self.exp_type = exp_type
        
        cfg = HIVE_CONFIG
        self.hub = IntelligenceHub(cfg['intelligence_hub'])
        self.brain = StrategicBrain(cfg['strategic_brain'])
        self.negotiator = TacticalNegotiator(cfg['tactical_negotiator'])
        self.watchdog = IntegrityWatchdog(cfg['integrity_watchdog'])
        self.red_teamer = ChaosInjector(cfg['chaos_injector'])
        self.critic = PostMortemCritic(cfg['critic'])
        
        self.blackboard = {
            "inventory": self.inventory,
            "quotes": {i['product_name']: i['selling_price'] for i in self.inventory},
            "strategy": "Initializing...",
            "logs": [],
            "chaos": []
        }
        
        self.current_hour = 0
        self.sold_items = []
        self.buyers = []
        self.histories = {}
        
        for i in range(1, N_BUYERS + 1):
            target = random.choice(self.inventory)['product_name']
            budget = next(item['selling_price'] for item in self.inventory if item['product_name'] == target) * random.uniform(0.9, 1.15)
            self.buyers.append(Buyer(i, "Llama-8B-GR", budget, target))
            self.histories[i] = []

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        layout["main"].split_row(
            Layout(name="inv", ratio=1),
            Layout(name="desk", ratio=2)
        )
        return layout

    def update_display(self, layout: Layout):
        layout["header"].update(Panel(Text(f"THE HIVE | CONSOLIDATED 6-AGENT MODE | {self.exp_type}", justify="center", style="bold green")))
        
        # Inv
        inv_table = Table(title="Inventory", expand=True)
        inv_table.add_column("Item")
        inv_table.add_column("Quote")
        for item in self.inventory:
            status = "[SOLD]" if item['product_name'] in self.sold_items else f"${self.blackboard['quotes'].get(item['product_name'], 0):.2f}"
            inv_table.add_row(item['product_name'], status)
        layout["inv"].update(Panel(inv_table, border_style="cyan"))

        # Desk
        desk_text = Text()
        desk_text.append(f"STRATEGY: {self.blackboard['strategy']}\n\n", style="bold yellow")
        for log in self.blackboard["logs"][-12:]:
            desk_text.append(f"{log}\n")
        layout["desk"].update(Panel(desk_text, title="Sales Desk", border_style="red"))

        # Footer
        layout["footer"].update(Panel(Text(f"Hour: {self.current_hour}/{MAX_HOURS} | Sold: {len(self.sold_items)} | Chaos: {len(self.blackboard['chaos'])}", justify="center")))

    async def _negotiate(self, buyer):
        if buyer.target_product in self.sold_items: return
        price = self.blackboard["quotes"].get(buyer.target_product, 0)
        
        # Async calls with heartbeat
        self.blackboard["logs"].append(f"ENGAGING: Buyer {buyer.buyer_id} for {buyer.target_product}...")
        b_act = await buyer.act(self.histories[buyer.buyer_id], price)
        
        if b_act.get("action") == "ACCEPT":
            if buyer.target_product not in self.sold_items:
                self.sold_items.append(buyer.target_product)
                self.blackboard["logs"].append(f"SUCCESS: B{buyer.buyer_id} accepted ${price:.2f} for {buyer.target_product}")
        else:
            s_act = await self.negotiator.act(buyer.buyer_id, buyer.target_product, price, self.blackboard["strategy"])
            self.blackboard["logs"].append(f"HIVE -> B{buyer.buyer_id}: {s_act.get('message', '')[:40]}...")

    async def run(self) -> Dict[str, Any]:
        layout = self.make_layout()
        with Live(layout, refresh_per_second=2, screen=True):
            while self.current_hour < MAX_HOURS and len(self.sold_items) < len(self.inventory):
                self.update_display(layout)
                
                # 1. Intelligence Hub
                intel = await self.hub.act(self.inventory, [])
                
                # 2. Strategic Brain
                res = await self.brain.act(intel, self.inventory)
                self.blackboard["quotes"] = res.get("quotes", self.blackboard["quotes"])
                self.blackboard["strategy"] = res.get("strategy_directive", "Normal operations.")
                
                # 3. Integrity Audit
                await self.watchdog.audit(self.blackboard["strategy"], self.blackboard["quotes"])
                
                # 4. Market Engagement
                tasks = [self._negotiate(b) for b in self.buyers]
                await asyncio.gather(*tasks)
                
                # 5. Red Teaming
                if random.random() < 0.2:
                    chaos = await self.red_teamer.act(self.blackboard)
                    self.blackboard["chaos"].append(chaos)
                    self.blackboard["logs"].append(f"ALERT: {chaos.get('event', 'Market Shock')}")

                self.current_hour += SIM_CLOCK_TICK
                self.update_display(layout)
                await asyncio.sleep(0.5)

        return {
            "status": "FINISHED",
            "sold_count": len(self.sold_items),
            "sold_items": self.sold_items,
            "total_items": len(self.inventory),
            "blackboard": self.blackboard,
            "histories": self.histories,
            "duration": self.current_hour
        }
