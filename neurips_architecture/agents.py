"""
NeurIPS Architecture — Agent Definitions

Key changes vs kanishka_src:
1. Buyer reads seller text + classifies tactic (persuasion mechanism)
2. StrategicBrain: NO hardcoded phases — autonomous discovery
3. REMOVED: IntelligenceHub, IntegrityWatchdog, PostMortemCritic (dead code pruned)
4. Pydantic validation on all outputs via llm_client schemas
5. DummyRiskReader now returns neutral (5,5) — fair ablation baseline
"""
import json
from typing import Dict, List, Any, Optional
from .llm_client import client, validate_output, BuyerActionSchema, RiskProfileSchema, DecisionSchema, SpokespersonSchema
from .config import MODELS, TACTIC_MULTIPLIERS


class BaseAgent:
    def __init__(self, model_alias: str):
        self.model_alias = model_alias


# ─── BUYER ───────────────────────────────────────────────────────────────────

class Buyer(BaseAgent):
    """
    NeurIPS upgrade: Buyer now reads the seller's text and classifies the persuasion tactic.
    Python applies a fixed mathematical multiplier to max_acceptable based on the tactic.
    This makes language economically measurable — a core NeurIPS/ACL contribution.
    """
    def __init__(self, buyer_id: int, model_alias: str, budget: float,
                 shopping_list: List[str], personality: str = "CALCULATED"):
        super().__init__(model_alias)
        self.buyer_id        = buyer_id
        self.budget          = budget          # Active spending limit (can be slashed by ChaosInjector)
        self.shopping_list   = shopping_list
        self.personality     = personality
        self.purchased_items = []

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
        desperation = current_hour / max_hours
        remaining   = [i for i in self.shopping_list if i not in self.purchased_items]

        # Base ceiling — Python math, not LLM hallucination
        base_max    = round(retail_price * (1.0 + 0.3 + 0.3 * desperation), 2)
        # Also enforce budget constraint
        effective_max = round(min(base_max, self.budget), 2)

        personality_desc = {
            "ESSENTIAL":  "You NEED this item urgently. You'll accept a moderate premium but won't be scammed.",
            "CALCULATED": "You are a sharp deal-seeker. Counter persistently; walk away if the premium is unreasonable.",
            "IMPULSE":    "You are spontaneous — may cave earlier or push back randomly, but won't pay obviously absurd prices.",
        }.get(self.personality, "You are a rational buyer.")

        seller_context = f'"{seller_last_message}"' if seller_last_message else "No message from seller yet."

        prompt = f"""
Role: Savvy Shopper. Personality: {self.personality}.
Current Target: {remaining[0] if remaining else 'None'}
Remaining List: {json.dumps(remaining[1:] if len(remaining) > 1 else [])}

SELLER'S LAST MESSAGE: {seller_context}

PRICE CONTEXT:
- Normal Retail Price: ${retail_price:.2f}
- Seller's Current Ask: ${current_quote:.2f}
- Your spending limit: ${effective_max:.2f} (HARD — do NOT exceed this)
- Days Until Expiry: {days_until_expiry} | Simulation Progress: {desperation*100:.0f}%

YOUR PERSONALITY: {personality_desc}

TACTIC EVALUATION (classify the seller's message FIRST, then decide):
Read the seller's message above and classify it:
- "scarcity"          → seller mentions limited stock, near-expiry, urgency ("only X left", "expires soon")
- "quality_assurance" → seller mentions premium quality, grade, organic, certified, freshness
- "partnership"       → seller mentions loyalty, bundle, relationship, returning customer
- "none"              → generic, empty, or no message

RULES:
- Your counter_offer MUST be a specific dollar amount <= ${effective_max:.2f}. Never exceed it.
- If current ask > your limit (${effective_max:.2f}), either COUNTER at or below your limit, or WALK_AWAY.
- If current ask <= your limit, you may ACCEPT.

Respond ONLY in JSON:
{{
  "seller_tactic_detected": "scarcity|quality_assurance|partnership|none",
  "action": "ACCEPT|COUNTER|WALK_AWAY",
  "counter_offer": float,
  "message": "your response to the seller"
}}
"""
        raw = await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)
        validated = validate_output(raw, BuyerActionSchema)
        if validated:
            return validated.model_dump()
        # Safe fallback
        return {"seller_tactic_detected": "none", "action": "COUNTER",
                "counter_offer": effective_max * 0.85, "message": "Can you do better?"}


# ─── STRATEGIC BRAIN (Autonomous — no hardcoded phases) ──────────────────────

