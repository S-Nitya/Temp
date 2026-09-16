"""
Buyer Agent with strict private information boundaries for the Minimal Perishability Benchmark.
"""
from typing import Dict, Any, List, Optional
import random
from pydantic import BaseModel, Field


class BuyerPrivateState(BaseModel):
    buyer_id: str
    target_item_id: str
    product_name: str
    budget_ceiling: float
    private_valuation: float
    urgency: str  # "HIGH", "MODERATE", "LOW"
    price_sensitivity: str  # "HIGH", "MODERATE", "LOW"
    persona: str  # "BARGAIN_HUNTER", "QUALITY_SEEKER", "PRAGMATIC_SHOPPER"


def generate_buyer_private_states(catalog: List[Dict[str, Any]], seed: int) -> Dict[str, BuyerPrivateState]:
    """
    Generate and persist the complete private buyer states for each item in the catalog.
    These exact states are replayed across MAS and LinearDecay for a clean paired comparison.
    """
    rng = random.Random(seed)
    urgencies = ["HIGH", "MODERATE", "LOW"]
    sensitivities = ["HIGH", "MODERATE", "LOW"]
    personas = ["BARGAIN_HUNTER", "QUALITY_SEEKER", "PRAGMATIC_SHOPPER"]

    buyer_states = {}
    for item in catalog:
        item_id = item["item_id"]
        retail = float(item["retail_reference"])
        
        # Valuation distributed around retail reference
        val_multiplier = rng.uniform(0.85, 1.20)
        private_val = round(retail * val_multiplier, 2)
        
        # Budget ceiling (private hard constraint)
        budget_multiplier = rng.uniform(0.90, 1.25)
        budget = round(retail * budget_multiplier, 2)
        # Ensure budget is at least near valuation
        budget = max(budget, round(private_val * 0.95, 2))

        buyer_states[item_id] = BuyerPrivateState(
            buyer_id=f"B_{seed}_{item_id}",
            target_item_id=item_id,
            product_name=item["product_name"],
            budget_ceiling=budget,
            private_valuation=private_val,
            urgency=rng.choice(urgencies),
            price_sensitivity=rng.choice(sensitivities),
            persona=rng.choice(personas),
        )

    return buyer_states


class BuyerAgent:
    def __init__(self, private_state: BuyerPrivateState, llm_client: Any):
        self.private_state = private_state
        self.llm = llm_client

    async def evaluate_quote(
        self,
        current_seller_price: float,
        remaining_shelf_life_hours: int,
        seller_message: str,
        conversation_history: List[Dict[str, Any]],
        trial_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Evaluate seller's price and message using pure LLM reasoning under private constraints.
        Returns: {thought, action, counter_offer, message}
        """
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
- If the seller's price is higher than you want but negotiation is worthwhile, COUNTER with a specific offer.
- If the price is far too high, beyond your budget ceiling, or the seller is unwilling to budge, WALK_AWAY.

RULES:
1. NEVER offer or agree to any price above ${self.private_state.budget_ceiling:.2f}.
2. Allowed actions: "ACCEPT", "COUNTER", "WALK_AWAY".
3. If COUNTER, propose a positive numerical counter_offer.
4. Output MUST be valid JSON only.

OUTPUT JSON SCHEMA:
{{
  "thought": "Your internal economic reasoning based on valuation, budget, and shelf life",
  "action": "ACCEPT" | "COUNTER" | "WALK_AWAY",
  "counter_offer": 0.00,
  "message": "Brief message to the seller"
}}"""

        history_text = "\n".join([
            f"Exchange {idx+1}: Buyer={h.get('buyer_action', '')} (${h.get('buyer_offer', 0):.2f}) | Seller={h.get('seller_action', '')} Quote=${h.get('seller_quote', 0):.2f} Msg='{h.get('seller_message', '')}'"
            for idx, h in enumerate(conversation_history)
        ]) if conversation_history else "No previous exchanges."

        user_prompt = f"""CURRENT TRANSACTION STATE:
Item: {self.private_state.product_name}
Remaining Shelf Life: {remaining_shelf_life_hours} hours
Current Seller Asking Price: ${current_seller_price:.2f}
Seller Message: "{seller_message}"

CONVERSATION HISTORY:
{history_text}

Evaluate this offer and provide your JSON response."""

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
