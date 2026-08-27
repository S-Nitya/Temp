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

        cfg = model_map if model_map else FINAL_CONFIG

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
                [item.get("item_id", item["product_name"]) for item in self.inventory],
                k=random.randint(2, 3),
            )
            personality = random.choice(personalities)
            total_val   = sum(
                next(item["selling_price"] for item in self.inventory if item.get("item_id", item["product_name"]) == n)
                for n in shopping_list
            )
            budget = total_val * random.uniform(0.9, 1.2)
            self.buyers.append(Buyer(i, buyer_model, budget, shopping_list, personality))
            self.histories[i]      = []
            self.buyer_targets[i]  = None

    # ─── Sale recording ───────────────────────────────────────────────────────

    def _record_sale(self, buyer: Buyer, item_data: Dict, price: float):
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
            })
            self.blackboard["item_outcomes"][item_id] = {
                "item": item_name,
                "item_id": item_id,
                "outcome": "SOLD",
                "final_price": price,
                "hour": self.current_hour,
            }
            self.blackboard["logs"].append(
                f"SALE: B{buyer.buyer_id} ({buyer.personality}) bought {item_name} ({item_id}) at ${price:.2f}"
            )

    # ─── Concurrent Double-Auction Bidding & Settlement ───────────────────────

    async def _get_buyer_bid(self, buyer: Buyer, unsold_items: List[Dict]) -> Optional[Dict[str, Any]]:
        unsold_ids = {u.get("item_id", u["product_name"]) for u in unsold_items}
        remaining = [
            i for i in buyer.shopping_list
            if i not in buyer.purchased_items and i in unsold_ids
        ]
        if not remaining:
            return None

        target_id = remaining[0]
        item_data = next(i for i in self.inventory if i.get("item_id", i["product_name"]) == target_id)
        target_name = item_data["product_name"]
        price       = self.blackboard["quotes"].get(target_id, item_data["selling_price"])
        retail_price = item_data["selling_price"]

        # Reset history when buyer switches target item
        if self.buyer_targets.get(buyer.buyer_id) != target_id:
            self.histories[buyer.buyer_id] = []
            self.buyer_targets[buyer.buyer_id] = target_id

        truncated_history = self.histories[buyer.buyer_id][-5:]
        seller_last_message = ""
        for msg in reversed(truncated_history):
            if msg["role"] == "assistant":
                try:
                    parsed = json.loads(msg["content"])
                    seller_last_message = parsed.get("message", "")
                except Exception:
                    pass
                break

        # Buyer generates bid via CoT utility
        b_act = await buyer.act(
            truncated_history, price, item_data["days_until_expiry"],
            self.current_hour, MAX_HOURS, retail_price, seller_last_message,
        )
        self.histories[buyer.buyer_id].append({"role": "user", "content": json.dumps(b_act)})

        # Track Natural Persuasion
        perceived_v = float(b_act.get("perceived_value_V", retail_price))
        if perceived_v > retail_price:
            shift_pct = ((perceived_v - retail_price) / retail_price) * 100
            event = f"NATURAL PERSUASION: B{buyer.buyer_id} ({buyer.personality}) updated V from ${retail_price:.2f} -> ${perceived_v:.2f} (+{shift_pct:.1f}%)"
            self.blackboard["persuasion_events"].append(event)
            self.blackboard["logs"].append(event)

        action = b_act.get("action", "COUNTER")
        if action == "ACCEPT":
            offer = price
        else:
            offer = b_act.get("counter_offer", 0.0)

        if not isinstance(offer, (int, float)):
            offer = 0.0
        offer = min(float(offer), buyer.budget, retail_price * 2.0)

        return {
            "buyer": buyer,
            "target_id": target_id,
            "target_name": target_name,
            "item_data": item_data,
            "action": action,
            "offer": offer,
            "b_act": b_act,
            "truncated_history": truncated_history,
        }

    async def _run_concurrent_auction_round(self):
        """Execute a concurrent double-auction round across all remaining inventory."""
        unsold_items = [i for i in self.inventory if i.get("item_id", i["product_name"]) not in self.sold_items]
        if not unsold_items:
            return

        # 1. Asynchronously gather bids from all active buyers in parallel
        bid_tasks = [self._get_buyer_bid(b, unsold_items) for b in self.buyers]
        bid_results = await asyncio.gather(*bid_tasks)
        valid_bids = [b for b in bid_results if b is not None and b.get("offer", 0) > 0]

        if not valid_bids:
            return

        # 2. Group bids by item_id
        import collections
        bids_by_item = collections.defaultdict(list)
        for bid in valid_bids:
            item_id = bid["item_data"].get("item_id", bid["target_name"])
            bids_by_item[item_id].append(bid)

        # 3. Clear auction product by product
        for item_id, bids in bids_by_item.items():
            if item_id in self.sold_items:
                continue

            # Sort bids descending by offer price (highest bidder gets priority)
            bids.sort(key=lambda x: x["offer"], reverse=True)
            top_bid = bids[0]
            top_buyer = top_bid["buyer"]
            top_offer = top_bid["offer"]
            item_data = top_bid["item_data"]
            product_name = item_data["product_name"]

            price = self.blackboard["quotes"].get(item_id, item_data["selling_price"])
            floor = max(self.blackboard["floor_prices"].get(item_id, item_data["cost_price"]), item_data["cost_price"])
            retail_price = item_data["selling_price"]
            competing_count = len(bids)

            # Scenario A: Top offer meets or exceeds target ask price -> Instant Market Clear
            if top_offer >= price and top_offer >= floor:
                self._record_sale(top_buyer, item_data, top_offer)
                if competing_count > 1:
                    msg = f"AUCTION CLEARED: {product_name} ({item_id}) awarded to B{top_buyer.buyer_id} at ${top_offer:.2f} (outbid {competing_count-1} competitors)"
                    self.blackboard["logs"].append(msg)
                
                self.blackboard["negotiation_log"].append({
                    "hour": float(self.current_hour),
                    "item": product_name,
                    "item_id": item_id,
                    "buyer_id": top_buyer.buyer_id,
                    "round": int(self.current_hour // SIM_CLOCK_TICK + 1),
                    "risk_reader": {"bluffing_probability": 0, "walk_away_probability": 0, "tactic_detected": "instant_accept"},
                    "decider": {"risk_evaluation": "Instant market clearance: top bid meets or exceeds ask.", "action": "ACCEPT", "target_price": float(price)},
                    "buyer_response": {"action": str(top_bid.get("action", "ACCEPT")), "bid_amount": float(top_offer)},
                    "time_elapsed_this_negotiation": float(SIM_CLOCK_TICK),
                })
                continue

            # Scenario B: Top offer is below ask -> Seller evaluates top bid with competing buyer awareness
            if self.mode in ("MAS", "MAS_DEBATE"):
                s_act = await self.orchestrator.act(
                    top_buyer.buyer_id, product_name, price, floor,
                    self.blackboard["strategy"], self.current_hour, MAX_HOURS,
                    top_bid["truncated_history"], top_offer,
                    competing_bidders_count=competing_count,
                )
            elif self.mode == "SINGLE_MODEL":
                s_act = await self.monolithic_seller.act(
                    top_buyer.buyer_id, product_name, price,
                    item_data["cost_price"], retail_price,
                    self.current_hour, MAX_HOURS, top_bid["truncated_history"], top_offer,
                )
            elif self.mode == "LINEAR_DECAY":
                s_act = self.linear_decay.respond_to_offer(
                    item_data, top_offer, self.current_hour, MAX_HOURS
                )
            elif self.mode == "BASELINE_CSV":
                if top_offer >= retail_price:
                    s_act = {"action": "ACCEPT", "new_quote": retail_price, "message": ""}
                else:
                    s_act = {"action": "COUNTER", "new_quote": retail_price,
                             "message": f"Fixed price: ${retail_price:.2f}."}

            # Thread negotiation_log entry (fires every round per active item)
            rr_entry = s_act.get("_risk_profile", {}) if isinstance(s_act, dict) else {}
            dec_entry = s_act.get("_decision", {}) if isinstance(s_act, dict) else {}
            dec_action = dec_entry.get("tactic", dec_entry.get("action", "HOLD"))
            self.blackboard["negotiation_log"].append({
                "hour": float(self.current_hour),
                "item": product_name,
                "item_id": item_id,
                "buyer_id": top_buyer.buyer_id,
                "round": int(self.current_hour // SIM_CLOCK_TICK + 1),
                "risk_reader": {
                    "bluffing_probability": int(rr_entry.get("bluffing_probability", 5)),
                    "walk_away_probability": int(rr_entry.get("walk_away_probability", 5)),
                    "tactic_detected": str(rr_entry.get("tactic_detected", "Unknown")),
                },
                "decider": {
                    "risk_evaluation": str(dec_entry.get("risk_evaluation", "")),
                    "action": str(dec_action),
                    "target_price": float(dec_entry.get("target_price", price)),
                },
                "buyer_response": {
                    "action": str(top_bid.get("action", "COUNTER")),
                    "bid_amount": float(top_offer),
                },
                "time_elapsed_this_negotiation": float(SIM_CLOCK_TICK),
            })

            # Process seller decision
            if s_act.get("action") == "ACCEPT" and top_offer >= floor:
                self._record_sale(top_buyer, item_data, top_offer)
                if competing_count > 1:
                    msg = f"AUCTION CLEARED: {product_name} ({item_id}) conceded to top bidder B{top_buyer.buyer_id} at ${top_offer:.2f} ({competing_count} competing bidders)"
                    self.blackboard["logs"].append(msg)
            else:
                new_price = s_act.get("new_quote", price)
                if not isinstance(new_price, (int, float)):
                    new_price = price
                new_price = max(floor + 0.01, float(new_price))
                self.blackboard["quotes"][item_id] = new_price
                self.histories[top_buyer.buyer_id].append(
                    {"role": "assistant", "content": json.dumps(s_act)}
                )

    # ─── Main simulation loop ─────────────────────────────────────────────────

    async def run(self):
        print(f"--- Starting [{self.mode}] {self.exp_type} (Concurrent Double Auction) ---", flush=True)

        while self.current_hour < MAX_HOURS and len(self.sold_items) < len(self.inventory):
            if self.current_hour % 2 == 0:
                print(f"[{self.exp_type}] Hour {self.current_hour}/{MAX_HOURS} | Sold: {len(self.sold_items)}/{len(self.inventory)}", flush=True)

            # ── Strategic pricing update (MAS modes only) ─────────────────────
            if self.mode in ("MAS", "MAS_DEBATE"):
                if self.current_hour % 4 == 0 or (
                    self.blackboard["logs"] and "SALE" in self.blackboard["logs"][-1]
                ):
                    res = await self.brain.act(
                        self.inventory, self.blackboard["chaos"],
                        self.current_hour, MAX_HOURS,
                    )

                    valid_names = {i["product_name"] for i in self.inventory}
                    new_quotes  = {k: float(v) for k, v in res.get("quotes", {}).items()
                                   if k in valid_names and isinstance(v, (int, float))}
                    new_floors  = {k: float(v) for k, v in res.get("floor_prices", {}).items()
                                   if k in valid_names and isinstance(v, (int, float))}
                    if new_quotes:
                        self.blackboard["quotes"].update(new_quotes)
                    if new_floors:
                        self.blackboard["floor_prices"].update(new_floors)
                    strategy_text = res.get("chosen_strategy", res.get("strategy_directive", "Autonomous strategy."))
                    if res.get("market_analysis"):
                        self.blackboard["logs"].append(f"STRATEGY DISCOVERY: {strategy_text} | Analysis: {res.get('market_analysis')[:100]}...")
                    self.blackboard["strategy"] = strategy_text

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

            # ── Concurrent Double Auction Round ───────────────────────────────
            await self._run_concurrent_auction_round()

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
