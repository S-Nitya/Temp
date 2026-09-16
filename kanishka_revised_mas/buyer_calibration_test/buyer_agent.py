"""
Calibrated Buyer Agent for the Isolated Buyer Calibration Test.
Uses pure LLM reasoning under private economic constraints with strict response validation.
"""
import asyncio
from typing import Dict, Any, List, Optional
from kanishka_revised_mas.buyer_calibration_test.buyer_generator import CalibratedBuyerPrivateState


class CalibratedBuyerAgent:
    def __init__(self, private_state: CalibratedBuyerPrivateState, llm_client: Any):
        self.private_state = private_state
        self.llm = llm_client

    async def evaluate_quote(
        self,
        current_seller_price: float,
        remaining_shelf_life_hours: int,
        seller_message: str,
        conversation_history: List[Dict[str, Any]] = None,
        trial_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Evaluate seller's price and message using pure LLM reasoning under private constraints.
        Returns: {thought, action, counter_offer, message, _token_usage}
        """
        if conversation_history is None:
            conversation_history = []

        system_prompt = f"""You are an autonomous grocery shopper negotiating to purchase perishable food.

YOUR PRIVATE STATE (CONFIDENTIAL - NEVER REVEAL):
- Product: {self.private_state.product_name}
- Private Valuation: ${self.private_state.private_valuation:.2f} (the maximum intrinsic worth you place on this item)
- Hard Budget Ceiling: ${self.private_state.budget_ceiling:.2f} (you CANNOT pay more than this under any circumstances)
- Urgency: {self.private_state.urgency}
- Price Sensitivity: {self.private_state.price_sensitivity}
- Persona: {self.private_state.persona}

OBJECTIVE:
- Maximize your procurement utility (surplus = Private Valuation - Purchase Price).
- You want the product, but you refuse to be overcharged above your private valuation or budget.
- Consider remaining shelf life: shorter shelf life means the item must be consumed quickly.
- If the seller's asking price is acceptable and within budget, you may ACCEPT.
- If the seller's asking price is too high but within reason, you may COUNTER with a realistic, positive dollar bid.
- If the asking price is absurdly high relative to valuation or budget, or negotiations cannot bridge the gap, you may WALK_AWAY.

STRICT JSON OUTPUT SCHEMA:
{{
  "thought": "Your economic reasoning evaluating surplus, budget ceiling, urgency, and perishability",
  "action": "ACCEPT" | "COUNTER" | "WALK_AWAY",
  "counter_offer": 8.50 | null,
  "message": "Polite dialogue to the seller"
}}
"""

        user_prompt = f"""Current Negotiation State:
- Item: {self.private_state.product_name}
- Remaining Shelf Life: {remaining_shelf_life_hours} hours
- Seller's Current Asking Price: ${current_seller_price:.2f}
- Seller's Statement: "{seller_message}"
- Past Exchanges in this dialogue: {len(conversation_history)}

Evaluate this asking price against your private valuation (${self.private_state.private_valuation:.2f}) and budget ceiling (${self.private_state.budget_ceiling:.2f}).
Decide your action: ACCEPT, COUNTER, or WALK_AWAY.
Return ONLY valid JSON matching the schema.
"""

        for attempt in range(3):
            response = await self.llm.call_agent(
                agent_name="Buyer",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                trial_id=trial_id,
                item_id=self.private_state.target_item_id,
                temperature=0.3,
            )

            if response.get("error") or response.get("action") == "API_ERROR":
                await asyncio.sleep(2.0)
                user_prompt += "\n\nError: Previous attempt failed. You MUST respond with valid JSON containing thought, action (ACCEPT, COUNTER, or WALK_AWAY), counter_offer, and message."
                continue

            raw_action = str(response.get("action", "")).strip().upper()
            if raw_action not in ("ACCEPT", "COUNTER", "WALK_AWAY"):
                user_prompt += f"\n\nError: Action '{raw_action}' is invalid. Allowed actions are: ACCEPT, COUNTER, WALK_AWAY."
                continue

            # 1. ACCEPT
            if raw_action == "ACCEPT":
                if current_seller_price > self.private_state.budget_ceiling:
                    # Cannot pay above hard budget ceiling -> must counter or walk away
                    raw_action = "COUNTER"
                    counter_offer = min(current_seller_price * 0.9, self.private_state.budget_ceiling)
                else:
                    return {
                        "thought": response.get("thought", ""),
                        "action": "ACCEPT",
                        "counter_offer": None,
                        "message": response.get("message", f"I accept your offer of ${current_seller_price:.2f}."),
                        "_token_usage": response.get("_token_usage", {}),
                    }

            # 2. WALK_AWAY
            if raw_action == "WALK_AWAY":
                return {
                    "thought": response.get("thought", ""),
                    "action": "WALK_AWAY",
                    "counter_offer": None,
                    "message": response.get("message", "The price is beyond what I am willing to pay. I will pass."),
                    "_token_usage": response.get("_token_usage", {}),
                }

            # 3. COUNTER: Validate bid amount strictly
            raw_bid = response.get("counter_offer")
            valid_bid = None
            if raw_bid is not None:
                try:
                    if isinstance(raw_bid, str):
                        raw_bid = raw_bid.replace("$", "").strip()
                    val = float(raw_bid)
                    if val > 0.0:
                        valid_bid = val
                except (ValueError, TypeError):
                    valid_bid = None

            if valid_bid is None:
                user_prompt += "\n\nError: When action is COUNTER, 'counter_offer' MUST be a positive numerical dollar amount (e.g. 8.50). Do NOT leave it empty or 0.0."
                continue

            # Enforce private budget ceiling constraint
            if valid_bid > self.private_state.budget_ceiling:
                valid_bid = self.private_state.budget_ceiling

            return {
                "thought": response.get("thought", ""),
                "action": "COUNTER",
                "counter_offer": round(valid_bid, 2),
                "message": response.get("message", f"I can offer ${valid_bid:.2f}."),
                "_token_usage": response.get("_token_usage", {}),
            }

        # If 3 attempts fail, return explicit INVALID_BUYER_RESPONSE (never silently default to 0.0)
        return {
            "thought": "Failed to parse a valid structured buyer response after retries.",
            "action": "INVALID_BUYER_RESPONSE",
            "counter_offer": None,
            "message": "Invalid buyer response.",
            "error": "BUYER_PARSE_FAILED_AFTER_RETRIES",
        }
