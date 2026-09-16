"""
Hierarchical Multi-Agent System (MAS) Seller Agents for the Minimal Perishability Benchmark.
Strictly stateless with no hardcoded pricing formulas or hidden heuristics.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class StrategicPolicy(BaseModel):
    opening_quote: float
    seller_floor: float
    strategy_label: str
    expiry_risk: str
    rationale: str


class RiskAssessment(BaseModel):
    bluffing_probability: float
    walk_away_probability: float
    detected_tactic: str
    risk_summary: str


class DeciderDecision(BaseModel):
    action: str  # "HOLD", "CONCEDE", "ACCEPT"
    target_price: float
    rationale: str


class MASOrchestrator:
    def __init__(self, llm_client: Any):
        self.llm = llm_client

    async def form_strategic_policy(
        self,
        item: Dict[str, Any],
        trial_id: int = 1,
    ) -> StrategicPolicy:
        """
        Synthesize macro strategic policy via StrategicBrain (70B) + Bull/Bear Debate + Judge.
        """
        product_name = item["product_name"]
        cost = float(item["cost_price"])
        retail = float(item["retail_reference"])
        rem_hours = int(item["starting_remaining_hours"])
        regime = item.get("expiry_regime", "Medium")

        # 1. Strategic Brain (70B)
        sb_sys = """You are the Lead Strategic Pricing Executive for a perishable grocery retailer.
Your objective is to maximize expected True Net Profit (Revenue - Cost - Spoilage Losses) over perishable inventory.
Unsold inventory at expiration suffers a complete loss of its cost price.

Given item economics and remaining shelf life, determine:
1. Opening asking price (initial quote to buyer)
2. Absolute seller floor price (minimum acceptable price below which selling is uneconomic)
3. Strategic rationale and expiry risk assessment.

Do not use hardcoded multipliers. Reason dynamically about margin versus spoilage urgency.

Return ONLY valid JSON matching:
{
  "opening_quote": 0.00,
  "seller_floor": 0.00,
  "strategy_label": "PREMIUM_HOLD" | "DYNAMIC_YIELD" | "AGGRESSIVE_CLEARANCE",
  "expiry_risk": "LOW" | "MODERATE" | "CRITICAL",
  "rationale": "Detailed strategic reasoning"
}"""

        sb_user = f"""ITEM PROFILE:
Product: {product_name}
Category: {item.get('category', 'Grocery')}
Cost Price: ${cost:.2f}
Retail Reference: ${retail:.2f}
Remaining Shelf Life: {rem_hours} hours
Expiry Regime: {regime}

Formulate your initial strategic pricing policy."""

        sb_res = await self.llm.call_agent(
            agent_name="StrategicBrain",
            system_prompt=sb_sys,
            user_prompt=sb_user,
            trial_id=trial_id,
            item_id=item["item_id"],
            temperature=0.2,
        )

        sb_quote = float(sb_res.get("opening_quote", retail))
        sb_floor = max(float(sb_res.get("seller_floor", cost)), cost)

        # 2. Bull Debater (Margin Advocate)
        bull_sys = """You are the Bull Debater on the pricing council.
Your mandate is to advocate for MARGIN MAXIMIZATION and resist premature price concessions.
Challenge whether the proposed price leaves profit on the table.

Return ONLY valid JSON:
{
  "recommended_quote": 0.00,
  "recommended_floor": 0.00,
  "argument": "Why higher price/margin is achievable and sustainable"
}"""
        bull_user = f"""ITEM: {product_name} | Cost: ${cost:.2f} | Retail: ${retail:.2f} | Remaining Life: {rem_hours}h
Strategic Brain Proposal: Quote=${sb_quote:.2f}, Floor=${sb_floor:.2f}
Present your margin-maximization argument."""

        bull_res = await self.llm.call_agent(
            agent_name="BullDebater",
            system_prompt=bull_sys,
            user_prompt=bull_user,
            trial_id=trial_id,
            item_id=item["item_id"],
            temperature=0.3,
        )

        # 3. Bear Debater (Waste Minimization Advocate)
        bear_sys = """You are the Bear Debater on the pricing council.
Your mandate is to advocate for WASTE MINIMIZATION and prevent terminal spoilage loss.
Challenge whether the proposed price risks an unsold outcome where full cost is lost.

Return ONLY valid JSON:
{
  "recommended_quote": 0.00,
  "recommended_floor": 0.00,
  "argument": "Why rapid clearance and volume velocity are necessary"
}"""
        bear_user = f"""ITEM: {product_name} | Cost: ${cost:.2f} | Retail: ${retail:.2f} | Remaining Life: {rem_hours}h
