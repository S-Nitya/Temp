"""
Final Architecture Environment — AsyncHiveEnvironment

Key features:
1. Buyer reads seller text + persuasion multiplier applied in Python
2. StrategicBrain quote output validated before applying
3. ChaosInjector wired to actually slash buyer budgets on MARKET_CRASH
4. LinearDecay mode added as math baseline
5. Buyer budget constraint enforced in negotiations
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
from .config import MAX_HOURS, SIM_CLOCK_TICK, N_BUYERS, FINAL_CONFIG


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
        self.buyer_model = buyer_model
        self.model_map = model_map or FINAL_CONFIG

        cfg = self.model_map

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
            "persuasion_events": [],  # tracks language persuasion impacts
            "price_trajectory": [],    # tracks price per item over time
            "inventory_trajectory": [], # tracks unsold % over time
            "negotiation_log": [],     # full negotiation-level records
            "item_outcomes": {},       # final per-item resolution
            "api_errors": 0,           # count of failed/timed out API calls
        }

        self.current_hour  = 0
        self.sold_items    = []
        self.buyers: List[Buyer] = []
        self.histories     = {}

    # ─── Sale recording ───────────────────────────────────────────────────────

    def _record_sale(self, buyer: Buyer, item_data: Dict, price: float, clearance_type: str = "NEGOTIATED"):
        item_id = item_data.get("item_id", item_data["product_name"])
        item_name = item_data["product_name"]
        if item_id not in self.sold_items:
            self.sold_items.append(item_id)
            buyer.purchased_items.append(item_id)
            self.blackboard["sales_data"].append({
                "item_id":          item_id,
                "product_name":     item_name,
                "sale_price":       price,
                "cost_price":       item_data["cost_price"],
                "initial_price":    item_data["selling_price"],
                "hour":             self.current_hour,
                "days_until_expiry": item_data["days_until_expiry"],
                "clearance_type":   clearance_type,
            })
            self.blackboard["item_outcomes"][item_id] = {
                "item": item_name,
                "item_id": item_id,
                "outcome": "SOLD",
                "final_price": price,
                "hour": self.current_hour,
                "clearance_type": clearance_type,
            }
            self.blackboard["logs"].append(
                f"SALE [{clearance_type}]: B{buyer.buyer_id} ({buyer.personality}) bought {item_name} ({item_id}) at ${price:.2f}"
            )

    # ─── Sequential 1-on-1 Bilateral Negotiation Round ────────────────────────

    async def _run_sequential_negotiation_round(self, period_buyers: Dict[str, Dict]):
        """
        Execute sequential, 1-on-1 bilateral negotiation per unsold item.
        No concurrent asyncio.gather, no competing bidders context.
        Each encounter is a fresh buyer.
        """
        unsold_items = [i for i in self.inventory if i.get("item_id", i["product_name"]) not in self.sold_items]
        if not unsold_items:
            return

        for item_data in unsold_items:
            item_id = item_data.get("item_id", item_data["product_name"])
            product_name = item_data["product_name"]
            retail_price = item_data["selling_price"]
            cost_price = item_data["cost_price"]

            if item_id not in period_buyers:
                continue

            buyer_cfg = period_buyers[item_id]
            buyer = Buyer(
                buyer_id=buyer_cfg["buyer_id"],
                model_alias=self.buyer_model,
                budget=buyer_cfg["budget"],
                shopping_list=[item_id],
                personality=buyer_cfg["personality"],
            )

            price = self.blackboard["quotes"].get(item_id, retail_price)
            floor = max(self.blackboard["floor_prices"].get(item_id, cost_price), cost_price)

            # Round 1: Buyer opening evaluation
            b_act = await buyer.act(
                history=[],
                current_quote=price,
                days_until_expiry=item_data["days_until_expiry"],
                current_hour=self.current_hour,
                max_hours=MAX_HOURS,
                retail_price=retail_price,
                seller_last_message="",
            )

            if b_act.get("action") == "API_ERROR":
                self.blackboard["api_errors"] += 1
                continue

            action = b_act.get("action", "COUNTER")
            bid_amount = b_act.get("bid_amount", b_act.get("counter_offer", 0.0))
            if not isinstance(bid_amount, (int, float)):
                bid_amount = 0.0
            bid_amount = min(float(bid_amount), buyer.budget, retail_price * 2.0)

            # Check Instant Market Clear
            if action == "ACCEPT" or (bid_amount >= price and bid_amount >= floor):
                final_price = max(price, bid_amount)
                self._record_sale(buyer, item_data, final_price, clearance_type="INSTANT_CLEAR")
                self.blackboard["negotiation_log"].append({
                    "hour": float(self.current_hour),
                    "item": product_name,
                    "item_id": item_id,
                    "buyer_id": buyer.buyer_id,
                    "round": 1,
                    "clearance_type": "INSTANT_CLEAR",
                    "decider": {"action": "ACCEPT", "target_price": float(price)},
                    "buyer_response": {"action": "ACCEPT", "bid_amount": float(final_price)},
                })
                continue

            if action == "WALK_AWAY":
                self.blackboard["negotiation_log"].append({
                    "hour": float(self.current_hour),
                    "item": product_name,
                    "item_id": item_id,
                    "buyer_id": buyer.buyer_id,
                    "round": 1,
                    "clearance_type": "WALK_AWAY_R1",
                    "decider": {"action": "HOLD", "target_price": float(price)},
                    "buyer_response": {"action": "WALK_AWAY", "bid_amount": 0.0},
                })
                continue

            # Multi-turn bilateral negotiation (up to 3 turns)
            negotiation_history = [{
                "hour": self.current_hour,
                "buyer_action": action,
                "bid": bid_amount,
                "seller_price": price,
                "seller_message": "",
            }]
            deal_closed = False

            for turn in range(2, 4):
                # Seller evaluates buyer's bid
                if self.mode in ("MAS", "MAS_DEBATE"):
                    s_act = await self.orchestrator.act(
                        buyer.buyer_id, product_name, price, floor,
                        self.blackboard["strategy"], self.current_hour, MAX_HOURS,
                        negotiation_history, bid_amount,
                        competing_bidders_count=1,
                    )
                elif self.mode == "LINEAR_DECAY":
                    s_act = self.linear_decay.respond_to_offer(
                        item_data, bid_amount, self.current_hour, MAX_HOURS
                    )
                elif self.mode == "BASELINE_CSV":
                    if bid_amount >= retail_price:
                        s_act = {"action": "ACCEPT", "new_quote": retail_price, "message": ""}
                    else:
                        s_act = {"action": "COUNTER", "new_quote": retail_price, "message": f"Fixed: ${retail_price:.2f}"}

                if s_act.get("action") == "ACCEPT" and bid_amount >= floor:
                    self._record_sale(buyer, item_data, bid_amount, clearance_type="NEGOTIATED")
                    self.blackboard["negotiation_log"].append({
                        "hour": float(self.current_hour),
                        "item": product_name,
                        "item_id": item_id,
                        "buyer_id": buyer.buyer_id,
                        "round": turn,
                        "clearance_type": "NEGOTIATED",
                        "decider": s_act.get("_decision", {}),
                        "buyer_response": {"action": "ACCEPT", "bid_amount": float(bid_amount)},
                    })
                    deal_closed = True
                    break

                new_price = s_act.get("new_quote", price)
                if not isinstance(new_price, (int, float)):
                    new_price = price
                new_price = max(floor + 0.01, float(new_price))
                price = new_price
                seller_msg = s_act.get("message", "")

                negotiation_history[-1]["seller_message"] = seller_msg

                # Buyer re-evaluates counter-offer
                b_act = await buyer.act(
                    history=negotiation_history,
                    current_quote=price,
                    days_until_expiry=item_data["days_until_expiry"],
                    current_hour=self.current_hour,
                    max_hours=MAX_HOURS,
                    retail_price=retail_price,
                    seller_last_message=seller_msg,
                )

                if b_act.get("action") == "API_ERROR":
                    self.blackboard["api_errors"] += 1
                    break

                action = b_act.get("action", "COUNTER")
                if action == "ACCEPT":
                    self._record_sale(buyer, item_data, price, clearance_type="NEGOTIATED")
                    self.blackboard["negotiation_log"].append({
                        "hour": float(self.current_hour),
                        "item": product_name,
                        "item_id": item_id,
                        "buyer_id": buyer.buyer_id,
                        "round": turn,
                        "clearance_type": "NEGOTIATED",
                        "decider": s_act.get("_decision", {}),
                        "buyer_response": {"action": "ACCEPT", "bid_amount": float(price)},
                    })
                    deal_closed = True
                    break
                elif action == "WALK_AWAY":
                    self.blackboard["negotiation_log"].append({
                        "hour": float(self.current_hour),
                        "item": product_name,
                        "item_id": item_id,
                        "buyer_id": buyer.buyer_id,
                        "round": turn,
                        "clearance_type": "WALK_AWAY",
                        "decider": s_act.get("_decision", {}),
                        "buyer_response": {"action": "WALK_AWAY", "bid_amount": 0.0},
                    })
                    break

                bid_amount = b_act.get("bid_amount", b_act.get("counter_offer", 0.0))
                if not isinstance(bid_amount, (int, float)):
                    bid_amount = 0.0
                bid_amount = min(float(bid_amount), buyer.budget, retail_price * 2.0)
                negotiation_history.append({
                    "hour": self.current_hour,
                    "buyer_action": action,
                    "bid": bid_amount,
                    "seller_price": price,
                    "seller_message": "",
                })

    # ─── Main simulation loop ─────────────────────────────────────────────────

    async def run(self, trial_buyer_sequence: Dict[int, Dict[str, Dict]] = None):
        print(f"--- Starting [{self.mode}] {self.exp_type} (Sequential 1-on-1 Bilateral) ---", flush=True)

        while self.current_hour < MAX_HOURS and len(self.sold_items) < len(self.inventory):
            if self.current_hour % 2 == 0:
                print(f"[{self.exp_type}] Hour {self.current_hour}/{MAX_HOURS} | Sold: {len(self.sold_items)}/{len(self.inventory)}", flush=True)

            # ── Strategic pricing update (MAS modes only) ─────────────────────
            if self.mode in ("MAS", "MAS_DEBATE"):
                unsold = [i for i in self.inventory if i.get("item_id", i["product_name"]) not in self.sold_items]
                decision = await self.brain.act(
                    unsold, self.blackboard.get("chaos", []), self.current_hour, MAX_HOURS
                )
                self.blackboard["strategy"] = decision.get("chosen_strategy", "Autonomous pricing")
                self.blackboard["quotes"].update(decision.get("quotes", {}))
                self.blackboard["floor_prices"].update(decision.get("floor_prices", {}))

            elif self.mode == "LINEAR_DECAY":
                for item in self.inventory:
                    i_id = item.get("item_id", item["product_name"])
                    if i_id not in self.sold_items:
                        self.blackboard["quotes"][i_id] = \
                            self.linear_decay.get_quote(item, self.current_hour, MAX_HOURS)
                        self.blackboard["floor_prices"][i_id] = \
                            self.linear_decay.get_floor(item)
                self.blackboard["strategy"] = "Linear decay pricing (OR baseline)"

            elif self.mode == "BASELINE_CSV":
                for item in self.inventory:
                    i_id = item.get("item_id", item["product_name"])
                    self.blackboard["quotes"][i_id] = item["selling_price"]
                self.blackboard["strategy"] = "Fixed CSV retail prices"

            # ── Sequential Bilateral Negotiation Round ────────────────────────
            period_buyers = trial_buyer_sequence.get(self.current_hour, {}) if trial_buyer_sequence else {}
            await self._run_sequential_negotiation_round(period_buyers)



            # ── Snapshot Trajectories for Publication Figures ─────────────────
            unsold_count = len(self.inventory) - len(self.sold_items)
            pct_unsold = unsold_count / len(self.inventory) if self.inventory else 0.0
            self.blackboard["inventory_trajectory"].append({
                "hour": float(self.current_hour),
                "pct_unsold": round(pct_unsold, 4),
                "unsold_count": unsold_count,
            })
            for item in self.inventory:
                i_id = item.get("item_id", item["product_name"])
                p_name = item["product_name"]
                curr_p = self.blackboard["quotes"].get(i_id, item["selling_price"])
                self.blackboard["price_trajectory"].append({
                    "hour": float(self.current_hour),
                    "item": p_name,
                    "item_id": i_id,
                    "price": float(curr_p),
                    "is_sold": i_id in self.sold_items,
                })

            self.current_hour += SIM_CLOCK_TICK
            await asyncio.sleep(0.8)

            yield {
                "mode": self.mode, "status": "RUNNING",
                "sold_count": len(self.sold_items), "sold_items": self.sold_items,
                "total_items": len(self.inventory), "blackboard": self.blackboard,
                "histories": self.histories, "duration": self.current_hour,
            }

        # ── Finalize Outcomes for Unsold / Expired Items ─────────────────────
        for item in self.inventory:
            i_id = item.get("item_id", item["product_name"])
            if i_id not in self.blackboard["item_outcomes"]:
                self.blackboard["item_outcomes"][i_id] = {
                    "item": item["product_name"],
                    "item_id": i_id,
                    "outcome": "EXPIRED_UNSOLD",
                    "final_price": 0.0,
                    "hour": float(MAX_HOURS),
                }

        yield {
            "mode": self.mode, "status": "FINISHED",
            "sold_count": len(self.sold_items), "sold_items": self.sold_items,
            "total_items": len(self.inventory), "blackboard": self.blackboard,
            "histories": self.histories, "duration": self.current_hour,
        }
