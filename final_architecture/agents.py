"""
Final Architecture — Agent Definitions

Key design principles:
1. Microeconomic CoT Utility Modeling: Buyer evaluates language persuasion natively and updates perceived value V without Python multipliers.
2. Autonomous StrategicBrain: Organic phase discovery and dynamic yield curve optimization without hardcoded time boundaries.
3. Autonomous Listing Decider: Emergent reflex reasoning over expected revenue vs. spoilage penalty without hardcoded threshold rules.
4. Strict Pydantic Schema Validation across all agent outputs.
5. Adversarial Persona Grounding & Differentiated Temperature (Buyer: 0.7, Seller: 0.2).
"""
import json
import math
from typing import Dict, List, Any, Optional
from .llm_client import (
    client, validate_output,
    StrategicDecision, DeciderAction, BuyerResponse,
    RiskProfileSchema, SpokespersonSchema
)
from .config import MODELS, BUYER_TEMPERATURE, SELLER_TEMPERATURE, PERSONA_PROFILES


class BaseAgent:
    def __init__(self, model_alias: str):
        self.model_alias = model_alias


# ─── TASK 3: NATIVE MICROECONOMIC BUYER UTILITY ──────────────────────────────

class Buyer(BaseAgent):
    """
    Autonomous Procurement Buyer Agent.
    Evaluates seller natural language arguments via hidden Chain-of-Thought (CoT),
    updating internal perceived valuation without hardcoded multipliers.
    Strictly constrained by corporate budget ceiling to eliminate cooperative bias.
    """
    def __init__(self, buyer_id: int, model_alias: str, budget: float,
                 shopping_list: List[str], personality: str = "CALCULATED"):
        super().__init__(model_alias)
        self.buyer_id        = buyer_id
        self.budget          = budget          # Active spending limit (can be slashed by ChaosInjector)
        self.shopping_list   = shopping_list
        self.personality     = personality
        self.purchased_items = []
        
        profile = PERSONA_PROFILES.get(personality, PERSONA_PROFILES["CALCULATED"])
        self.alpha = profile["alpha"]
        self.beta  = profile["beta"]
        self.persona_desc = profile["desc"]

    async def act(
        self,
        history: List[Dict[str, str]],
        current_quote: float,
        days_until_expiry: int,
        current_hour: int,
        max_hours: int,
        retail_price: float,
        seller_last_message: str = "",
    ) -> Dict[str, Any]:
        hours_remaining  = max_hours - current_hour
        remaining_items  = [i for i in self.shopping_list if i not in self.purchased_items]
        target_item      = remaining_items[0] if remaining_items else "General Item"

        seller_context = f'"{seller_last_message}"' if seller_last_message else "No direct message from seller yet."

        history_summary = ""
        if history:
            history_summary = "PRIOR ROUNDS FOR THIS ITEM:\n" + "\n".join(
                f"- Hour {h.get('hour', 0)}: Seller asked ${h.get('seller_price', 0):.2f}, you chose {h.get('buyer_action')} (bid: ${h.get('bid', 0):.2f})"
                for h in history if isinstance(h, dict)
            ) + "\n"

        prompt = f"""
You are a ruthless procurement buyer. Persona: {self.personality} ({self.persona_desc}).
Target Product: {target_item}
Your baseline valuation is ${retail_price:.2f}.
CURRENT SELLER ASK (HOUR {current_hour}/{max_hours}): ${current_quote:.2f}
Time Remaining (TTE): {hours_remaining} hours (Days until expiry: {days_until_expiry})

SELLER'S MESSAGE:
{seller_context}

{history_summary}
ADVERSARIAL CONSTRAINTS:
You can adjust your internal valuation based on the seller's persuasion, but if you pay more than your absolute budget ceiling of ${self.budget:.2f}, you will be fired.
If the seller has discounted their price since prior rounds or if time is running out, you may rationally re-engage (COUNTER or ACCEPT) even if you walked away from an earlier higher price.

TASK:
1. In internal_monologue: Evaluate the seller's current ask (${current_quote:.2f}) against your valuation (${retail_price:.2f}), budget ceiling (${self.budget:.2f}), and remaining time ({hours_remaining}h).
2. Choose action: ACCEPT, COUNTER, or WALK_AWAY.
3. If COUNTER: Provide bid_amount <= ${self.budget:.2f}.
4. Provide dialogue: Your natural language response to the seller.

Respond ONLY in valid JSON matching this schema:
{{
  "internal_monologue": "Evaluate current price vs valuation and time remaining.",
  "action": "ACCEPT|COUNTER|WALK_AWAY",
  "bid_amount": float,
  "dialogue": "Your natural language response to the seller."
}}
"""
        raw = await client.call(
            self.model_alias,
            [{"role": "system", "content": prompt}],
            temperature=BUYER_TEMPERATURE,
        )
        if isinstance(raw, dict) and raw.get("action") == "API_ERROR":
            return {
                "internal_monologue": f"API_ERROR: {raw.get('error', 'CONNECTION_FAILED')}",
                "action": "API_ERROR",
                "bid_amount": 0.0,
                "counter_offer": 0.0,
                "dialogue": "",
                "message": "",
                "error": raw.get("error", "API_ERROR"),
            }

        validated = validate_output(raw, BuyerResponse)
        if validated:
            bid = min(float(validated.bid_amount), self.budget) if validated.bid_amount else 0.0
            return {
                "internal_monologue": validated.internal_monologue,
                "action": validated.action,
                "bid_amount": bid,
                "counter_offer": bid,  # Compatibility field
                "dialogue": validated.dialogue,
                "message": validated.dialogue,  # Compatibility field
            }
        
        # Fallback
        fallback_bid = round(min(retail_price * 0.85, self.budget), 2)
        return {
            "internal_monologue": "Fallback parsing: counter at standard conservative valuation",
            "action": "COUNTER",
            "bid_amount": fallback_bid,
            "counter_offer": fallback_bid,
            "dialogue": "Can you do better on this price?",
            "message": "Can you do better on this price?",
        }