Strategic Brain Proposal: Quote=${sb_quote:.2f}, Floor=${sb_floor:.2f}
Present your waste-minimization argument."""

        bear_res = await self.llm.call_agent(
            agent_name="BearDebater",
            system_prompt=bear_sys,
            user_prompt=bear_user,
            trial_id=trial_id,
            item_id=item["item_id"],
            temperature=0.3,
        )

        # 4. Debate Judge (Synthesis)
        judge_sys = """You are the Debate Judge and Chief Commercial Officer.
Synthesize the Strategic Brain proposal, the Bull margin argument, and the Bear waste argument.
Establish the final binding opening asking price and minimum acceptable floor price.

Return ONLY valid JSON:
{
  "final_opening_quote": 0.00,
  "final_seller_floor": 0.00,
  "strategy_label": "PREMIUM_HOLD" | "DYNAMIC_YIELD" | "AGGRESSIVE_CLEARANCE",
  "expiry_risk": "LOW" | "MODERATE" | "CRITICAL",
  "rationale": "Synthesis rationale"
}"""

        judge_user = f"""ITEM: {product_name} | Cost: ${cost:.2f} | Retail: ${retail:.2f} | Remaining: {rem_hours}h
Strategic Brain: Quote=${sb_quote:.2f}, Floor=${sb_floor:.2f}
Bull Argument: Quote=${bull_res.get('recommended_quote', sb_quote):.2f}, Floor=${bull_res.get('recommended_floor', sb_floor):.2f} - "{bull_res.get('argument', '')}"
Bear Argument: Quote=${bear_res.get('recommended_quote', sb_quote):.2f}, Floor=${bear_res.get('recommended_floor', sb_floor):.2f} - "{bear_res.get('argument', '')}"

