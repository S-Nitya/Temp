"""
Sequential 1-on-1 Bilateral Negotiation Environment with Deterministic Physical Market Clock,
Explicit Terminal States, True Spoilage Accounting, and Audit Traces.
"""
from typing import Dict, Any, List, Optional
import time
from kanishka_revised_mas.buyer import BuyerAgent, BuyerPrivateState
from kanishka_revised_mas.mas_agents import MASOrchestrator, StrategicPolicy
from kanishka_revised_mas.linear_decay import LinearDecayPolicy


class NegotiationEnvironment:
    """
    Deterministic Perishable Goods Negotiation Environment.
    Separates physical simulated time from negotiation rounds.
    Spoilage occurs ONLY when current_simulated_time >= expiry_time.
    """
    def __init__(self, mode: str, llm_client: Any, max_exchanges: int = 3, time_per_exchange: float = 1.0):
        assert mode in ("MAS", "LinearDecay"), f"Unknown mode: {mode}"
        self.mode = mode
        self.llm = llm_client
        self.max_exchanges = max_exchanges
        self.time_per_exchange = time_per_exchange
        self.mas_orchestrator = MASOrchestrator(llm_client) if mode == "MAS" else None

    async def execute_item_transaction(
        self,
        item: Dict[str, Any],
        buyer_state: BuyerPrivateState,
        trial_id: int = 1,
        starting_time: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Execute sequential 1-on-1 negotiation for a single perishable item.
        Tracks physical time, remaining shelf life, exchange counts, and detailed timelines.
        """
        item_id = item["item_id"]
        product_name = item["product_name"]
        cost = float(item["cost_price"])
        retail = float(item["retail_reference"])
        expiry_hours = float(item["starting_remaining_hours"])
        regime = item.get("expiry_regime", "Medium")

        # 1. Independent Time Tracking Variables
        current_simulated_time = starting_time
        expiry_time = starting_time + expiry_hours
        remaining_shelf_life = max(0.0, expiry_time - current_simulated_time)
        negotiation_exchange_count = 0
        maximum_exchanges_per_epoch = self.max_exchanges

        buyer = BuyerAgent(buyer_state, self.llm)
        timeline: List[Dict[str, Any]] = []

        start_call_idx = len(self.llm.call_records) if hasattr(self.llm, "call_records") else 0

        # 2. Strategic Brain & Opening Pricing
        if self.mode == "MAS":
            policy = await self.mas_orchestrator.form_strategic_policy(item, trial_id=trial_id)
            opening_quote = policy.opening_quote
            seller_floor = policy.seller_floor
            strategy_label = policy.strategy_label
        else:
            ld_policy = LinearDecayPolicy(item, max_exchanges=self.max_exchanges)
            opening_quote = ld_policy.opening_quote
            seller_floor = ld_policy.seller_floor
            strategy_label = "DETERMINISTIC_LINEAR_DECAY"

        current_seller_price = opening_quote
        seller_message = f"Welcome! We are offering fresh {product_name} at ${opening_quote:.2f}."

        # 3. Exchange 0 (Buyer Opening Evaluation)
        buyer_res = await buyer.evaluate_quote(
            current_seller_price=current_seller_price,
            remaining_shelf_life_hours=int(remaining_shelf_life),
            seller_message=seller_message,
            conversation_history=[],
            trial_id=trial_id,
        )

        b_action = buyer_res["action"]
        b_bid = buyer_res.get("counter_offer")
        b_msg = buyer_res.get("message", "")

        # Record Exchange 0 in timeline
        timeline.append({
            "exchange_number": 0,
            "current_simulated_time": round(current_simulated_time, 2),
            "remaining_shelf_life": round(remaining_shelf_life, 2),
            "seller_action": "QUOTE",
            "seller_price": current_seller_price,
            "seller_floor": seller_floor,
            "seller_message": seller_message,
            "buyer_action": b_action,
            "buyer_bid": b_bid,
            "buyer_message": b_msg,
            "risk_reader_invoked": False,
            "risk_reader_result": None,
            "decider_invoked": False,
            "decider_result": None,
            "spokesperson_invoked": False,
            "spokesperson_output": None,
        })

        # Instant Clear Condition
        if b_action == "ACCEPT" or (b_bid is not None and b_bid >= current_seller_price and b_bid >= seller_floor):
            final_price = max(current_seller_price, b_bid) if b_bid is not None else current_seller_price
            profit = final_price - cost
            pcr = profit / (retail - cost) if (retail - cost) > 0 else 1.0
            return self._build_result(
                item=item,
                final_status="SOLD",
                sale_price=final_price,
                spoilage_loss=0.0,
                item_profit=profit,
                pcr=pcr,
                negotiation_status="INSTANT_CLEAR",
                number_of_exchanges=0,
                starting_time=starting_time,
                current_simulated_time=current_simulated_time,
                expiry_time=expiry_time,
                remaining_shelf_life=remaining_shelf_life,
                opening_quote=opening_quote,
                seller_floor=seller_floor,
                timeline=timeline,
                start_call_idx=start_call_idx,
                trial_id=trial_id,
            )

        # Immediate Walk Away Condition
        if b_action == "WALK_AWAY":
            current_simulated_time += self.time_per_exchange
            remaining_shelf_life = max(0.0, expiry_time - current_simulated_time)
            is_expired = current_simulated_time >= expiry_time
            final_status = "EXPIRED" if is_expired else "BUYER_WALK_AWAY"
            spoilage = cost if is_expired else 0.0
            item_prof = -cost if is_expired else 0.0
            return self._build_result(
                item=item,
                final_status=final_status,
                sale_price=0.0,
                spoilage_loss=spoilage,
                item_profit=item_prof,
                pcr=0.0,
                negotiation_status="BUYER_WALK_AWAY_OPENING",
                number_of_exchanges=0,
                starting_time=starting_time,
                current_simulated_time=current_simulated_time,
                expiry_time=expiry_time,
                remaining_shelf_life=remaining_shelf_life,
                opening_quote=opening_quote,
                seller_floor=seller_floor,
                timeline=timeline,
                start_call_idx=start_call_idx,
                trial_id=trial_id,
            )

        # Invalid Buyer Response Condition
        if b_action == "INVALID_BUYER_RESPONSE" or b_bid is None:
            current_simulated_time += self.time_per_exchange
            remaining_shelf_life = max(0.0, expiry_time - current_simulated_time)
            is_expired = current_simulated_time >= expiry_time
            final_status = "EXPIRED" if is_expired else "INVALID_BUYER_RESPONSE"
            spoilage = cost if is_expired else 0.0
            item_prof = -cost if is_expired else 0.0
            return self._build_result(
                item=item,
                final_status=final_status,
                sale_price=0.0,
                spoilage_loss=spoilage,
                item_profit=item_prof,
                pcr=0.0,
                negotiation_status="INVALID_BUYER_RESPONSE",
                number_of_exchanges=0,
                starting_time=starting_time,
                current_simulated_time=current_simulated_time,
                expiry_time=expiry_time,
                remaining_shelf_life=remaining_shelf_life,
                opening_quote=opening_quote,
                seller_floor=seller_floor,
                timeline=timeline,
                start_call_idx=start_call_idx,
                trial_id=trial_id,
            )

        # 4. Multi-Exchange Negotiation Loop (Exchanges 1 to max_exchanges)
        last_buyer_bid = b_bid
        last_buyer_msg = b_msg

        for ex in range(1, maximum_exchanges_per_epoch + 1):
            negotiation_exchange_count = ex
            current_simulated_time += self.time_per_exchange
            remaining_shelf_life = max(0.0, expiry_time - current_simulated_time)

            # Check if physical expiry occurred while negotiating
            if current_simulated_time >= expiry_time:
                timeline.append({
                    "exchange_number": ex,
                    "current_simulated_time": round(current_simulated_time, 2),
                    "remaining_shelf_life": 0.0,
                    "event": "PHYSICAL_EXPIRY_REACHED",
                })
                return self._build_result(
                    item=item,
                    final_status="EXPIRED",
                    sale_price=0.0,
                    spoilage_loss=cost,
                    item_profit=-cost,
                    pcr=0.0,
                    negotiation_status="EXPIRED_DURING_NEGOTIATION",
                    number_of_exchanges=ex,
                    starting_time=starting_time,
                    current_simulated_time=current_simulated_time,
                    expiry_time=expiry_time,
                    remaining_shelf_life=0.0,
                    opening_quote=opening_quote,
                    seller_floor=seller_floor,
                    timeline=timeline,
                    start_call_idx=start_call_idx,
                    trial_id=trial_id,
                )

            # Seller evaluation of buyer's valid counter
            rr_invoked = False
            dec_invoked = False
            spk_invoked = False
            rr_res = None
            dec_res = None

            if self.mode == "MAS":
                rr_invoked = True
                dec_invoked = True
                spk_invoked = True
                s_res = await self.mas_orchestrator.evaluate_buyer_counter(
                    item=item,
                    policy=policy,
                    buyer_counter_offer=last_buyer_bid,
                    buyer_message=last_buyer_msg,
                    current_seller_price=current_seller_price,
                    remaining_shelf_life_hours=int(remaining_shelf_life),
                    conversation_history=timeline,
                    trial_id=trial_id,
                )
                rr_res = s_res.get("risk_reader")
                dec_res = {"action": s_res.get("action"), "target_price": s_res.get("target_price"), "rationale": s_res.get("rationale")}
            else:
                s_res = ld_policy.evaluate_offer(last_buyer_bid, exchange_idx=ex)
                dec_res = {"action": s_res.get("action"), "target_price": s_res.get("target_price")}

            s_action = s_res["action"]
            target_price = s_res["target_price"]
            s_msg = s_res.get("spokesperson_message", "")

            # If Seller accepts Buyer's offer
            if s_action == "ACCEPT" and last_buyer_bid >= seller_floor:
                final_price = last_buyer_bid
                profit = final_price - cost
                pcr = profit / (retail - cost) if (retail - cost) > 0 else 1.0
                timeline.append({
                    "exchange_number": ex,
                    "current_simulated_time": round(current_simulated_time, 2),
                    "remaining_shelf_life": round(remaining_shelf_life, 2),
                    "seller_action": "ACCEPT",
                    "seller_price": final_price,
                    "seller_floor": seller_floor,
                    "seller_message": s_msg,
                    "buyer_action": "ACCEPTED_BY_SELLER",
                    "buyer_bid": last_buyer_bid,
                    "risk_reader_invoked": rr_invoked,
                    "risk_reader_result": rr_res,
                    "decider_invoked": dec_invoked,
                    "decider_result": dec_res,
                    "spokesperson_invoked": spk_invoked,
                    "spokesperson_output": s_msg,
                })
                return self._build_result(
                    item=item,
                    final_status="SOLD",
                    sale_price=final_price,
                    spoilage_loss=0.0,
                    item_profit=profit,
                    pcr=pcr,
                    negotiation_status="NEGOTIATED_SALE",
                    number_of_exchanges=ex,
                    starting_time=starting_time,
                    current_simulated_time=current_simulated_time,
                    expiry_time=expiry_time,
                    remaining_shelf_life=remaining_shelf_life,
                    opening_quote=opening_quote,
                    seller_floor=seller_floor,
                    timeline=timeline,
                    start_call_idx=start_call_idx,
                    trial_id=trial_id,
                )

            # Seller proposes new price quote
            current_seller_price = target_price
            seller_message = s_msg

            # Buyer evaluates seller's new quote
            b_next = await buyer.evaluate_quote(
                current_seller_price=current_seller_price,
                remaining_shelf_life_hours=int(remaining_shelf_life),
                seller_message=seller_message,
                conversation_history=timeline,
                trial_id=trial_id,
            )

            b_action = b_next["action"]
            b_bid = b_next.get("counter_offer")
            b_msg = b_next.get("message", "")

            timeline.append({
                "exchange_number": ex,
                "current_simulated_time": round(current_simulated_time, 2),
                "remaining_shelf_life": round(remaining_shelf_life, 2),
                "seller_action": s_action,
                "seller_price": current_seller_price,
                "seller_floor": seller_floor,
                "seller_message": seller_message,
                "buyer_action": b_action,
                "buyer_bid": b_bid,
                "buyer_message": b_msg,
                "risk_reader_invoked": rr_invoked,
                "risk_reader_result": rr_res,
                "decider_invoked": dec_invoked,
                "decider_result": dec_res,
                "spokesperson_invoked": spk_invoked,
                "spokesperson_output": seller_message,
            })

            # Check Buyer Accept or Crossing of Bid/Ask
            if b_action == "ACCEPT" or (b_bid is not None and b_bid >= current_seller_price and b_bid >= seller_floor):
                final_price = max(current_seller_price, b_bid) if b_bid is not None else current_seller_price
                profit = final_price - cost
                pcr = profit / (retail - cost) if (retail - cost) > 0 else 1.0
                return self._build_result(
                    item=item,
                    final_status="SOLD",
                    sale_price=final_price,
                    spoilage_loss=0.0,
                    item_profit=profit,
                    pcr=pcr,
                    negotiation_status="NEGOTIATED_SALE",
                    number_of_exchanges=ex,
                    starting_time=starting_time,
                    current_simulated_time=current_simulated_time,
                    expiry_time=expiry_time,
                    remaining_shelf_life=remaining_shelf_life,
                    opening_quote=opening_quote,
                    seller_floor=seller_floor,
                    timeline=timeline,
                    start_call_idx=start_call_idx,
                    trial_id=trial_id,
                )

            # Check Buyer Walk Away
            if b_action == "WALK_AWAY":
                is_expired = current_simulated_time >= expiry_time
                final_status = "EXPIRED" if is_expired else "BUYER_WALK_AWAY"
                spoilage = cost if is_expired else 0.0
                item_prof = -cost if is_expired else 0.0
                return self._build_result(
                    item=item,
                    final_status=final_status,
                    sale_price=0.0,
                    spoilage_loss=spoilage,
                    item_profit=item_prof,
                    pcr=0.0,
                    negotiation_status="BUYER_WALK_AWAY",
                    number_of_exchanges=ex,
                    starting_time=starting_time,
                    current_simulated_time=current_simulated_time,
                    expiry_time=expiry_time,
                    remaining_shelf_life=remaining_shelf_life,
                    opening_quote=opening_quote,
                    seller_floor=seller_floor,
                    timeline=timeline,
                    start_call_idx=start_call_idx,
                    trial_id=trial_id,
                )

            # Check Invalid Response
            if b_action == "INVALID_BUYER_RESPONSE" or b_bid is None:
                is_expired = current_simulated_time >= expiry_time
                final_status = "EXPIRED" if is_expired else "INVALID_BUYER_RESPONSE"
                spoilage = cost if is_expired else 0.0
                item_prof = -cost if is_expired else 0.0
                return self._build_result(
                    item=item,
                    final_status=final_status,
                    sale_price=0.0,
                    spoilage_loss=spoilage,
                    item_profit=item_prof,
                    pcr=0.0,
                    negotiation_status="INVALID_BUYER_RESPONSE",
                    number_of_exchanges=ex,
                    starting_time=starting_time,
                    current_simulated_time=current_simulated_time,
                    expiry_time=expiry_time,
                    remaining_shelf_life=remaining_shelf_life,
                    opening_quote=opening_quote,
                    seller_floor=seller_floor,
                    timeline=timeline,
                    start_call_idx=start_call_idx,
                    trial_id=trial_id,
                )

            last_buyer_bid = b_bid
            last_buyer_msg = b_msg

        # 5. Maximum Rounds Reached (Unresolved)
        # Advance simulated time to mark conclusion of the 3-exchange epoch
        is_expired = current_simulated_time >= expiry_time
        final_status = "EXPIRED" if is_expired else "MAX_ROUNDS_UNRESOLVED"
        spoilage = cost if is_expired else 0.0
        item_prof = -cost if is_expired else 0.0

        return self._build_result(
            item=item,
            final_status=final_status,
            sale_price=0.0,
            spoilage_loss=spoilage,
            item_profit=item_prof,
            pcr=0.0,
            negotiation_status="MAX_ROUNDS_UNRESOLVED",
            number_of_exchanges=maximum_exchanges_per_epoch,
            starting_time=starting_time,
            current_simulated_time=current_simulated_time,
            expiry_time=expiry_time,
            remaining_shelf_life=remaining_shelf_life,
            opening_quote=opening_quote,
            seller_floor=seller_floor,
            timeline=timeline,
            start_call_idx=start_call_idx,
            trial_id=trial_id,
        )

    def _build_result(
        self,
        item: Dict[str, Any],
        final_status: str,
        sale_price: float,
        spoilage_loss: float,
        item_profit: float,
        pcr: float,
        negotiation_status: str,
        number_of_exchanges: int,
        starting_time: float,
        current_simulated_time: float,
        expiry_time: float,
        remaining_shelf_life: float,
        opening_quote: float,
        seller_floor: float,
        timeline: List[Dict[str, Any]],
        start_call_idx: int,
        trial_id: int,
    ) -> Dict[str, Any]:
        """Construct comprehensive item transaction record with full timeline and token breakdown."""
        call_records = self.llm.call_records[start_call_idx:] if hasattr(self.llm, "call_records") else []
        total_tokens = sum(r.total_tokens for r in call_records)
        token_breakdown: Dict[str, int] = {}
        for r in call_records:
            token_breakdown[r.agent_name] = token_breakdown.get(r.agent_name, 0) + r.total_tokens

        return {
            "item_id": item["item_id"],
            "product_name": item["product_name"],
            "cost_price": float(item["cost_price"]),
            "retail_reference": float(item["retail_reference"]),
            "expiry_hours": float(item["starting_remaining_hours"]),
            "expiry_regime": item.get("expiry_regime", "Medium"),
            "starting_time": round(starting_time, 2),
            "expiry_time": round(expiry_time, 2),
            "current_simulated_time": round(current_simulated_time, 2),
            "remaining_shelf_life": round(remaining_shelf_life, 2),
            "starting_price": round(opening_quote, 2),
            "seller_floor": round(seller_floor, 2),
            "final_price": round(sale_price, 2),
            "sale_status": "SOLD" if final_status == "SOLD" else "UNSOLD",
            "final_status": final_status,
            "negotiation_status": negotiation_status,
            "number_of_exchanges": number_of_exchanges,
            "spoilage_loss": round(spoilage_loss, 2),
            "item_profit": round(item_profit, 2),
            "pcr": round(pcr, 4),
            "timeline": timeline,
            "total_tokens": total_tokens,
            "token_breakdown_by_agent": token_breakdown,
            "trial_id": trial_id,
            "condition": self.mode,
        }