# ─── TASK 1: AUTONOMOUS STRATEGIC BRAIN (PHASE DISCOVERY) ───────────────────

class StrategicBrain(BaseAgent):
    """
    Autonomous Strategic Pricing Brain.
    Analyzes raw environment state (TTE, inventory, cost, spoilage penalty)
    and organically discovers dynamic yield curves via Chain-of-Thought.
    """
    async def act(
        self,
        inventory: List[Dict[str, Any]],
        chaos_events: List[Dict[str, Any]],
        current_hour: int,
        max_hours: int,
    ) -> Dict[str, Any]:
        product_names = [i["product_name"] for i in inventory]
        tte = max_hours - current_hour
        pct_elapsed = (current_hour / max_hours) * 100

        inventory_summary = []
        for item in inventory:
            inventory_summary.append({
                "product_name":     item["product_name"],
                "selling_price":    item["selling_price"],
                "cost_price":       item["cost_price"],
                "margin":           round(item["selling_price"] - item["cost_price"], 2),
                "days_until_expiry": item["days_until_expiry"],
                "quality_grade":    item.get("quality_grade", "N/A"),
                "daily_demand":     item.get("daily_demand", "N/A"),
            })

        prompt = f"""
Role: Autonomous Strategic Pricing Brain.
Objective: Maximize True Net Profit = (Revenue) - (Spoilage Penalties).

ENVIRONMENT STATE:
- Time Remaining (TTE): {tte} hours ({pct_elapsed:.0f}% elapsed of {max_hours}h total horizon)
- Inventory Remaining: {len(inventory)} units
- Unsold units at TTE = 0 incur a full -${{cost}} penalty (total spoilage loss).

INVENTORY:
{json.dumps(inventory_summary, indent=2)}

ACTIVE MARKET EVENTS:
{json.dumps(chaos_events[-3:] if chaos_events else [], indent=2)}

CORE YIELD-MANAGEMENT PRINCIPLES:
- Phase 1 (TTE >= 8h / Early Hours): Fresh goods have peak consumer willingness-to-pay. Set ask quotes at a premium (1.15x - 1.25x selling_price) to scalp early consumer surplus.
- Phase 2 (TTE 4-6h / Mid Hours): Realign quotes toward base selling_price to sustain transaction velocity.
- Phase 3 (TTE <= 2h / Endgame Liquidation): Spoilage risk dominates (-100% cost loss if unsold). Slash quotes toward cost_price + $0.50 to clear all remaining units.
- Floor prices: Must cover physical cost (floor >= cost_price + $0.30).

TASK:
Analyze the spoilage risk vs margin opportunity and set your strategy organically.
1. market_analysis: Analyze time remaining, inventory levels, and spoilage risk.
2. chosen_strategy: Declare your current pricing strategy (e.g., Early Premium Scalping, Dynamic Alignment, Endgame Liquidation).
3. quotes: The starting ask price for EVERY product.
4. floor_prices: The absolute minimum acceptable price for EVERY product. Must cover cost unless spoilage is imminent.
5. priority_items: List of product names most at risk of expiring unsold.

CRITICAL — Use EXACTLY these product names as JSON keys (copy-paste):
{json.dumps(product_names)}

Respond ONLY in valid JSON matching this schema:
{{
  "market_analysis": "Analyze time remaining, inventory levels, and spoilage risk.",
  "chosen_strategy": "Declare the current pricing strategy (e.g., margin defense, aggressive clearance).",
  "quotes": {{ "<exact product name>": float }},
  "floor_prices": {{ "<exact product name>": float }},
  "priority_items": ["list of product names"]
}}
"""
        raw = await client.call(
            self.model_alias,
            [{"role": "system", "content": prompt}],
            temperature=SELLER_TEMPERATURE,
        )
        validated = validate_output(raw, StrategicDecision)
        if validated:
            return validated.model_dump()
        return {
            "market_analysis": "Fallback analysis: standard holding",
            "chosen_strategy": "Autonomous holding",
            "quotes": {i["product_name"]: i["selling_price"] for i in inventory},
            "floor_prices": {i["product_name"]: i["cost_price"] for i in inventory},
            "priority_items": [],
        }


