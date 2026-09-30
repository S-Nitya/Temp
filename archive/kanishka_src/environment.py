import asyncio
import time
import random
import json
from typing import Dict, List, Any

from .agents import (
    Buyer, IntelligenceHub, StrategicBrain, TacticalOrchestrator, RiskReader, Spokesperson,
    BullDebater, BearDebater, DebateJudge,
    IntegrityWatchdog, ChaosInjector, PostMortemCritic, MonolithicSeller
)
from .config import MAX_HOURS, SIM_CLOCK_TICK, N_BUYERS, HIVE_CONFIG

class AsyncHiveEnvironment:
    def __init__(self, inventory_data: List[Dict[str, Any]], exp_type: str, mode: str = "MAS", model_map: Dict[str, str] = None, buyer_model: str = "Llama-8B-GR"):
        self.inventory = inventory_data
        self.exp_type = exp_type
        self.mode = mode
        
        cfg = model_map if model_map else HIVE_CONFIG
        if self.mode in ["MAS", "MAS_DEBATE"]:
            self.hub = IntelligenceHub(cfg.get('intelligence_hub', 'Llama-8B-GR'))
            self.brain = StrategicBrain(cfg.get('strategic_brain', 'Llama-70B-NV'))
            
            # DEBATE LOOP
            self.bull = BullDebater(cfg.get('strategic_brain', 'Llama-70B-NV'))
            self.bear = BearDebater(cfg.get('strategic_brain', 'Llama-70B-NV'))
            self.judge = DebateJudge(cfg.get('strategic_brain', 'Llama-70B-NV'))
            
            # KANISHKA'S MICRO-NEGOTIATION ENGINE
            risk_reader = RiskReader(cfg.get('tactical_negotiator', 'Llama-8B-GR'))
            spokesperson = Spokesperson(cfg.get('tactical_negotiator', 'Llama-8B-GR'))
            self.orchestrator = TacticalOrchestrator(cfg.get('tactical_negotiator', 'Llama-8B-GR'), risk_reader, spokesperson)
        elif self.mode == "SINGLE_MODEL":
            # PURE SINGLE MODEL (no architecture, no hub, no brain)
            self.monolithic_seller = MonolithicSeller(cfg.get('tactical_negotiator', 'Llama-8B-GR'))
        elif self.mode == "BASELINE_CSV":
            # NAIVE BASELINE: Fixed prices from CSV. No LLMs at all.
            pass
            
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
        self.buyer_targets = {}  # FIX: Track each buyer's current target to reset history on target change
        
        # ADVANCED BUYER GENERATION
        personalities = ["ESSENTIAL", "CALCULATED", "IMPULSE"]
        for i in range(1, N_BUYERS + 1):
            shopping_list = random.sample([item['product_name'] for item in self.inventory], k=random.randint(2, 3))
            personality = random.choice(personalities)
            
            total_target_val = sum(next(item['selling_price'] for item in self.inventory if item['product_name'] == name) for name in shopping_list)
            budget = total_target_val * random.uniform(0.9, 1.2)
            
            self.buyers.append(Buyer(i, buyer_model, budget, shopping_list, personality))
            self.histories[i] = []
            self.buyer_targets[i] = None

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
        remaining = [i for i in buyer.shopping_list if i not in buyer.purchased_items and i not in self.sold_items]
        if not remaining: return
        
        target_name = remaining[0]
        item_data = next(i for i in self.inventory if i['product_name'] == target_name)
        price = self.blackboard["quotes"].get(target_name, 0)
        floor = self.blackboard["floor_prices"].get(target_name, item_data['cost_price'])
        retail_price = item_data['selling_price']
        
        if floor < item_data['cost_price']: floor = item_data['cost_price']
        expiry = item_data['days_until_expiry']
        
        # FIX 1: Reset conversation history when buyer's target item changes
        if self.buyer_targets.get(buyer.buyer_id) != target_name:
            self.histories[buyer.buyer_id] = []
            self.buyer_targets[buyer.buyer_id] = target_name
        
        truncated_history = self.histories[buyer.buyer_id][-5:]
        b_act = await buyer.act(truncated_history, price, expiry, self.current_hour, MAX_HOURS, retail_price)
        self.histories[buyer.buyer_id].append({"role": "user", "content": json.dumps(b_act)})
        
        if b_act.get("action") == "ACCEPT":
            if price >= floor:
                self._record_sale(buyer, target_name, price, item_data)
        elif b_act.get("action") == "COUNTER":
            offer = b_act.get("counter_offer", 0)
            
            # FIX 2: Hard environment-side cap — reject any offer > 2x retail (buyer LLM gone rogue)
            if isinstance(offer, (int, float)) and offer > retail_price * 2.0:
                self.blackboard["logs"].append(f"REJECTED: B{buyer.buyer_id} offered ${offer:.2f} for {target_name} (retail: ${retail_price:.2f}) — irrational offer blocked")
                return
            
            if offer >= price and offer >= floor:
                self._record_sale(buyer, target_name, offer, item_data)
                return

            if self.mode in ["MAS", "MAS_DEBATE"]:
                s_act = await self.orchestrator.act(buyer.buyer_id, target_name, price, floor, self.blackboard["strategy"], self.current_hour, MAX_HOURS, truncated_history, offer)
            elif self.mode == "SINGLE_MODEL":
                s_act = await self.monolithic_seller.act(buyer.buyer_id, target_name, price, item_data['cost_price'], retail_price, self.current_hour, MAX_HOURS, truncated_history, offer)
            elif self.mode == "BASELINE_CSV":
                # Static pricing: Accept if buyer meets retail price, else counter with retail price.
                if offer >= retail_price:
                    s_act = {"action": "ACCEPT"}
                else:
                    s_act = {"action": "COUNTER", "new_quote": retail_price, "message": f"The price is fixed at ${retail_price:.2f}. Take it or leave it."}

            if s_act.get("action") == "ACCEPT" and offer >= floor:
                self._record_sale(buyer, target_name, offer, item_data)
            else:
                new_price = s_act.get("new_quote")
                if new_price is None: new_price = price
                
                if new_price < floor: new_price = floor + 0.01
                self.blackboard["quotes"][target_name] = new_price
                self.histories[buyer.buyer_id].append({"role": "assistant", "content": json.dumps(s_act)})

    async def run(self) -> Dict[str, Any]:
        print(f"--- Starting simulation {self.exp_type} ---", flush=True)
        while self.current_hour < MAX_HOURS and len(self.sold_items) < len(self.inventory):
            if self.current_hour % 2 == 0:
                print(f"[{self.exp_type}] Hour: {self.current_hour}/{MAX_HOURS} | Sold: {len(self.sold_items)}", flush=True)
            
            if self.mode in ["MAS", "MAS_DEBATE"]:
                if self.current_hour % 4 == 0 or (self.blackboard["logs"] and "SUCCESS" in self.blackboard["logs"][-1]):
                    intel = await self.hub.act(self.inventory, [])
                    res = await self.brain.act(intel, self.inventory, self.blackboard["chaos"], self.current_hour, MAX_HOURS)
                    
                    valid_names = {i['product_name'] for i in self.inventory}
                    new_quotes = {k: float(v) for k, v in res.get("quotes", {}).items() if k in valid_names and isinstance(v, (int, float))}
                    new_floors = {k: float(v) for k, v in res.get("floor_prices", {}).items() if k in valid_names and isinstance(v, (int, float))}
                    if new_quotes:
                        self.blackboard["quotes"].update(new_quotes)
                    if new_floors:
                        self.blackboard["floor_prices"].update(new_floors)
                    self.blackboard["strategy"] = res.get("strategy_directive", "Normal operations.")
                    
                    if self.mode == "MAS_DEBATE":
                        bull_res, bear_res = await asyncio.gather(
                            self.bull.act(intel, self.inventory, self.blackboard["quotes"], self.current_hour, MAX_HOURS),
                            self.bear.act(intel, self.inventory, self.blackboard["quotes"], self.current_hour, MAX_HOURS)
                        )
                        final_res = await self.judge.act(self.blackboard["quotes"], self.blackboard["floor_prices"], bull_res, bear_res, self.inventory)
                        self.blackboard["quotes"] = final_res.get("final_quotes", self.blackboard["quotes"])
                        self.blackboard["floor_prices"] = final_res.get("final_floor_prices", self.blackboard["floor_prices"])
                        self.blackboard["strategy"] += " [DEBATE MODIFIED]"

                    await self.watchdog.audit(self.blackboard["strategy"], self.blackboard["quotes"], self.blackboard["chaos"])
            elif self.mode == "SINGLE_MODEL":
                self.blackboard["strategy"] = "Single monolithic LLM."
            elif self.mode == "BASELINE_CSV":
                self.blackboard["strategy"] = "Fixed CSV prices."
                # Ensure quotes remain at retail price
                self.blackboard["quotes"] = {i['product_name']: i['selling_price'] for i in self.inventory}
            
            for b in self.buyers:
                await self._negotiate(b)
                await asyncio.sleep(0.5) 
            
            if random.random() < 0.1:
                light_state = {"inventory": self.inventory, "strategy": self.blackboard["strategy"]}
                chaos = await self.red_teamer.act(light_state)
                self.blackboard["chaos"].append(chaos)

            self.current_hour += SIM_CLOCK_TICK
            await asyncio.sleep(1.0) 
            
            yield {
                "mode": self.mode,
                "status": "RUNNING",
                "sold_count": len(self.sold_items),
                "sold_items": self.sold_items,
                "total_items": len(self.inventory),
                "blackboard": self.blackboard,
                "histories": self.histories,
                "duration": self.current_hour
            }

        yield {
            "mode": self.mode,
            "status": "FINISHED",
            "sold_count": len(self.sold_items),
            "sold_items": self.sold_items,
            "total_items": len(self.inventory),
            "blackboard": self.blackboard,
            "histories": self.histories,
            "duration": self.current_hour
        }
