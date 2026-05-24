import re
import json
from typing import Dict, List, Any, Optional
from .llm_client import client
from .config import MODELS

class BaseAgent:
    def __init__(self, model_alias: str):
        self.model_alias = model_alias

class Buyer(BaseAgent):
    def __init__(self, buyer_id: int, model_alias: str, budget: float, target_product: str):
        super().__init__(model_alias)
        self.buyer_id = buyer_id
        self.budget = budget
        self.target_product = target_product

    async def act(self, history: List[Dict[str, str]], current_quote: float) -> Dict[str, Any]:
        prompt = f"""
        Role: Expert Buyer. Product: {self.target_product} | Budget: ${self.budget:.2f}
        Current Market Price: ${current_quote:.2f}
        TASK: ACCEPT or WAIT. No counters.
        Respond ONLY in JSON: {{"action": "ACCEPT|WAIT|WALK_AWAY", "message": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}] + history)

# --- THE 6 POWER AGENTS ---

class IntelligenceHub(BaseAgent):
    """Combines IoT Sentinel + Market Scout + Sentiment."""
    async def act(self, inventory: List[Dict[str, Any]], buyers_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"""
        Role: Intelligence Hub. 
        Inventory: {json.dumps(inventory)}
        Buyers: {json.dumps(buyers_data)}
        TASK: Analyze telemetry, market demand, and buyer sentiments.
        Respond ONLY in JSON: 
        {{
            "critical_risk_item": "...",
            "market_demand_map": {{}},
            "buyer_sentiments": {{}},
            "overall_market_status": "STABLE|VOLATILE"
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class StrategicBrain(BaseAgent):
    """Combines Yield Analyst + Chief Orchestrator."""
    async def act(self, intel: Dict[str, Any], inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"""
        Role: Strategic Brain.
        Intelligence: {json.dumps(intel)}
        Inventory: {json.dumps(inventory)}
        TASK: Set UNIFIED market quotes for all items and define global sales strategy.
        Respond ONLY in JSON:
        {{
            "quotes": {{ "item_name": float }},
            "strategy_directive": "...",
            "priority_items": []
        }}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class TacticalNegotiator(BaseAgent):
    async def act(self, buyer_id: int, product: str, quote: float, strategy: str) -> Dict[str, Any]:
        prompt = f"""
        Role: Tactical Sales Desk.
        Target: B{buyer_id} | Item: {product} | Price: ${quote:.2f}
        Directive: {strategy}
        TASK: Pitch the price consistently.
        Respond ONLY in JSON: {{"message": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class IntegrityWatchdog(BaseAgent):
    """Combines Compliance + Risk Auditor."""
    async def audit(self, strategy: str, quotes: Dict[str, float]) -> Dict[str, Any]:
        prompt = f"""
        Role: Integrity Watchdog.
        Strategy: {strategy} | Quotes: {json.dumps(quotes)}
        TASK: Audit for pricing ethics and detect buyer deception/leakage.
        Respond ONLY in JSON: {{"status": "APPROVED|REJECTED", "risks": "..."}}
        """
        return await client.call(self.model_alias, [{"role": "system", "content": prompt}])

class ChaosInjector(BaseAgent):
    """The Red-Teamer."""
    async def act(self, state: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Role: Chaos Injector.
        State: {json.dumps(state)}
        TASK: Inject a real-time market shock.
        Respond ONLY in JSON: {{"event": "...", "severity": 1-10}}
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