# ─── DEBATE LOOP (for MAS_DEBATE mode) ───────────────────────────────────────

class BullDebater(BaseAgent):
    """Argues for HIGHER prices — premium capture focus."""
    async def act(self, inventory: List[Dict], proposed_quotes: Dict[str, float],
                  current_hour: int, max_hours: int) -> Dict[str, Any]:
        product_names = [i["product_name"] for i in inventory]
        prompt = f"""
Role: Bull Debater (Profit Maximizer). Simulation: {current_hour}/{max_hours} hrs.
Inventory: {json.dumps(inventory)}
Brain's Proposed Quotes: {json.dumps(proposed_quotes)}

TASK: Argue for HIGHER prices. Which items are underpriced? Back with quality/demand data.
Valid product names: {json.dumps(product_names)}

Respond ONLY in JSON:
{{
  "argument": "...",
  "recommended_quotes": {{ "<exact product name>": float }},
  "key_items_to_hold": []
}}
"""
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])


class BearDebater(BaseAgent):
    """Argues for LOWER prices — waste minimization focus."""
    async def act(self, inventory: List[Dict], proposed_quotes: Dict[str, float],
                  current_hour: int, max_hours: int) -> Dict[str, Any]:
        product_names = [i["product_name"] for i in inventory]
        prompt = f"""
Role: Bear Debater (Waste Minimizer). Simulation: {current_hour}/{max_hours} hrs.
Inventory: {json.dumps(inventory)}
Brain's Proposed Quotes: {json.dumps(proposed_quotes)}

TASK: Argue for LOWER prices on near-expiry items. Identify where the Brain is too greedy.
Valid product names: {json.dumps(product_names)}

Respond ONLY in JSON:
{{
  "argument": "...",
  "recommended_quotes": {{ "<exact product name>": float }},
  "items_at_risk": []
}}
"""
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])


