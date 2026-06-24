import re
import json
from typing import Dict, List, Any, Optional
from .llm_client import client
from .config import MODELS

class BaseAgent:
    def __init__(self, model_alias: str):
        self.model_alias = model_alias

class Buyer(BaseAgent):
    def __init__(self, buyer_id: int, model_alias: str, budget: float, shopping_list: List[str], personality: str = "CALCULATED"):
        super().__init__(model_alias)
        self.buyer_id = buyer_id
        self.budget = budget # Total budget for the whole list
        self.shopping_list = shopping_list 
        self.personality = personality # ESSENTIAL, CALCULATED, IMPULSE
        self.purchased_items = []

    async def act(self, history: List[Dict[str, str]], current_quote: float, days_until_expiry: int, current_hour: int, max_hours: int, retail_price: float) -> Dict[str, Any]:
        desperation = current_hour / max_hours
        remaining_items = [i for i in self.shopping_list if i not in self.purchased_items]
        
        # Per-item ceiling: max 30% premium at start, up to 60% if very desperate — never more.
        max_acceptable = round(retail_price * (1.0 + 0.3 + 0.3 * desperation), 2)
        
        personality_prompts = {
            "ESSENTIAL": "You NEED this item urgently and will accept slightly higher prices, but you know the retail price and won't be scammed.",
            "CALCULATED": "You are a sharp deal-seeker. You will counter persistently and walk away if the premium exceeds what's reasonable.",
            "IMPULSE": "You are spontaneous. You may cave earlier or push back randomly, but you still won't pay obviously absurd prices."
        }

        prompt = f"""
        Role: Savvy Shopper. Personality: {self.personality}.
        Current Target: {remaining_items[0] if remaining_items else 'None'}
        Remaining Shopping List: {json.dumps(remaining_items[1:] if len(remaining_items) > 1 else [])}

        PRICE CONTEXT:
        - Normal Retail Price: ${retail_price:.2f}
        - Seller's Current Quote: ${current_quote:.2f}
        - YOUR HARD LIMIT: ${max_acceptable:.2f}  ← You MUST NOT offer or accept above this. Ever.
        - Days Until Expiry: {days_until_expiry} | Simulation Progress: {desperation*100:.0f}%

        RULES:
        - {personality_prompts.get(self.personality)}
        - If the seller's quote is above your hard limit (${max_acceptable:.2f}), WALK_AWAY or COUNTER at or below ${max_acceptable:.2f}.
        - Your counter_offer MUST be a specific dollar amount <= ${max_acceptable:.2f}. Never exceed it.
        
        Respond ONLY in JSON: {{"action": "ACCEPT|WALK_AWAY|COUNTER", "counter_offer": float, "message": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)



# --- MACRO AGENTS (BRAIN + DEBATE LOOP) ---

class IntelligenceHub(BaseAgent):
    """Combines IoT Sentinel + Market Scout + Sentiment."""
    async def act(self, inventory: List[Dict[str, Any]], buyers_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"""
        Role: Intelligence Hub. 
        Inventory: {json.dumps(inventory)}
        
        TASK: Analyze Predictive Metrics.
        - Flag items that need immediate price drops to avoid total loss (Waste Mitigation).
        - Identify 'High Demand' items where we can raise the quote.
        
        Respond ONLY in JSON: 
        {{
            "high_risk_items": [],
            "premium_items": [],
            "overall_market_status": "STABLE|VOLATILE"
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class StrategicBrain(BaseAgent):
    """Combines Yield Analyst + Chief Orchestrator."""
    async def act(self, intel: Dict[str, Any], inventory: List[Dict[str, Any]], chaos_events: List[Dict[str, Any]], current_hour: int, max_hours: int) -> Dict[str, Any]:
        progress = current_hour / max_hours
        
        if progress < 0.4:
            phase = "PREMIUM_SCALPING"
            desc = "Maximize margins on all items. Quote +20% over selling_price."
        elif progress < 0.7:
            phase = "MARKET_BALANCE"
            desc = "Align with standard selling_price. Floor = Cost + 15%."
        else:
            phase = "SMART_LIQUIDATION"
            desc = "Prioritize volume but avoid selling below Cost + 5% unless absolutely necessary."

        product_names = [i['product_name'] for i in inventory]
        prompt = f"""
        Role: Strategic Brain. Phase: {phase} | Progress: {progress*100:.0f}%
        Intelligence: {json.dumps(intel)}
        Inventory: {json.dumps(inventory)}
        
        TASK: {desc}
        - Do not panic. The human manager often sells too cheap; stay more rational.
        - Set floors carefully. Even in LIQUIDATION, try to keep floors at Cost + $0.50.
        
        CRITICAL: Use EXACT product names as JSON keys. The valid product names are:
        {json.dumps(product_names)}
        
        Respond ONLY in JSON:
        {{
            "quotes": {{ "<exact product name from list above>": float }},
            "floor_prices": {{ "<exact product name from list above>": float }},
            "strategy_directive": "{phase}",
            "priority_items": []
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class BullDebater(BaseAgent):
    """Argues for HIGHER prices and holding firm to maximize margins."""
    async def act(self, intel: Dict[str, Any], inventory: List[Dict[str, Any]], proposed_quotes: Dict[str, float], current_hour: int, max_hours: int) -> Dict[str, Any]:
        progress = current_hour / max_hours
        prompt = f"""
        Role: Bull Debater (Profit Maximizer). Progress: {progress*100:.0f}%
        Intelligence: {json.dumps(intel)}
        Inventory: {json.dumps(inventory)}
        Brain's Proposed Quotes: {json.dumps(proposed_quotes)}
        
        TASK: Argue why prices should be HIGHER. Identify items where we are leaving money on the table.
        - Back your argument with demand data and quality grades.
        - Ignore spoilage fears unless absolutely critical. Focus on premium capture.
        
        Respond ONLY in JSON:
        {{
            "argument": "...",
            "recommended_quotes": {{ "item_name": float }},
            "key_items_to_hold": []
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class BearDebater(BaseAgent):
    """Argues for LOWER prices and faster volume to minimize waste."""
    async def act(self, intel: Dict[str, Any], inventory: List[Dict[str, Any]], proposed_quotes: Dict[str, float], current_hour: int, max_hours: int) -> Dict[str, Any]:
        progress = current_hour / max_hours
        prompt = f"""
        Role: Bear Debater (Waste Minimizer). Progress: {progress*100:.0f}%
        Intelligence: {json.dumps(intel)}
        Inventory: {json.dumps(inventory)}
        Brain's Proposed Quotes: {json.dumps(proposed_quotes)}
        
        TASK: Argue why prices should be LOWER. Identify near-expiry items that will spoil unsold.
        - Focus on the cost of holding vs the cost of discounting.
        - Point out where the Brain is being too greedy.
        
        Respond ONLY in JSON:
        {{
            "argument": "...",
            "recommended_quotes": {{ "item_name": float }},
            "items_at_risk": []
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class DebateJudge(BaseAgent):
    """Synthesizes Bull and Bear arguments into a final pricing decision."""
    async def act(self, proposed_quotes: Dict[str, float], floor_prices: Dict[str, float], bull_arg: Dict[str, Any], bear_arg: Dict[str, Any], inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"""
        Role: Neutral Debate Judge.
        Brain's Initial Quotes: {json.dumps(proposed_quotes)}
        Initial Floors: {json.dumps(floor_prices)}
        Bull Argument: {json.dumps(bull_arg)}
        Bear Argument: {json.dumps(bear_arg)}
        Inventory Context: {json.dumps(inventory)}
        
        TASK: You are the final arbitrator. Read both arguments and synthesize a refined pricing strategy.
        - You may choose to hold prices high on premium items (siding with Bull).
        - You may choose to cut prices on near-expiry items (siding with Bear).
        - Your output will REPLACE the Brain's initial quotes and floors.
        
        Respond ONLY in JSON:
        {{
            "reasoning": "...",
            "final_quotes": {{ "item_name": float }},
            "final_floor_prices": {{ "item_name": float }}
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

# --- KANISHKA'S MICRO-NEGOTIATION AGENTS (REPLACES TACTICAL NEGOTIATOR) ---

class MonolithicSeller(BaseAgent):
    """A single LLM handling the entire seller role (no architecture)."""
    async def act(self, buyer_id: int, product: str, current_quote: float, cost_price: float, retail_price: float, current_hour: int, max_hours: int, history: List[Dict[str, str]], buyer_offer: Optional[float] = None) -> Dict[str, Any]:
        progress = current_hour / max_hours
        prompt = f"""
        Role: Sole Sales Agent.
        Item: {product}
        Cost Price: ${cost_price:.2f}
        Normal Retail Price: ${retail_price:.2f}
        Current Quote: ${current_quote:.2f}
        Simulation Progress: {progress*100:.0f}%
        Buyer's Bid: ${buyer_offer if buyer_offer else 'None'}

        TASK:
        You are the only agent negotiating with this buyer. You must balance profit margin vs risk of the item expiring (Waste).
        - Analyze the buyer's history to guess their urgency.
        - Decide on a new price. DO NOT go below Cost Price.
        - Draft a persuasive message to close the deal.
        
        Respond ONLY in JSON: {{"action": "ACCEPT|COUNTER", "new_quote": float, "message": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)

class RiskReader(BaseAgent):
    """Profiles the buyer based on chat history to detect bluffs and urgency."""
    async def act(self, history: List[Dict[str, str]], current_hour: int) -> Dict[str, Any]:
        prompt = f"""
        Role: Behavioral Risk Reader.
        Current Hour: {current_hour}/10
        
        TASK: Read the buyer's messages in the negotiation transcript and produce a psychological profile.
        1. What tactic is the buyer using? (anchoring, probing, bluffing, cooperative, aggressive, passive)
        2. Are they bluffing or serious? (rate 0-10, where 10 = definitely bluffing)
        3. How close are they to walking away? (rate 0-10, where 10 = about to walk)
        
        Respond ONLY in JSON:
        {{
            "buyer_profile": "2-3 sentence psychological assessment",
            "tactic_detected": "primary tactic name",
            "bluffing_probability": int,
            "walk_away_probability": int,
            "recommended_stance": "brief recommendation for the decision-maker"
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)

class DummyRiskReader(RiskReader):
    """Ablated Risk Reader that provides a neutral/unknown profile (not falsely optimistic).
    
    Returns 5/10 for both bluffing and walk-away probability — this represents maximum
    uncertainty (i.e., the agent truly knows nothing). Returning 0/0 would incorrectly
    signal 'definitely not bluffing, definitely not walking away', biasing the decider
    to over-concede and giving No_RiskReader an unfair PCR advantage.
    """
    async def act(self, history, current_hour):
        return {
            "buyer_profile": "UNKNOWN — RiskReader is ablated. No psychological profiling available.",
            "tactic_detected": "UNKNOWN",
            "bluffing_probability": 5,
            "walk_away_probability": 5,
            "recommended_stance": "Proceed with caution. No buyer intel available — default to moderate stance."
        }

class Spokesperson(BaseAgent):
    """Crafts the final persuasive message using the RiskReader profile."""
    async def act(self, target_price: float, action: str, risk_profile: Dict[str, Any], history: List[Dict[str, str]]) -> Dict[str, Any]:
        prompt = f"""
        Role: Elite Spokesperson (Sales Closer).
        Target Price to Offer: ${target_price:.2f}
        Action Mandated: {action}
        
        BUYER PSYCHOLOGY (from Risk Reader):
        - Profile: {risk_profile.get('buyer_profile', 'N/A')}
        - Tactic: {risk_profile.get('tactic_detected', 'N/A')}
        - Bluffing Prob: {risk_profile.get('bluffing_probability', 0)}/10
        
        YOUR RULES:
        1. You MUST use exactly the price and action mandated. Do NOT change the numbers.
        2. Match the buyer's energy: if they're aggressive, be calm but firm.
        3. If the buyer is bluffing, smoothly deflect their complaints and justify the premium.
        4. Draft a concise, highly persuasive response (2-3 sentences).
        
        Respond ONLY in JSON:
        {{
            "thought": "how I will persuade the buyer",
            "action": "{action}",
            "new_quote": {target_price},
            "message": "..."
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)

class ListingAgentDecider(BaseAgent):
    """The decision-maker — reads Risk Reader's profile and makes the call on exact price and action."""
    async def act(self, product: str, quote: float, floor: float, risk_profile: Dict[str, Any], current_hour: int, max_hours: int, buyer_offer: Optional[float] = None) -> Dict[str, Any]:
        progress = current_hour / max_hours
        
        system_prompt = f"""
        Role: Listing Agent (Senior Deal-Maker).
        Product: {product}
        Current Quote (Retail Base): ${quote:.2f}
        Absolute Floor Price: ${floor:.2f}
        Simulation Progress: {progress*100:.0f}%
        Buyer's Last Offer: ${buyer_offer if buyer_offer else 'None'}
        
        RISK READER'S BUYER PROFILE:
        - Profile: {risk_profile.get('buyer_profile', 'N/A')}
        - Tactic Detected: {risk_profile.get('tactic_detected', 'N/A')}
        - Bluffing Probability: {risk_profile.get('bluffing_probability', 'N/A')}/10
        - Walk-Away Probability: {risk_profile.get('walk_away_probability', 'N/A')}/10
        - Recommended Stance: {risk_profile.get('recommended_stance', 'N/A')}
        
        YOUR DECISION RULES:
        1. HARD FLOOR: NEVER offer below ${floor:.2f}. This is absolute.
        2. HARD CEILING: NEVER offer above ${min(quote * 1.15, quote + 5.0):.2f}. Do NOT inflate prices above the quote.
        3. BLUFF RESPONSE: If bluffing_probability >= 7 AND progress < 70%, HOLD FIRM — counter at exactly ${quote:.2f}. Don't concede.
        4. WALK-AWAY RESPONSE: If walk_away_probability >= 8 AND progress > 50%, make a SMALL concession — midpoint of (${quote:.2f} + buyer_offer) / 2, but never below ${floor:.2f}.
        5. LATE-GAME ACCEPTANCE: If progress > 70% AND buyer's last offer >= ${floor:.2f}, ACCEPT immediately. Spoilage = total loss.
        6. DEFAULT (applies in most cases): HOLD at the StrategicBrain's computed quote of ${quote:.2f}. This is YOUR target price — defend it. Do NOT drop toward the buyer's offer unless rules 4 or 5 explicitly apply. The buyer coming back means they are interested; stay at ${quote:.2f}.
        
        IMPORTANT: The current quote ${quote:.2f} is already set by the StrategicBrain based on market conditions. Your job is to DEFEND this price, not give it away.
        
        Output a specific dollar amount. Think step by step, then output strictly valid JSON:
        {{
          "decision_reasoning": "Brief step-by-step reasoning applying the rules above",
          "action": "ACCEPT|COUNTER|WALK_AWAY",
          "price": float
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": system_prompt}])

class TacticalOrchestrator(BaseAgent):
    """Replaces TacticalNegotiator. Coordinates RiskReader -> ListingAgentDecider -> Spokesperson."""
    def __init__(self, model_alias: str, risk_reader: RiskReader, spokesperson: Spokesperson):
        super().__init__(model_alias)
        self.risk_reader = risk_reader
        self.decider = ListingAgentDecider(model_alias)
        self.spokesperson = spokesperson
        
    async def act(self, buyer_id: int, product: str, quote: float, floor: float, strategy: str, current_hour: int, max_hours: int, history: List[Dict[str, str]], buyer_offer: Optional[float] = None) -> Dict[str, Any]:
        # 1. Profile the Buyer
        risk_profile = await self.risk_reader.act(history, current_hour)
        
        # 2. Decide the exact price
        decision = await self.decider.act(product, quote, floor, risk_profile, current_hour, max_hours, buyer_offer)
        
        target_price = decision.get("price", quote)
        action = decision.get("action", "COUNTER")
                
        # 3. Craft the Message
        return await self.spokesperson.act(target_price, action, risk_profile, history)

# --- SUPPORTING AGENTS ---

class IntegrityWatchdog(BaseAgent):
    """Combines Compliance + Risk Auditor."""
    async def audit(self, strategy: str, quotes: Dict[str, float], chaos_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"""
        Role: Integrity Watchdog (SOTA Risk Auditor).
        Strategy: {strategy} | Quotes: {json.dumps(quotes)}
        Chaos Events: {json.dumps(chaos_events)}
        
        TASK: Detect and mitigate adversarial threats.
        - Analyze 'Chaos Events' for Buyer Collusion or Market Manipulation.
        - If a 'DECEPTIVE_BIDDING' event is detected, advise the Brain to FREEZE discounts to protect margins.
        - Audit for pricing ethics (ensure quotes are not predatory).
        
        Respond ONLY in JSON: {{"status": "APPROVED|REJECTED", "risks": "...", "mitigation_advice": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class ChaosInjector(BaseAgent):
    """The Red-Teamer / Adversarial Agent."""
    async def act(self, state: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Role: Adversarial Market Manipulator.
        Current State: {json.dumps(state)}
        
        TASK: Inject a sophisticated market shock or deceptive signal.
        - DECEPTION: Simulate a 'Buyer Cartel' where buyers collectively lower their bids.
        - SHOCK: Simulate a 'Flash Crash' where a competitor dumps similar inventory.
        - ANOMALY: Inject a 'Spoofing' signal where budgets appear lower than they are.
        
        Respond ONLY in JSON: 
        {{
            "event": "DECEPTIVE_BIDDING | MARKET_CRASH | SUPPLY_SURGE",
            "impact_magnitude": 1-10,
            "message": "..."
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class PostMortemCritic(BaseAgent):
    async def review(self, data: Any) -> Dict[str, Any]:
        prompt = f"""
        Role: Senior Research Analyst.
        Task: Perform a Research-Grade SWOT Analysis on the following MAS session.
        Session Data: {json.dumps(data)}
        
        Analyze:
        1. Strategic Cohesion: Did the Brain and Negotiator act as one?
        2. Market Resilience: How did the Hive handle chaos/red-teaming?
        3. Economic Efficiency: Items sold vs total inventory.
        
        Respond ONLY in JSON:
        {{
            "thought": "...",
            "executive_summary": "...",
            "swot_analysis": {{
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "threats": []
            }},
            "final_grade": "A|B|C|D|F",
            "research_notes": "..."
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])