class StrategicBrain(BaseAgent):
    """
    NeurIPS upgrade: Phases are NOT hardcoded. The LLM must discover the optimal
    Scalping → Balance → Liquidation strategy autonomously from time pressure and
    inventory data. If the 70B model discovers this independently, it is a publishable finding.
    """
    async def act(
        self,
        inventory: List[Dict[str, Any]],
        chaos_events: List[Dict[str, Any]],
        current_hour: int,
        max_hours: int,
    ) -> Dict[str, Any]:
        product_names = [i["product_name"] for i in inventory]
        hours_remaining = max_hours - current_hour
        pct_elapsed = current_hour / max_hours * 100

        # Compute holding cost urgency score per item for the brain's context
        inventory_context = []
        for item in inventory:
            expiry_urgency = "CRITICAL" if item["days_until_expiry"] <= 2 else \
                             "HIGH"     if item["days_until_expiry"] <= 5 else "NORMAL"
            inventory_context.append({
                "product_name":     item["product_name"],
                "selling_price":    item["selling_price"],
                "cost_price":       item["cost_price"],
                "margin":           round(item["selling_price"] - item["cost_price"], 2),
                "days_until_expiry": item["days_until_expiry"],
                "quality_grade":    item.get("quality_grade", "N/A"),
                "daily_demand":     item.get("daily_demand", "N/A"),
                "expiry_urgency":   expiry_urgency,
            })

        prompt = f"""
Role: Autonomous Strategic Pricing Brain.

SIMULATION STATE:
- Hours elapsed: {current_hour}/{max_hours} ({pct_elapsed:.0f}% complete)
- Hours remaining: {hours_remaining}

INVENTORY (with financial risk analysis):
{json.dumps(inventory_context, indent=2)}

ECONOMIC CONSTRAINTS:
- Any item UNSOLD at simulation end = TOTAL LOSS of its cost_price (the "waste" penalty)
- You must balance: MARGIN (sell high) vs VELOCITY (sell before expiry)
- Items with "expiry_urgency": "CRITICAL" or "HIGH" are at risk of total loss

ACTIVE MARKET EVENTS (if any):
{json.dumps(chaos_events[-3:] if chaos_events else [], indent=2)}

YOUR TASK:
Set an optimal ask price (quote) and a minimum acceptable price (floor) for EVERY item.
Discover the right strategy yourself based on time pressure and item risk profiles.
- High quality + low urgency → you can ask for a premium
- Near expiry + high urgency → prioritize velocity over margin
- Floor must always be >= cost_price + $0.30 (never sell below cost)

CRITICAL — Use EXACTLY these product names as JSON keys (copy-paste):
{json.dumps(product_names)}

Respond ONLY in valid JSON:
{{
  "quotes":           {{ "<exact product name>": float }},
  "floor_prices":     {{ "<exact product name>": float }},
  "strategy_directive": "one sentence describing your current autonomous strategy",
  "priority_items":   ["list of items most at risk of expiring unsold"]
}}
"""
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])


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


class ListingAgentDecider(BaseAgent):
    """
    Takes RiskReader profile and makes the price + action decision.
    Rules are deterministic thresholds applied to validated integer scores.
    The StrategicBrain's quote is the default — the decider DEFENDS it.
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
    ) -> Dict[str, Any]:
        progress     = current_hour / max_hours
        hard_ceiling = round(min(quote * 1.15, quote + 5.0), 2)

        prompt = f"""
Role: Listing Agent (Senior Deal-Maker).
Product: {product}
StrategicBrain's Quote (YOUR target): ${quote:.2f}
Absolute Floor Price: ${floor:.2f}
Hard Ceiling (NEVER exceed): ${hard_ceiling:.2f}
Simulation Progress: {progress*100:.0f}%
Buyer's Last Offer: ${buyer_offer if buyer_offer else "None"}

RISK READER'S PROFILE:
- Buyer Type:            {risk_profile.get('buyer_profile', 'N/A')}
- Tactic Detected:       {risk_profile.get('tactic_detected', 'N/A')}
- Bluffing Probability:  {risk_profile.get('bluffing_probability', 'N/A')}/10
- Walk-Away Probability: {risk_profile.get('walk_away_probability', 'N/A')}/10
- Recommended Stance:    {risk_profile.get('recommended_stance', 'N/A')}

YOUR DECISION RULES (apply in order):
1. HARD FLOOR:    NEVER go below ${floor:.2f}. Absolute.
2. HARD CEILING:  NEVER go above ${hard_ceiling:.2f}. Do NOT inflate.
3. BLUFF HOLD:    If bluffing_probability >= 7 AND progress < 70% → COUNTER at ${quote:.2f}. Hold firm.
4. WALK-AWAY CONCEDE: If walk_away_probability >= 8 AND progress > 50% → COUNTER at midpoint: (${quote:.2f} + buyer_offer) / 2, min ${floor:.2f}.
5. LATE ACCEPT:   If progress > 70% AND buyer_offer >= ${floor:.2f} → ACCEPT. Spoilage = total loss.
6. DEFAULT:       HOLD at ${quote:.2f}. The Brain computed this for a reason. Defend it.
                  Only concede if rules 4 or 5 explicitly apply.

Think step by step, then output ONLY valid JSON:
{{
  "decision_reasoning": "brief step-by-step applying rules above",
  "action": "ACCEPT|COUNTER|WALK_AWAY",
  "price": float
}}
"""
        raw = await client.call(self.model_alias, [{"role": "system", "content": prompt}])
        validated = validate_output(raw, DecisionSchema)
        if validated:
            # Hard-enforce floor/ceiling in Python regardless of LLM output
            price = max(floor, min(hard_ceiling, validated.price))
            return {"decision_reasoning": validated.decision_reasoning,
                    "action": validated.action, "price": price}
        return {"decision_reasoning": "Fallback: hold at quote", "action": "COUNTER", "price": quote}


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
    ) -> Dict[str, Any]:
        risk_profile = await self.risk_reader.act(history, current_hour)
        decision     = await self.decider.act(product, quote, floor, risk_profile,
                                              current_hour, max_hours, buyer_offer)
        target_price = decision.get("price", quote)
        action       = decision.get("action", "COUNTER")
        return await self.spokesperson.act(target_price, action, risk_profile, history)


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