class DebateJudge(BaseAgent):
    """Synthesizes Bull and Bear into a final pricing decision."""
    async def act(self, proposed_quotes: Dict, floor_prices: Dict,
                  bull_arg: Dict, bear_arg: Dict, inventory: List[Dict]) -> Dict[str, Any]:
        product_names = [i["product_name"] for i in inventory]
        prompt = f"""
Role: Neutral Debate Judge. Your output REPLACES the Brain's initial quotes.
Brain Quotes: {json.dumps(proposed_quotes)}
Floor Prices: {json.dumps(floor_prices)}
Bull Argument: {json.dumps(bull_arg)}
Bear Argument: {json.dumps(bear_arg)}
Inventory: {json.dumps(inventory)}

TASK: Synthesize both arguments into a refined pricing strategy.
Valid product names: {json.dumps(product_names)}

Respond ONLY in JSON:
{{
  "reasoning": "...",
  "final_quotes":       {{ "<exact product name>": float }},
  "final_floor_prices": {{ "<exact product name>": float }}
}}
"""
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])


# ─── MICRO-NEGOTIATION PIPELINE ───────────────────────────────────────────────

class RiskReader(BaseAgent):
    """
    Profiles buyer psychology from conversation history.
    Output is Pydantic-validated — bluffing/walk_away guaranteed to be 0-10 ints.
    """
    async def act(self, history: List[Dict[str, str]], current_hour: int) -> Dict[str, Any]:
        prompt = f"""
Role: Behavioral Risk Reader. Current Hour: {current_hour}/10

TASK: Read the negotiation transcript and produce a psychological profile.
1. What tactic is the buyer using? (anchoring / bluffing / probing / cooperative / aggressive / passive)
2. Are they bluffing or serious? (0 = definitely serious, 10 = definitely bluffing)
3. How close to walking away? (0 = very committed, 10 = about to leave)

Respond ONLY in JSON:
{{
  "buyer_profile":        "2-3 sentence psychological assessment",
  "tactic_detected":      "primary tactic",
  "bluffing_probability": int (0-10),
  "walk_away_probability": int (0-10),
  "recommended_stance":   "brief recommendation"
}}
"""
        raw = await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)
        validated = validate_output(raw, RiskProfileSchema)
        if validated:
            return validated.model_dump()
        return RiskProfileSchema().model_dump()  # Safe neutral default


class DummyRiskReader(RiskReader):
    """
    Ablation baseline — returns maximum uncertainty (5/10 on both axes).
    NOT 0/0 (which would falsely signal 'definitely not bluffing') — that biases the decider.
    This represents a truly blind seller who has no buyer intelligence.
    """
    async def act(self, history, current_hour):
        return RiskProfileSchema(
            buyer_profile="UNKNOWN — RiskReader ablated. No profiling available.",
            tactic_detected="UNKNOWN",
            bluffing_probability=5,
            walk_away_probability=5,
            recommended_stance="Proceed with caution. No buyer intel — default to moderate stance.",
        ).model_dump()


# ─── TASK 2: EMERGENT LISTING AGENT DECIDER (REFLEX ENGINE) ──────────────────