Produce the final binding strategic policy."""

        judge_res = await self.llm.call_agent(
            agent_name="DebateJudge",
            system_prompt=judge_sys,
            user_prompt=judge_user,
            trial_id=trial_id,
            item_id=item["item_id"],
            temperature=0.2,
        )

        final_quote = float(judge_res.get("final_opening_quote", sb_quote))
        final_floor = float(judge_res.get("final_seller_floor", sb_floor))
        
        # Enforce cost as lowest possible baseline safety constraint
        final_floor = max(final_floor, cost)
        final_quote = max(final_quote, final_floor)

        return StrategicPolicy(
            opening_quote=round(final_quote, 2),
            seller_floor=round(final_floor, 2),
            strategy_label=judge_res.get("strategy_label", "DYNAMIC_YIELD"),
            expiry_risk=judge_res.get("expiry_risk", regime),
            rationale=judge_res.get("rationale", sb_res.get("rationale", "")),
        )

    async def evaluate_buyer_counter(
        self,
        item: Dict[str, Any],
        policy: StrategicPolicy,
        buyer_counter_offer: float,
        buyer_message: str,
        current_seller_price: float,
        remaining_shelf_life_hours: int,
        conversation_history: List[Dict[str, Any]],
        trial_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Tactical pipeline invoked when buyer counters:
        RiskReader -> ListingDecider -> Spokesperson
        """
        product_name = item["product_name"]
        cost = float(item["cost_price"])
        retail = float(item["retail_reference"])

        history_text = "\n".join([
            f"Exchange {idx+1}: Buyer={h.get('buyer_action', '')} (${h.get('buyer_offer', 0):.2f}) | Seller Quote=${h.get('seller_quote', 0):.2f} Msg='{h.get('seller_message', '')}'"
            for idx, h in enumerate(conversation_history)
        ]) if conversation_history else "Opening counter-offer."

        # 1. RiskReader: Micro-behavioral signal analysis
        rr_sys = """You are an expert Behavioral Negotiation Analyst (RiskReader).
Analyze the buyer's observable counter-offer, communication style, and conversation history.
Infer behavioral signals such as bluffing probability and walk-away risk.
Do not assume hidden parameters; infer purely from observable interaction.

Return ONLY valid JSON:
{
  "bluffing_probability": 0.0 to 1.0,
  "walk_away_probability": 0.0 to 1.0,
  "detected_tactic": "LOWBALL" | "ANCHORING" | "URGENCY_PROBE" | "SINCERE_CONCESSION" | "FIRM_LIMIT",
  "risk_summary": "Concise assessment of buyer willingness to pay vs risk of losing the deal"
}"""

        rr_user = f"""ITEM: {product_name} | Retail: ${retail:.2f} | Remaining Life: {remaining_shelf_life_hours}h
Current Seller Price: ${current_seller_price:.2f}
Buyer Counter Offer: ${buyer_counter_offer:.2f}
Buyer Message: "{buyer_message}"
Conversation History:
{history_text}

Assess buyer behavioral signals."""

        rr_res = await self.llm.call_agent(
            agent_name="RiskReader",
            system_prompt=rr_sys,
            user_prompt=rr_user,
            trial_id=trial_id,
            item_id=item["item_id"],
            temperature=0.2,
        )

        bluff_prob = float(rr_res.get("bluffing_probability", 0.5))
        walk_prob = float(rr_res.get("walk_away_probability", 0.5))
        tactic = rr_res.get("detected_tactic", "ANCHORING")
        risk_sum = rr_res.get("risk_summary", "")

        # 2. Listing Agent Decider: Tactical Decision
        dec_sys = f"""You are the Listing Agent Decider executing bilateral negotiation for perishable food.
You must balance:
1. Realized margin (selling above cost ${cost:.2f})
2. Transaction probability (preventing the buyer from walking away)
3. Spoilage risk (remaining life {remaining_shelf_life_hours}h; unsold item loses entire cost ${cost:.2f})
4. Strategic policy guidance (Target Floor: ${policy.seller_floor:.2f})

ALLOWED ACTIONS:
- "ACCEPT": Accept the buyer's offer ${buyer_counter_offer:.2f} (only if it satisfies your economic criteria and is >= floor ${policy.seller_floor:.2f}).
- "CONCEDE": Offer a reduced price below current ${current_seller_price:.2f} but >= floor ${policy.seller_floor:.2f}.
- "HOLD": Re-quote the current price ${current_seller_price:.2f} or make a minimal adjustment.

Do not use hardcoded decision trees. Reason through the economic tradeoff.

Return ONLY valid JSON:
{{
  "action": "HOLD" | "CONCEDE" | "ACCEPT",
  "target_price": 0.00,
  "rationale": "Economic reason for this decision"
}}"""

        dec_user = f"""CURRENT STATE:
Item: {product_name} | Cost: ${cost:.2f} | Retail: ${retail:.2f} | Remaining Life: {remaining_shelf_life_hours}h
Seller Floor: ${policy.seller_floor:.2f} | Strategy: {policy.strategy_label}
Current Seller Ask: ${current_seller_price:.2f}
Buyer Offer: ${buyer_counter_offer:.2f} | Buyer Msg: "{buyer_message}"

BEHAVIORAL SIGNALS (RiskReader):
- Bluffing Probability: {bluff_prob:.2f}
- Walk-Away Probability: {walk_prob:.2f}
- Detected Tactic: {tactic}
- Assessment: {risk_sum}

Determine your action and target price."""

        dec_res = await self.llm.call_agent(
            agent_name="ListingDecider",
            system_prompt=dec_sys,
            user_prompt=dec_user,
            trial_id=trial_id,
            item_id=item["item_id"],
            temperature=0.2,
        )

        action = dec_res.get("action", "HOLD").upper()
        if action not in ("ACCEPT", "CONCEDE", "HOLD"):
            action = "HOLD"

        target_price = dec_res.get("target_price", current_seller_price)
        try:
            target_price = float(target_price)
        except Exception:
            target_price = current_seller_price

        # Hard system constraints
        if action == "ACCEPT":
            if buyer_counter_offer < policy.seller_floor:
                action = "CONCEDE"
                target_price = policy.seller_floor
            else:
                target_price = buyer_counter_offer
        elif action == "CONCEDE":
            target_price = max(target_price, policy.seller_floor)
            target_price = min(target_price, current_seller_price)
        elif action == "HOLD":
            target_price = max(current_seller_price, policy.seller_floor)

        target_price = round(target_price, 2)

        # 3. Spokesperson: Persuasive Communication
        spk_sys = f"""You are the Retail Spokesperson communicating with the customer.
Your job is to write a courteous, persuasive message reflecting the decision.
MANDATORY CONSTRAINT: You must communicate the EXACT target price of ${target_price:.2f}.
Do not change or renegotiate this price in your message.

Return ONLY valid JSON:
{{
  "message": "Persuasive, friendly message to the customer quoting ${target_price:.2f}"
}}"""

        spk_user = f"""Customer offered: ${buyer_counter_offer:.2f} with message: "{buyer_message}"
Decider Action: {action}
Mandated Price: ${target_price:.2f}

Draft the response message."""

        spk_res = await self.llm.call_agent(
            agent_name="Spokesperson",
            system_prompt=spk_sys,
            user_prompt=spk_user,
            trial_id=trial_id,
            item_id=item["item_id"],
            temperature=0.3,
        )

        return {
            "action": action,
            "target_price": target_price,
            "rationale": dec_res.get("rationale", ""),
            "spokesperson_message": spk_res.get("message", f"We can offer this for ${target_price:.2f}."),
            "risk_reader": {
                "bluffing_probability": bluff_prob,
                "walk_away_probability": walk_prob,
                "detected_tactic": tactic,
            },
        }
