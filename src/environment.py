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
    IntegrityWatchdog, ChaosInjector, PostMortemCritic, HumanSalesManager
)
from .config import MAX_HOURS, SIM_CLOCK_TICK, N_BUYERS, HIVE_CONFIG

console = Console()

class AsyncHiveEnvironment:
    def __init__(self, inventory_data: List[Dict[str, Any]], exp_type: str, mode: str = "MAS", model_map: Dict[str, str] = None, buyer_model: str = "Llama-8B-GR"):
        self.inventory = inventory_data
        self.exp_type = exp_type
        self.mode = mode
        
        cfg = model_map if model_map else HIVE_CONFIG
        if self.mode == "MAS":
            self.hub = IntelligenceHub(cfg.get('intelligence_hub', 'Llama-8B-GR'))
            self.brain = StrategicBrain(cfg.get('strategic_brain', 'Llama-70B-NV'))
            self.negotiator = TacticalNegotiator(cfg.get('tactical_negotiator', 'Llama-8B-GR'))
        else:
            self.human_manager = HumanSalesManager(cfg.get('strategic_brain', 'Llama-70B-NV'))
            
        self.watchdog = IntegrityWatchdog(cfg.get('integrity_watchdog', 'Llama-8B-GR'))
        self.red_teamer = ChaosInjector(cfg.get('chaos_injector', 'Mixtral-8x7B-GR'))
        self.critic = PostMortemCritic(cfg.get('critic', 'Llama-8B-GR'))
        
        self.blackboard = {
            "inventory": self.inventory,
            "quotes": {i['product_name']: i['selling_price'] for i in self.inventory},
            "floor_prices": {i['product_name']: i['cost_price'] for i in self.inventory},
            "strategy": "Initializing...",
            "logs": [],
            "chaos": [],
            "sales_data": []
        }
        
        self.current_hour = 0
        self.sold_items = []
        self.buyers = []
        self.histories = {}
        
        # ADVANCED BUYER GENERATION
        personalities = ["ESSENTIAL", "CALCULATED", "IMPULSE"]
        for i in range(1, N_BUYERS + 1):
            # Each buyer wants 2-3 items
            shopping_list = random.sample([item['product_name'] for item in self.inventory], k=random.randint(2, 3))
            personality = random.choice(personalities)
            
            # Budget based on the sum of targets + 10%
            total_target_val = sum(next(item['selling_price'] for item in self.inventory if item['product_name'] == name) for name in shopping_list)
            budget = total_target_val * random.uniform(0.9, 1.2)
            
            self.buyers.append(Buyer(i, buyer_model, budget, shopping_list, personality))
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
        title = "THE HIVE | MAS MODE" if self.mode == "MAS" else "HUMAN BASELINE | MANUAL MODE"
        layout["header"].update(Panel(Text(f"{title} | {self.exp_type}", justify="center", style="bold green")))
        
        # Inv
        inv_table = Table(title="Inventory", expand=True)
        inv_table.add_column("Item")
        inv_table.add_column("Quote")
        inv_table.add_column("Exp")
        for item in self.inventory:
            status = "[SOLD]" if item['product_name'] in self.sold_items else f"${self.blackboard['quotes'].get(item['product_name'], 0):.2f}"
            inv_table.add_row(item['product_name'], status, str(item['days_until_expiry']))
        layout["inv"].update(Panel(inv_table, border_style="cyan"))

        # Desk
        desk_text = Text()
        desk_text.append(f"STRATEGY: {self.blackboard['strategy']}\n", style="bold yellow")
        
        # Show LLM Status Logs
        from .llm_client import client
        for s_log in client.status_logs[-2:]:
            desk_text.append(f"{s_log}\n", style="dim cyan")
        
        desk_text.append("\n---\n", style="dim")
        for log in self.blackboard["logs"][-8:]:
            desk_text.append(f"{log}\n")
        layout["desk"].update(Panel(desk_text, title="Sales Desk", border_style="red"))

        # Footer
        profit = sum(s['sale_price'] - s['cost_price'] for s in self.blackboard['sales_data'])
        sold_names = [s['product_name'] for s in self.blackboard['sales_data']]
        waste = sum(i['cost_price'] for i in self.inventory if i['product_name'] not in sold_names)
        layout["footer"].update(Panel(Text(f"Hour: {self.current_hour}/{MAX_HOURS} | Sold: {len(self.sold_items)} | Profit: ${profit:.2f} | Waste: ${waste:.2f}", justify="center")))

    def _record_sale(self, buyer, item_name, price, item_data):
        if item_name not in self.sold_items:
            self.sold_items.append(item_name)
            buyer.purchased_items.append(item_name)
            self.blackboard["sales_data"].append({
                "product_name": item_name,
                "sale_price": price,
                "cost_price": item_data['cost_price'],
                "initial_price": item_data['selling_price'],
                "hour": self.current_hour,
                "days_until_expiry": item_data['days_until_expiry']
            })
            self.blackboard["logs"].append(f"SUCCESS: B{buyer.buyer_id} ({buyer.personality}) bought {item_name} at ${price:.2f}")

    async def _negotiate(self, buyer):
        # Find next unpurchased item from shopping list
        remaining = [i for i in buyer.shopping_list if i not in buyer.purchased_items and i not in self.sold_items]
        if not remaining: return
        
        target_name = remaining[0]
        item_data = next(i for i in self.inventory if i['product_name'] == target_name)
        price = self.blackboard["quotes"].get(target_name, 0)
        floor = self.blackboard["floor_prices"].get(target_name, item_data['cost_price'])
        
        if floor < item_data['cost_price']: floor = item_data['cost_price']
        expiry = item_data['days_until_expiry']
        
        self.blackboard["logs"].append(f"ENGAGING: B{buyer.buyer_id} ({buyer.personality}) for {target_name}...")
        
        truncated_history = self.histories[buyer.buyer_id][-5:]
        b_act = await buyer.act(truncated_history, price, expiry, self.current_hour, MAX_HOURS)
        # Store buyer's response in history for both to see
        self.histories[buyer.buyer_id].append({"role": "user", "content": json.dumps(b_act)})
        
        if b_act.get("action") == "ACCEPT":
            if price >= floor:
                self._record_sale(buyer, target_name, price, item_data)
            else:
                self.blackboard["logs"].append(f"REJECTED: Quote ${price:.2f} < floor ${floor:.2f}")
        elif b_act.get("action") == "COUNTER":
            offer = b_act.get("counter_offer", 0)
            self.blackboard["logs"].append(f"COUNTER: B{buyer.buyer_id} offered ${offer:.2f}")
            
            if offer >= price and offer >= floor:
                self._record_sale(buyer, target_name, offer, item_data)
                return

            if self.mode == "MAS":
                s_act = await self.negotiator.act(buyer.buyer_id, target_name, price, floor, self.blackboard["strategy"], self.current_hour, MAX_HOURS, truncated_history, offer)
            else:
                s_res = await self.human_manager.act(target_name, item_data['cost_price'], price, expiry, truncated_history, self.blackboard["chaos"], self.current_hour, MAX_HOURS)
                s_act = {"action": "ACCEPT" if s_res.get("new_quote", 999) <= offer else "COUNTER", "new_quote": s_res.get("new_quote")}

            if s_act.get("action") == "ACCEPT" and offer >= floor:
                self._record_sale(buyer, target_name, offer, item_data)
            else:
                new_price = s_act.get("new_quote")
                if new_price is None: new_price = price
                
                if new_price < floor: new_price = floor + 0.01
                self.blackboard["quotes"][target_name] = new_price
                self.blackboard["logs"].append(f"SELLER -> B{buyer.buyer_id}: Counter-offer ${new_price:.2f}")
                # Store seller's response in history
                self.histories[buyer.buyer_id].append({"role": "assistant", "content": json.dumps(s_act)})

    async def run(self) -> Dict[str, Any]:
        layout = self.make_layout()
        with Live(layout, refresh_per_second=5, screen=True):
            while self.current_hour < MAX_HOURS and len(self.sold_items) < len(self.inventory):
                self.update_display(layout)
                
                if self.mode == "MAS":
                    if self.current_hour % 4 == 0 or (self.blackboard["logs"] and "SUCCESS" in self.blackboard["logs"][-1]):
                        self.blackboard["logs"].append("HIVE: Analyzing market...")
                        self.update_display(layout)
                        intel = await self.hub.act(self.inventory, [])
                        
                        self.blackboard["logs"].append("HIVE: Formulating strategy...")
                        self.update_display(layout)
                        res = await self.brain.act(intel, self.inventory, self.blackboard["chaos"], self.current_hour, MAX_HOURS)
                        
                        self.blackboard["quotes"] = res.get("quotes", self.blackboard["quotes"])
                        self.blackboard["floor_prices"] = res.get("floor_prices", self.blackboard["floor_prices"])
                        self.blackboard["strategy"] = res.get("strategy_directive", "Normal operations.")
                        
                        await self.watchdog.audit(self.blackboard["strategy"], self.blackboard["quotes"], self.blackboard["chaos"])
                else:
                    self.blackboard["strategy"] = "Human intuition mode."
                
                self.blackboard["logs"].append("HIVE: Engaging active buyers...")
                self.update_display(layout)
                
                for b in self.buyers:
                    await self._negotiate(b)
                    self.update_display(layout)
                    await asyncio.sleep(0.5) 
                
                # Red Teaming
                if random.random() < 0.1:
                    light_state = {"inventory": self.inventory, "strategy": self.blackboard["strategy"]}
                    chaos = await self.red_teamer.act(light_state)
                    self.blackboard["chaos"].append(chaos)

                self.current_hour += SIM_CLOCK_TICK
                self.update_display(layout)
                await asyncio.sleep(1) 

        return {
            "mode": self.mode,
            "status": "FINISHED",
            "sold_count": len(self.sold_items),
            "sold_items": self.sold_items,
            "total_items": len(self.inventory),
            "blackboard": self.blackboard,
            "histories": self.histories,
            "duration": self.current_hour
        }