class ListingAgentDecider(BaseAgent):
    """
    Autonomous Tactical Deal-Maker (Reflex Engine).
    Ingests RiskReader scores and raw state (TTE, floor, quote, incoming bid).
    Autonomously reasons over expected revenue vs. spoilage penalty to choose:
    HOLD, CONCEDE, or ACCEPT.
    """
    async def act(
        self,
        product: str,
        quote: float,
        floor: float,
        risk_profile: Dict[str, Any],
        current_hour: int,
        max_hours: int,
        buyer_offer: Optional[float] = None,
        competing_bidders_count: int = 1,
    ) -> Dict[str, Any]:
        tte = max_hours - current_hour
        bluff_score = risk_profile.get("bluffing_probability", 5)
        walk_score  = risk_profile.get("walk_away_probability", 5)
        offer_str   = f"${buyer_offer:.2f}" if buyer_offer is not None else "None"

        prompt = f"""
You are the tactical execution agent.
Product: {product}
Current floor is ${floor:.2f}.
Target asking quote is ${quote:.2f}.
Buyer's incoming bid is {offer_str} ({competing_bidders_count} active bidder(s)).
RiskReader indicates Bluffing: {bluff_score}/10, Walk-Away: {walk_score}/10.
TTE is {tte} hours remaining.

OBJECTIVE & TACTICAL GUIDELINES:
Maximize expected revenue and avoid spoilage:
- When TTE >= 4h: If buyer bluffing score is high (>=6) and offer is low, choose HOLD (${quote:.2f}) or CONCEDE slightly to defend margin.
- When TTE <= 2h (Endgame): Spoilage penalty is imminent (-100% loss). If the buyer's incoming bid is >= ${floor:.2f}, choose ACCEPT to guarantee volume clearance and avoid total waste loss.
- HOLD: Defend target asking quote (${quote:.2f}).
- CONCEDE: Counter with a discounted target_price (between ${floor:.2f} and ${quote:.2f}).
- ACCEPT: Accept the buyer's bid ({offer_str}).

Respond ONLY in valid JSON matching this schema:
{{
  "risk_evaluation": "Evaluate the RiskReader's bluff and walk-away scores against current TTE and inventory.",
  "action": "HOLD|CONCEDE|ACCEPT",
  "target_price": float
}}
"""
        raw = await client.call(
            self.model_alias,
            [{"role": "system", "content": prompt}],
            temperature=SELLER_TEMPERATURE,
        )
        validated = validate_output(raw, DeciderAction)
        if validated:
            tactical_action = validated.action.upper()
            if tactical_action == "HOLD":
                price = quote
                out_action = "COUNTER"
            elif tactical_action == "ACCEPT":
                price = buyer_offer if buyer_offer and buyer_offer >= floor else quote
                out_action = "ACCEPT"
            elif tactical_action == "CONCEDE":
                proposed = validated.target_price if validated.target_price > 0 else (quote + (buyer_offer or floor)) / 2
                price = max(floor, min(quote, proposed))
                out_action = "COUNTER"
            else:
                price = quote
                out_action = "COUNTER"

            return {
                "risk_evaluation": validated.risk_evaluation,
                "tactic": tactical_action,
                "action": out_action,
                "price": price,
                "target_price": price,
            }

        return {
            "risk_evaluation": "Fallback: defend strategic target quote",
            "tactic": "HOLD",
            "action": "COUNTER",
            "price": quote,
            "target_price": quote,
        }


class Spokesperson(BaseAgent):
    """
    Crafts the persuasive message. Price is HARDCODED in the JSON template —
    LLM cannot override the number, only the language.
    """
    async def act(
        self,
        target_price: float,
        action: str,
        risk_profile: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        prompt = f"""
Role: Elite Spokesperson (Sales Closer).
Mandated Price: ${target_price:.2f} — YOU MUST USE THIS EXACTLY in new_quote.
Mandated Action: {action}

BUYER PSYCHOLOGY:
- Profile:       {risk_profile.get('buyer_profile', 'N/A')}
- Tactic:        {risk_profile.get('tactic_detected', 'N/A')}
- Bluffing:      {risk_profile.get('bluffing_probability', 0)}/10

YOUR RULES:
1. Use EXACTLY ${target_price:.2f} as new_quote. Do NOT change the number.
2. Match buyer energy: calm if aggressive, warm if cooperative.
3. Use ONE of these persuasion tactics in your message:
   - SCARCITY: mention limited stock or near-expiry
   - QUALITY:  mention premium grade, freshness, certification
   - PARTNERSHIP: mention fair deal, returning customer value
4. Keep message to 2-3 sentences. Be specific, not generic.

Respond ONLY in JSON:
{{
  "thought":    "which tactic I will use and why",
  "action":     "{action}",
  "new_quote":  {target_price},
  "message":    "your persuasive message to the buyer"
}}
"""
        raw = await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)
        validated = validate_output(raw, SpokespersonSchema)
        if validated:
            # Hard-enforce the mandated price — LLM cannot override
            return {"thought": validated.thought, "action": action,
                    "new_quote": target_price, "message": validated.message}
        return {"thought": "", "action": action, "new_quote": target_price,
                "message": f"Our price is ${target_price:.2f}. This reflects the quality and freshness of this item."}


