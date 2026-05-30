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

    async def act(self, history: List[Dict[str, str]], current_quote: float, days_until_expiry: int, current_hour: int, max_hours: int) -> Dict[str, Any]:
        desperation = current_hour / max_hours
        remaining_items = [i for i in self.shopping_list if i not in self.purchased_items]
        
        personality_prompts = {
            "ESSENTIAL": "You NEED these items urgently. You are less price-sensitive and more likely to accept higher quotes to secure the goods.",
            "CALCULATED": "You are a rational deal-seeker. You want the best price and will walk away if the deal isn't 'fair' relative to market value.",
            "IMPULSE": "You are emotional and unpredictable. You might overpay if you like the 'message' or walk away on a whim."
        }

        prompt = f"""
        Role: Expert Buyer. Personality: {self.personality}.
        Shopping List: {json.dumps(remaining_items)} | Total Budget: ${self.budget:.2f}
        Current Target: {remaining_items[0] if remaining_items else 'None'}
        Expiry: {days_until_expiry} days | Simulation Progress: {desperation*100:.0f}%
        Current Market Quote: ${current_quote:.2f}

        CONTEXT: 
        - {personality_prompts.get(self.personality)}
        - Your 'Desperation Factor' is {desperation:.2f}. As it nears 1.0, you become much more willing to pay premiums to avoid leaving empty-handed.
        
        TASK: Negotiate for the current target.
        Respond ONLY in JSON: {{"action": "ACCEPT|WAIT|WALK_AWAY|COUNTER", "counter_offer": float, "message": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)

class HumanSalesManager(BaseAgent):
    """Simulates a human sales manager for baseline comparison."""
    async def act(self, product: str, cost_price: float, current_quote: float, days_until_expiry: int, buyer_history: List[Dict[str, Any]], chaos_events: List[Dict[str, Any]], current_hour: int, max_hours: int) -> Dict[str, Any]:
        progress = current_hour / max_hours
        prompt = f"""
        Role: Human Sales Manager (Baseline).
        Item: {product} | Cost Price (CP): ${cost_price:.2f} | Current Quote: ${current_quote:.2f}
        Days Until Expiry: {days_until_expiry} | Progress: {progress*100:.0f}%
        Market Chaos: {json.dumps(chaos_events[-1] if chaos_events else "NONE")}

        TASK: You are a pragmatic manager.
        - If Progress > 80%, you get nervous about unsold stock and will accept almost ANY offer above Cost Price.
        - You want to avoid 'Waste Loss' at all costs.
        
        Respond ONLY in JSON: {{"new_quote": float, "message": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

# --- THE 6 POWER AGENTS ---

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
        
        # REFINED TIME-DECAY STRATEGY
        if progress < 0.4:
            phase = "PREMIUM_SCALPING"
            desc = "Maximize margins on all items. Quote +20% over selling_price."
        elif progress < 0.7:
            phase = "MARKET_BALANCE"
            desc = "Align with standard selling_price. Floor = Cost + 15%."
        else:
            phase = "SMART_LIQUIDATION"
            desc = "Prioritize volume but avoid selling below Cost + 5% unless absolutely necessary."

        prompt = f"""
        Role: Strategic Brain. Phase: {phase} | Progress: {progress*100:.0f}%
        Intelligence: {json.dumps(intel)}
        Inventory: {json.dumps(inventory)}
        
        TASK: {desc}
        - Do not panic. The human manager often sells too cheap; stay more rational.
        - Set floors carefully. Even in LIQUIDATION, try to keep floors at Cost + $0.50.
        
        Respond ONLY in JSON:
        {{
            "quotes": {{ "item_name": float }},
            "floor_prices": {{ "item_name": float }},
            "strategy_directive": "{phase}",
            "priority_items": []
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])


class TacticalNegotiator(BaseAgent):
    async def act(self, buyer_id: int, product: str, quote: float, floor: float, strategy: str, current_hour: int, max_hours: int, history: List[Dict[str, str]], buyer_offer: Optional[float] = None) -> Dict[str, Any]:
        progress = current_hour / max_hours
        prompt = f"""
        Role: Tactical Negotiator (The Closer). Progress: {progress*100:.0f}%
        Target: B{buyer_id} | Item: {product} | My Quote: ${quote:.2f} | Floor (CP+): ${floor:.2f}
        Strategy Directive: {strategy}
        Buyer's Bid: ${buyer_offer if buyer_offer else 'None'}

        TASK:
        1. ANALYZE HISTORY: Look at the provided negotiation history. 
           - Is the buyer persistent? 
           - Do they counter-offer quickly or walk away? 
           - Infer if they are 'ESSENTIAL' (high urgency), 'CALCULATED' (rational/slow), or 'IMPULSE' (emotional).
        2. PRICE DISCRIMINATION: If you detect high urgency (e.g., they counter multiple times or their messages sound desperate), hold your price firmer to maximize profit.
        3. CLOSE THE DEAL: If progress > 80% and the buyer is rational, you can drop closer to the floor.
        
        Respond ONLY in JSON: {{"action": "ACCEPT|COUNTER", "new_quote": float, "message": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)

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
