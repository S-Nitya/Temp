"""
NeurIPS Environment — AsyncHiveEnvironment

Key changes vs kanishka_src:
1. Buyer reads seller text + persuasion multiplier applied in Python
2. StrategicBrain quote output validated before applying (no more PCR=1.0 bug)
3. ChaosInjector wired to actually slash buyer budgets on MARKET_CRASH
4. LinearDecay mode added as NeurIPS math baseline
5. Pruned: IntelligenceHub removed, IntegrityWatchdog removed
6. Buyer budget constraint enforced in negotiations
"""
import asyncio
import json
import random
from typing import Dict, List, Any, Optional

from .agents import (
    Buyer, StrategicBrain, TacticalOrchestrator, RiskReader,
    Spokesperson, BullDebater, BearDebater, DebateJudge,
    ChaosInjector, MonolithicSeller, DummyStrategicBrain, DummyRiskReader,
)
from .baselines import LinearDecayBaseline
from .config import MAX_HOURS, SIM_CLOCK_TICK, N_BUYERS, NEURIPS_CONFIG, TACTIC_MULTIPLIERS


class AsyncHiveEnvironment:
    def __init__(
        self,
        inventory_data: List[Dict[str, Any]],
        exp_type: str,
        mode: str = "MAS",
        model_map: Dict[str, str] = None,
        buyer_model: str = "Llama-8B-GR",
    ):
        self.inventory = inventory_data
        self.exp_type  = exp_type
        self.mode      = mode

        cfg = model_map if model_map else NEURIPS_CONFIG

        # ── Agent instantiation by mode ──────────────────────────────────────
        if self.mode in ("MAS", "MAS_DEBATE"):
            # Autonomous StrategicBrain (no hardcoded phases)
            self.brain = StrategicBrain(cfg.get("strategic_brain", "Llama-70B-GR"))

            # Micro-negotiation pipeline
            risk_reader  = RiskReader(cfg.get("tactical_negotiator", "Llama-8B-GR"))
            spokesperson = Spokesperson(cfg.get("tactical_negotiator", "Llama-8B-GR"))
            self.orchestrator = TacticalOrchestrator(
                cfg.get("tactical_negotiator", "Llama-8B-GR"), risk_reader, spokesperson
            )

            if self.mode == "MAS_DEBATE":
                self.bull  = BullDebater(cfg.get("strategic_brain", "Llama-70B-GR"))
                self.bear  = BearDebater(cfg.get("strategic_brain", "Llama-70B-GR"))
                self.judge = DebateJudge(cfg.get("strategic_brain", "Llama-70B-GR"))

        elif self.mode == "SINGLE_MODEL":
            self.monolithic_seller = MonolithicSeller(cfg.get("tactical_negotiator", "Llama-8B-GR"))

        elif self.mode == "LINEAR_DECAY":
            self.linear_decay = LinearDecayBaseline()

        elif self.mode == "BASELINE_CSV":
            pass  # No LLMs — fixed retail prices

        # ChaosInjector (wired to buyer budgets in NeurIPS arch)
        self.chaos_injector = ChaosInjector(cfg.get("chaos_injector", "Llama-70B-GR"))

        # ── Blackboard ───────────────────────────────────────────────────────
        self.blackboard = {
            "inventory":       self.inventory,
            "quotes":          {i["product_name"]: i["selling_price"] for i in self.inventory},
            "floor_prices":    {i["product_name"]: i["cost_price"]    for i in self.inventory},
            "strategy":        "Initializing...",
            "logs":            [],
            "chaos":           [],
            "sales_data":      [],
            "persuasion_events": [],  # NEW: tracks language persuasion impacts
        }

        self.current_hour  = 0
        self.sold_items    = []
        self.buyers: List[Buyer] = []
        self.histories:      Dict[int, List] = {}
        self.buyer_targets:  Dict[int, Optional[str]] = {}

        # ── Buyer generation ─────────────────────────────────────────────────
        personalities = ["ESSENTIAL", "CALCULATED", "IMPULSE"]
        for i in range(1, N_BUYERS + 1):
            shopping_list = random.sample(
                [item["product_name"] for item in self.inventory],
                k=random.randint(2, 3),
            )
            personality = random.choice(personalities)
            total_val   = sum(
                next(item["selling_price"] for item in self.inventory if item["product_name"] == n)
                for n in shopping_list
            )
            budget = total_val * random.uniform(0.9, 1.2)
            self.buyers.append(Buyer(i, buyer_model, budget, shopping_list, personality))
            self.histories[i]      = []
            self.buyer_targets[i]  = None

    # ─── Sale recording ───────────────────────────────────────────────────────

    def _record_sale(self, buyer: Buyer, item_name: str, price: float, item_data: Dict):
        if item_name not in self.sold_items:
            self.sold_items.append(item_name)
            buyer.purchased_items.append(item_name)
            self.blackboard["sales_data"].append({
                "product_name":     item_name,
                "sale_price":       price,
                "cost_price":       item_data["cost_price"],
                "initial_price":    item_data["selling_price"],
                "hour":             self.current_hour,
                "days_until_expiry": item_data["days_until_expiry"],
            })
            self.blackboard["logs"].append(
                f"SALE: B{buyer.buyer_id} ({buyer.personality}) bought {item_name} at ${price:.2f}"
            )

    # ─── Negotiation logic ────────────────────────────────────────────────────

    async def _negotiate(self, buyer: Buyer):
        remaining = [
            i for i in buyer.shopping_list
            if i not in buyer.purchased_items and i not in self.sold_items
        ]
        if not remaining:
            return

        target_name = remaining[0]
        item_data   = next(i for i in self.inventory if i["product_name"] == target_name)
        price       = self.blackboard["quotes"].get(target_name, item_data["selling_price"])
        floor       = self.blackboard["floor_prices"].get(target_name, item_data["cost_price"])
        retail_price = item_data["selling_price"]

        # Enforce floor >= cost_price
        floor = max(floor, item_data["cost_price"])

        # Reset history when buyer moves to a new item
        if self.buyer_targets.get(buyer.buyer_id) != target_name:
            self.histories[buyer.buyer_id] = []
            self.buyer_targets[buyer.buyer_id] = target_name

        truncated_history = self.histories[buyer.buyer_id][-5:]

        # ── Extract seller's last message for persuasion evaluation ──────────
        seller_last_message = ""
        for msg in reversed(truncated_history):
            if msg["role"] == "assistant":
                try:
                    parsed = json.loads(msg["content"])
                    seller_last_message = parsed.get("message", "")
                except Exception:
                    pass
                break

        # ── Buyer acts (with seller text context) ────────────────────────────
        b_act = await buyer.act(
            truncated_history, price, item_data["days_until_expiry"],
            self.current_hour, MAX_HOURS, retail_price, seller_last_message,
        )
        self.histories[buyer.buyer_id].append({"role": "user", "content": json.dumps(b_act)})

        # ── Apply persuasion multiplier (Python math, not LLM) ───────────────
        tactic          = b_act.get("seller_tactic_detected", "none")
        if tactic not in TACTIC_MULTIPLIERS:
            tactic = "none"
        persuasion_mult = TACTIC_MULTIPLIERS[tactic]
        desperation     = self.current_hour / MAX_HOURS
        base_max        = retail_price * (1.0 + 0.3 + 0.3 * desperation)
        adjusted_max    = round(base_max * persuasion_mult, 2)

        if tactic != "none":
            event = f"PERSUASION: B{buyer.buyer_id} classified tactic='{tactic}' → ceiling ${base_max:.2f} → ${adjusted_max:.2f} (+{(persuasion_mult-1)*100:.0f}%)"
            self.blackboard["persuasion_events"].append(event)
            self.blackboard["logs"].append(event)

        # ── Process buyer action ─────────────────────────────────────────────
        action = b_act.get("action")

        if action == "ACCEPT":
            if price >= floor and price <= adjusted_max:
                self._record_sale(buyer, target_name, price, item_data)

        elif action == "COUNTER":
            offer = b_act.get("counter_offer", 0)

            # Sanity cap: if buyer LLM hallucinates above 2x retail, clamp to adjusted_max
            if not isinstance(offer, (int, float)):
                offer = 0.0
            offer = min(float(offer), retail_price * 2.0, adjusted_max)

            # If offer meets or exceeds ask → deal
            if offer >= price and offer >= floor:
                self._record_sale(buyer, target_name, offer, item_data)
                return

            # Seller responds
            if self.mode in ("MAS", "MAS_DEBATE"):
                s_act = await self.orchestrator.act(
                    buyer.buyer_id, target_name, price, floor,
                    self.blackboard["strategy"], self.current_hour, MAX_HOURS,
                    truncated_history, offer,
                )
            elif self.mode == "SINGLE_MODEL":
                s_act = await self.monolithic_seller.act(
                    buyer.buyer_id, target_name, price,
                    item_data["cost_price"], retail_price,
                    self.current_hour, MAX_HOURS, truncated_history, offer,
                )
            elif self.mode == "LINEAR_DECAY":
                s_act = self.linear_decay.respond_to_offer(
                    item_data, offer, self.current_hour, MAX_HOURS
                )
            elif self.mode == "BASELINE_CSV":
                if offer >= retail_price:
                    s_act = {"action": "ACCEPT", "new_quote": retail_price, "message": ""}
                else:
                    s_act = {"action": "COUNTER", "new_quote": retail_price,
                             "message": f"Fixed price: ${retail_price:.2f}."}

            # Apply seller response
            if s_act.get("action") == "ACCEPT" and offer >= floor:
                self._record_sale(buyer, target_name, offer, item_data)
            else:
                new_price = s_act.get("new_quote", price)
                if not isinstance(new_price, (int, float)):
                    new_price = price
                new_price = max(floor + 0.01, float(new_price))
                self.blackboard["quotes"][target_name] = new_price
                self.histories[buyer.buyer_id].append(
                    {"role": "assistant", "content": json.dumps(s_act)}
                )

    # ─── Main simulation loop ─────────────────────────────────────────────────

    async def run(self):
        print(f"--- Starting [{self.mode}] {self.exp_type} ---", flush=True)

        while self.current_hour < MAX_HOURS and len(self.sold_items) < len(self.inventory):
            if self.current_hour % 2 == 0:
                print(f"[{self.exp_type}] Hour {self.current_hour}/{MAX_HOURS} | Sold: {len(self.sold_items)}", flush=True)

            # ── Strategic pricing update (MAS modes only) ─────────────────────
            if self.mode in ("MAS", "MAS_DEBATE"):
                if self.current_hour % 4 == 0 or (
                    self.blackboard["logs"] and "SALE" in self.blackboard["logs"][-1]
                ):
                    res = await self.brain.act(
                        self.inventory, self.blackboard["chaos"],
                        self.current_hour, MAX_HOURS,
                    )

                    # Validated quote application — only accept real product name keys
                    valid_names = {i["product_name"] for i in self.inventory}
                    new_quotes  = {k: float(v) for k, v in res.get("quotes", {}).items()
                                   if k in valid_names and isinstance(v, (int, float))}
                    new_floors  = {k: float(v) for k, v in res.get("floor_prices", {}).items()
                                   if k in valid_names and isinstance(v, (int, float))}
                    if new_quotes:
                        self.blackboard["quotes"].update(new_quotes)
                    if new_floors:
                        self.blackboard["floor_prices"].update(new_floors)
                    self.blackboard["strategy"] = res.get("strategy_directive", "Autonomous strategy.")

                    if self.mode == "MAS_DEBATE":
                        bull_res, bear_res = await asyncio.gather(
                            self.bull.act(self.inventory, self.blackboard["quotes"],
                                          self.current_hour, MAX_HOURS),
                            self.bear.act(self.inventory, self.blackboard["quotes"],
                                          self.current_hour, MAX_HOURS),
                        )
                        final = await self.judge.act(
                            self.blackboard["quotes"], self.blackboard["floor_prices"],
                            bull_res, bear_res, self.inventory,
                        )
                        debate_quotes  = {k: float(v) for k, v in final.get("final_quotes", {}).items()
                                          if k in valid_names and isinstance(v, (int, float))}
                        debate_floors  = {k: float(v) for k, v in final.get("final_floor_prices", {}).items()
                                          if k in valid_names and isinstance(v, (int, float))}
                        if debate_quotes:
                            self.blackboard["quotes"].update(debate_quotes)
                        if debate_floors:
                            self.blackboard["floor_prices"].update(debate_floors)
                        self.blackboard["strategy"] += " [DEBATE MODIFIED]"

            elif self.mode == "LINEAR_DECAY":
                # Update quotes each hour based on decay formula
                for item in self.inventory:
                    if item["product_name"] not in self.sold_items:
                        self.blackboard["quotes"][item["product_name"]] = \
                            self.linear_decay.get_quote(item, self.current_hour, MAX_HOURS)
                        self.blackboard["floor_prices"][item["product_name"]] = \
                            self.linear_decay.get_floor(item)
                self.blackboard["strategy"] = "Linear decay pricing (OR baseline)"

            elif self.mode == "BASELINE_CSV":
                self.blackboard["quotes"] = {i["product_name"]: i["selling_price"] for i in self.inventory}
                self.blackboard["strategy"] = "Fixed CSV retail prices"

            # ── Buyer negotiations ────────────────────────────────────────────
            for b in self.buyers:
                await self._negotiate(b)
                await asyncio.sleep(0.4)

            # ── ChaosInjector (10% chance per hour) — WIRED to buyer budgets ──
            if random.random() < 0.10:
                light_state = {"inventory": self.inventory, "strategy": self.blackboard["strategy"]}
                chaos = await self.chaos_injector.act(light_state)
                self.blackboard["chaos"].append(chaos)

                # MARKET_CRASH → actually slash buyer budgets
                if chaos.get("event") == "MARKET_CRASH":
                    magnitude = min(10, max(1, chaos.get("impact_magnitude", 5))) / 10.0
                    slash_pct = 0.40 * magnitude
                    for buyer in self.buyers:
                        buyer.budget = round(buyer.budget * (1.0 - slash_pct), 2)
                    msg = f"CHAOS: MARKET_CRASH (magnitude {magnitude*10:.0f}/10) -> buyer budgets slashed {slash_pct*100:.0f}%"
                    self.blackboard["logs"].append(msg)
                    print(f"  [CHAOS] {msg}", flush=True)

            self.current_hour += SIM_CLOCK_TICK
            await asyncio.sleep(0.8)

            yield {
                "mode": self.mode, "status": "RUNNING",
                "sold_count": len(self.sold_items), "sold_items": self.sold_items,
                "total_items": len(self.inventory), "blackboard": self.blackboard,
                "histories": self.histories, "duration": self.current_hour,
            }

        yield {
            "mode": self.mode, "status": "FINISHED",
            "sold_count": len(self.sold_items), "sold_items": self.sold_items,
            "total_items": len(self.inventory), "blackboard": self.blackboard,
            "histories": self.histories, "duration": self.current_hour,
        }