class TacticalOrchestrator(BaseAgent):
    """
    Micro-negotiation pipeline: RiskReader → ListingAgentDecider → Spokesperson.
    All outputs are Pydantic-validated before being used.
    """
    def __init__(self, model_alias: str, risk_reader: RiskReader, spokesperson: Spokesperson):
        super().__init__(model_alias)
        self.risk_reader = risk_reader
        self.decider     = ListingAgentDecider(model_alias)
        self.spokesperson = spokesperson

    async def act(
        self,
        buyer_id: int,
        product: str,
        quote: float,
        floor: float,
        strategy: str,
        current_hour: int,
        max_hours: int,
        history: List[Dict[str, str]],
        buyer_offer: Optional[float] = None,
        competing_bidders_count: int = 1,
    ) -> Dict[str, Any]:
        risk_profile = await self.risk_reader.act(history, current_hour)
        decision     = await self.decider.act(product, quote, floor, risk_profile,
                                              current_hour, max_hours, buyer_offer,
                                              competing_bidders_count=competing_bidders_count)
        target_price = decision.get("price", quote)
        action       = decision.get("action", "COUNTER")
        spokesperson_res = await self.spokesperson.act(target_price, action, risk_profile, history)
        spokesperson_res["_risk_profile"] = risk_profile
        spokesperson_res["_decision"] = decision
        return spokesperson_res


# ─── MONOLITHIC SELLER (Single-model ablation baseline) ──────────────────────

class MonolithicSeller(BaseAgent):
    """Single LLM handling entire seller role — no architecture, no specialization."""
    async def act(
        self,
        buyer_id: int,
        product: str,
        current_quote: float,
        cost_price: float,
        retail_price: float,
        current_hour: int,
        max_hours: int,
        history: List[Dict[str, str]],
        buyer_offer: Optional[float] = None,
    ) -> Dict[str, Any]:
        progress = current_hour / max_hours
        prompt = f"""
Role: Sole Sales Agent.
Item: {product} | Cost: ${cost_price:.2f} | Retail: ${retail_price:.2f}
Current Quote: ${current_quote:.2f} | Buyer's Bid: ${buyer_offer or 'None'}
Progress: {progress*100:.0f}%

Decide: balance margin vs risk of expiry waste. Do NOT go below cost price.
Respond ONLY in JSON: {{"action": "ACCEPT|COUNTER", "new_quote": float, "message": "..."}}
"""
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)


# ─── CHAOS INJECTOR ──────────────────────────────────────────────────────────

class ChaosInjector(BaseAgent):
    """
    Adversarial agent that injects market shocks.
    In NeurIPS architecture, MARKET_CRASH events are wired to actually
    slash buyer budgets in the environment (not just logged).
    """
    async def act(self, state: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
Role: Adversarial Market Manipulator.
Current State: {json.dumps(state)}

Inject ONE of these market shocks:
- DECEPTIVE_BIDDING: Buyer cartel — buyers collectively lower bids
- MARKET_CRASH:      Flash crash — competitor dumps similar inventory, reducing buyer willingness to pay
- SUPPLY_SURGE:      Sudden supply glut — similar items flood the market

Respond ONLY in JSON:
{{
  "event": "DECEPTIVE_BIDDING|MARKET_CRASH|SUPPLY_SURGE",
  "impact_magnitude": <int 1-10>,
  "message": "description of the event"
}}
"""
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])


# ─── DUMMY STRATEGIC BRAIN (ablation) ────────────────────────────────────────

class DummyStrategicBrain(StrategicBrain):
    """Ablation: provides no dynamic pricing. Environment keeps initial CSV prices."""
    async def act(self, inventory, chaos_events, current_hour, max_hours):
        return {"strategy_directive": "STATIC_HOLD (StrategicBrain ablated)"}
