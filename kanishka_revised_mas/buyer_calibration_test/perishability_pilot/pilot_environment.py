"""
Isolated Perishability Environment for Real-Time Perishability Pilot.
Implements:
- Fixed MARKET_DECISION_INTERVAL_HOURS = 2.0
- Exchanges within a session do NOT advance physical hours
- 3 exchanges communication limit per session
- Spoilage occurs ONLY when market_time >= expiry_hours while unsold
- Items remain alive across sessions if market_time < expiry_hours
"""
from typing import Dict, Any, List, Optional
import copy

from kanishka_revised_mas.mas_agents import MASOrchestrator, StrategicPolicy
from kanishka_revised_mas.linear_decay import LinearDecayPolicy
from kanishka_revised_mas.buyer_calibration_test.buyer_agent import CalibratedBuyerAgent
from kanishka_revised_mas.buyer_calibration_test.buyer_generator import CalibratedBuyerPrivateState


class PerishabilityPilotEnvironment:
    """
    Simulates sequential selling opportunities across fixed 2.0-hour market decision intervals.
    """
    def __init__(
        self,
        mode: str,
        llm_client: Any,
        market_decision_interval: float = 2.0,
        max_exchanges_per_session: int = 3,
    ):
        assert mode in ("MAS", "LinearDecay"), f"Unknown mode: {mode}"
        self.mode = mode
        self.llm = llm_client
        self.interval_hours = market_decision_interval
        self.max_exchanges = max_exchanges_per_session
        self.mas_orchestrator = MASOrchestrator(llm_client) if mode == "MAS" else None

    async def execute_item_lifecycle(
        self,
        item: Dict[str, Any],
        buyer_state: CalibratedBuyerPrivateState,
        trial_id: int = 999,
    ) -> Dict[str, Any]:
        """
        Execute the full lifecycle of an item across market decision intervals until SOLD or EXPIRED.
        """
        item_id = item["item_id"]
        product_name = item["product_name"]
        cost = float(item["cost_price"])
        retail = float(item["retail_reference"])
        expiry_hours = float(item["starting_remaining_hours"])
        regime = item.get("expiry_regime", "Medium")

        current_market_time = 0.0
        buyer = CalibratedBuyerAgent(buyer_state, self.llm)
        all_timeline_events: List[Dict[str, Any]] = []
        session_index = 0
        final_status = "UNRESOLVED"
        sale_price = 0.0
        spoilage_loss = 0.0
        item_profit = 0.0
        pcr = 0.0
        total_sessions = 0
        total_exchanges = 0

        start_call_idx = len(self.llm.call_records) if hasattr(self.llm, "call_records") else 0

        # Run multi-interval market lifecycle
        while current_market_time < expiry_hours:
            session_index += 1
            total_sessions = session_index
            remaining_shelf_life = max(0.0, expiry_hours - current_market_time)

            # Check if physical expiry was already reached at start of session
            if current_market_time >= expiry_hours:
                final_status = "EXPIRED"
                spoilage_loss = cost
                item_profit = -cost
                all_timeline_events.append({
                    "item_id": item_id,
                    "product_name": product_name,
                    "session_index": session_index,
                    "market_time_h": round(current_market_time, 2),
                    "exchange_number": 0,
                    "time_before_exchange_h": round(current_market_time, 2),
                    "time_after_exchange_h": round(current_market_time, 2),
                    "remaining_shelf_life_h": 0.0,
                    "seller_action": "EXPIRED",
                    "seller_price": 0.0,
                    "buyer_action": "NONE",
                    "buyer_bid": None,
                    "risk_reader_output": None,
                    "decider_output": None,
                    "event_type": "PHYSICAL_EXPIRY",
                    "final_status": "EXPIRED",
                })
                break

            # Current item representation with remaining shelf life for the seller
            current_item = copy.deepcopy(item)
            current_item["starting_remaining_hours"] = remaining_shelf_life

            # 1. Seller Macro Policy Formation at Current Market Time
            if self.mode == "MAS":
                policy = await self.mas_orchestrator.form_strategic_policy(current_item, trial_id=trial_id)
                opening_quote = policy.opening_quote
                seller_floor = policy.seller_floor
            else:
                ld_policy = LinearDecayPolicy(current_item, max_exchanges=self.max_exchanges)
                opening_quote = ld_policy.opening_quote
                seller_floor = ld_policy.seller_floor

            current_seller_price = opening_quote
            seller_message = f"Welcome! We are offering fresh {product_name} at ${opening_quote:.2f}."

            session_timeline: List[Dict[str, Any]] = []

            # 2. Exchange 0 (Buyer Opening Evaluation)
            # Physical time remains current_market_time
            time_before = current_market_time
            time_after = current_market_time

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

            # Record Exchange 0
            ex0_event = {
                "item_id": item_id,
                "product_name": product_name,
                "expiry_hours": expiry_hours,
                "cost_price": cost,
                "retail_reference": retail,
                "session_index": session_index,
                "market_time_h": round(current_market_time, 2),
                "exchange_number": 0,
                "time_before_exchange_h": round(time_before, 2),
                "time_after_exchange_h": round(time_after, 2),
                "remaining_shelf_life_h": round(remaining_shelf_life, 2),
                "seller_action": "QUOTE",
                "seller_price": current_seller_price,
                "seller_quote": current_seller_price,
                "seller_message": seller_message,
                "buyer_action": b_action,
                "buyer_bid": b_bid,
                "buyer_offer": b_bid if b_bid is not None else 0.0,
                "buyer_message": b_msg,
                "risk_reader_output": None,
                "decider_output": None,
                "event_type": "OPENING_QUOTE",
                "final_status": "IN_PROGRESS",
                "sale_price": 0.0,
                "spoilage_loss": 0.0,
            }
            session_timeline.append(ex0_event)
            all_timeline_events.append(ex0_event)

            # Outcome A: Instant Clear
            if b_action == "ACCEPT" or (b_bid is not None and b_bid >= current_seller_price and b_bid >= seller_floor):
                final_price = max(current_seller_price, b_bid) if b_bid is not None else current_seller_price
                final_status = "SOLD"
                sale_price = final_price
                spoilage_loss = 0.0
                item_profit = final_price - cost
                pcr = item_profit / (retail - cost) if (retail - cost) > 0 else 1.0
                ex0_event["final_status"] = "SOLD"
                break

            # Outcome B: Immediate Walk-Away at Exchange 0
            if b_action == "WALK_AWAY":
                ex0_event["final_status"] = "BUYER_WALK_AWAY"
                # Advance market clock by interval
                current_market_time += self.interval_hours
                remaining_shelf_life = max(0.0, expiry_hours - current_market_time)

                advance_event = {
                    "item_id": item_id,
                    "product_name": product_name,
                    "expiry_hours": expiry_hours,
                    "cost_price": cost,
                    "retail_reference": retail,
                    "session_index": session_index,
                    "market_time_h": round(current_market_time, 2),
                    "exchange_number": 0,
                    "time_before_exchange_h": round(time_before, 2),
                    "time_after_exchange_h": round(current_market_time, 2),
                    "remaining_shelf_life_h": round(remaining_shelf_life, 2),
                    "seller_action": "INTERVAL_ADVANCE",
                    "seller_price": 0.0,
                    "buyer_action": "WALK_AWAY",
                    "buyer_bid": None,
                    "risk_reader_output": None,
                    "decider_output": None,
                    "event_type": "MARKET_CLOCK_ADVANCE",
                    "final_status": "EXPIRED" if current_market_time >= expiry_hours else "BUYER_WALK_AWAY",
                    "sale_price": 0.0,
                    "spoilage_loss": cost if current_market_time >= expiry_hours else 0.0,
                }
                all_timeline_events.append(advance_event)

                if current_market_time >= expiry_hours:
                    final_status = "EXPIRED"
                    spoilage_loss = cost
                    item_profit = -cost
                    break
                else:
                    # Item remains alive, continue to next session
                    continue

            # Outcome C: Invalid Response
            if b_action == "INVALID_BUYER_RESPONSE" or b_bid is None:
                ex0_event["final_status"] = "INVALID_BUYER_RESPONSE"
                current_market_time += self.interval_hours
                remaining_shelf_life = max(0.0, expiry_hours - current_market_time)

                advance_event = {
                    "item_id": item_id,
                    "product_name": product_name,
                    "expiry_hours": expiry_hours,
                    "cost_price": cost,
                    "retail_reference": retail,
                    "session_index": session_index,
                    "market_time_h": round(current_market_time, 2),
                    "exchange_number": 0,
                    "time_before_exchange_h": round(time_before, 2),
                    "time_after_exchange_h": round(current_market_time, 2),
                    "remaining_shelf_life_h": round(remaining_shelf_life, 2),
                    "seller_action": "INTERVAL_ADVANCE",
                    "seller_price": 0.0,
                    "buyer_action": "INVALID",
                    "buyer_bid": None,
                    "risk_reader_output": None,
                    "decider_output": None,
                    "event_type": "MARKET_CLOCK_ADVANCE",
                    "final_status": "EXPIRED" if current_market_time >= expiry_hours else "INVALID_BUYER_RESPONSE",
                    "sale_price": 0.0,
                    "spoilage_loss": cost if current_market_time >= expiry_hours else 0.0,
                }
                all_timeline_events.append(advance_event)

                if current_market_time >= expiry_hours:
                    final_status = "EXPIRED"
                    spoilage_loss = cost
                    item_profit = -cost
                    break
                else:
                    continue

            # Outcome D: Buyer Countered -> Multi-Exchange Negotiation within session
            last_buyer_bid = b_bid
            last_buyer_msg = b_msg
            session_sold = False
            session_walked_away = False

            for ex in range(1, self.max_exchanges + 1):
                total_exchanges += 1
                # Physical time does NOT advance per exchange turn
                time_before = current_market_time
                time_after = current_market_time

                rr_res = None
                dec_res = None

                if self.mode == "MAS":
                    s_res = await self.mas_orchestrator.evaluate_buyer_counter(
                        item=current_item,
                        policy=policy,
                        buyer_counter_offer=last_buyer_bid,
                        buyer_message=last_buyer_msg,
                        current_seller_price=current_seller_price,
                        remaining_shelf_life_hours=int(remaining_shelf_life),
                        conversation_history=session_timeline,
                        trial_id=trial_id,
                    )
                    rr_res = s_res.get("risk_reader")
                    dec_res = {"action": s_res.get("action"), "target_price": s_res.get("target_price")}
                else:
                    s_res = ld_policy.evaluate_offer(last_buyer_bid, exchange_idx=ex)
                    dec_res = {"action": s_res.get("action"), "target_price": s_res.get("target_price")}

                s_action = s_res["action"]
                target_price = s_res["target_price"]
                s_msg = s_res.get("spokesperson_message", f"Our price is ${target_price:.2f}.")

                # If seller accepts buyer offer
                if s_action == "ACCEPT" and last_buyer_bid >= seller_floor:
                    final_price = last_buyer_bid
                    final_status = "SOLD"
                    sale_price = final_price
                    spoilage_loss = 0.0
                    item_profit = final_price - cost
                    pcr = item_profit / (retail - cost) if (retail - cost) > 0 else 1.0
                    session_sold = True

                    deal_event = {
                        "item_id": item_id,
                        "product_name": product_name,
                        "expiry_hours": expiry_hours,
                        "cost_price": cost,
                        "retail_reference": retail,
                        "session_index": session_index,
                        "market_time_h": round(current_market_time, 2),
                        "exchange_number": ex,
                        "time_before_exchange_h": round(time_before, 2),
                        "time_after_exchange_h": round(time_after, 2),
                        "remaining_shelf_life_h": round(remaining_shelf_life, 2),
                        "seller_action": "ACCEPT",
                        "seller_price": final_price,
                        "seller_quote": final_price,
                        "seller_message": s_msg,
                        "buyer_action": "ACCEPTED_BY_SELLER",
                        "buyer_bid": last_buyer_bid,
                        "buyer_offer": last_buyer_bid,
                        "buyer_message": last_buyer_msg,
                        "risk_reader_output": rr_res.get("risk_summary") if rr_res else None,
                        "decider_output": str(dec_res),
                        "event_type": "SELLER_ACCEPT",
                        "final_status": "SOLD",
                        "sale_price": final_price,
                        "spoilage_loss": 0.0,
                    }
                    session_timeline.append(deal_event)
                    all_timeline_events.append(deal_event)
                    break

                # Seller counters with target_price
                current_seller_price = target_price
                seller_message = s_msg

                # Buyer evaluates new quote
                b_next = await buyer.evaluate_quote(
                    current_seller_price=current_seller_price,
                    remaining_shelf_life_hours=int(remaining_shelf_life),
                    seller_message=seller_message,
                    conversation_history=session_timeline,
                    trial_id=trial_id,
                )

                b_action = b_next["action"]
                b_bid = b_next.get("counter_offer")
                b_msg = b_next.get("message", "")

                ex_event = {
                    "item_id": item_id,
                    "product_name": product_name,
                    "expiry_hours": expiry_hours,
                    "cost_price": cost,
                    "retail_reference": retail,
                    "session_index": session_index,
                    "market_time_h": round(current_market_time, 2),
                    "exchange_number": ex,
                    "time_before_exchange_h": round(time_before, 2),
                    "time_after_exchange_h": round(time_after, 2),
                    "remaining_shelf_life_h": round(remaining_shelf_life, 2),
                    "seller_action": s_action,
                    "seller_price": current_seller_price,
                    "seller_quote": current_seller_price,
                    "seller_message": seller_message,
                    "buyer_action": b_action,
                    "buyer_bid": b_bid,
                    "buyer_offer": b_bid if b_bid is not None else 0.0,
                    "buyer_message": b_msg,
                    "risk_reader_output": rr_res.get("risk_summary") if rr_res else None,
                    "decider_output": str(dec_res),
                    "event_type": "COUNTER_EXCHANGE",
                    "final_status": "IN_PROGRESS",
                    "sale_price": 0.0,
                    "spoilage_loss": 0.0,
                }
                session_timeline.append(ex_event)
                all_timeline_events.append(ex_event)

                # Buyer accepts seller counter
                if b_action == "ACCEPT" or (b_bid is not None and b_bid >= current_seller_price and b_bid >= seller_floor):
                    final_price = max(current_seller_price, b_bid) if b_bid is not None else current_seller_price
                    final_status = "SOLD"
                    sale_price = final_price
                    spoilage_loss = 0.0
                    item_profit = final_price - cost
                    pcr = item_profit / (retail - cost) if (retail - cost) > 0 else 1.0
                    ex_event["final_status"] = "SOLD"
                    ex_event["sale_price"] = final_price
                    session_sold = True
                    break

                # Buyer walks away mid-negotiation
                if b_action == "WALK_AWAY":
                    ex_event["final_status"] = "BUYER_WALK_AWAY"
                    session_walked_away = True
                    break

                last_buyer_bid = b_bid
                last_buyer_msg = b_msg

            if session_sold:
                break

            # If session finished without sale: advance market clock by 2.0 hours
            current_market_time += self.interval_hours
            remaining_shelf_life = max(0.0, expiry_hours - current_market_time)

            session_end_status = "BUYER_WALK_AWAY" if session_walked_away else "MAX_ROUNDS_UNRESOLVED"
            post_advance_status = "EXPIRED" if current_market_time >= expiry_hours else session_end_status

            interval_event = {
                "item_id": item_id,
                "product_name": product_name,
                "expiry_hours": expiry_hours,
                "cost_price": cost,
                "retail_reference": retail,
                "session_index": session_index,
                "market_time_h": round(current_market_time, 2),
                "exchange_number": 0,
                "time_before_exchange_h": round(time_before, 2),
                "time_after_exchange_h": round(current_market_time, 2),
                "remaining_shelf_life_h": round(remaining_shelf_life, 2),
                "seller_action": "INTERVAL_ADVANCE",
                "seller_price": 0.0,
                "buyer_action": session_end_status,
                "buyer_bid": None,
                "risk_reader_output": None,
                "decider_output": None,
                "event_type": "MARKET_CLOCK_ADVANCE",
                "final_status": post_advance_status,
                "sale_price": 0.0,
                "spoilage_loss": cost if current_market_time >= expiry_hours else 0.0,
            }
            all_timeline_events.append(interval_event)

            if current_market_time >= expiry_hours:
                final_status = "EXPIRED"
                spoilage_loss = cost
                item_profit = -cost
                break

        end_call_idx = len(self.llm.call_records) if hasattr(self.llm, "call_records") else 0
        call_records = self.llm.call_records[start_call_idx:end_call_idx] if hasattr(self.llm, "call_records") else []
        item_total_tokens = sum(r.total_tokens for r in call_records)

        return {
            "item_id": item_id,
            "product_name": product_name,
            "category": item["category"],
            "cost_price": cost,
            "retail_reference": retail,
            "expiry_hours": expiry_hours,
            "expiry_regime": regime,
            "condition": self.mode,
            "final_status": final_status,
            "sale_price": round(sale_price, 2),
            "spoilage_loss": round(spoilage_loss, 2),
            "item_profit": round(item_profit, 2),
            "pcr": round(pcr, 4) if final_status == "SOLD" else 0.0,
            "final_simulated_time_h": round(current_market_time, 2),
            "remaining_shelf_life_h": round(max(0.0, expiry_hours - current_market_time), 2),
            "total_sessions": total_sessions,
            "total_exchanges": total_exchanges,
            "total_tokens": item_total_tokens,
            "timeline": all_timeline_events,
        }
