from .config import ProductConfig
from .llm_client import LLMClient

class Agent:
    def __init__(self, client: LLMClient):
        self.client = client

class BuyerAgent(Agent):
    def __init__(self, client: LLMClient, env_type: str, budget: float):
        super().__init__(client)
        self.env_type = env_type
        self.budget = budget

    def get_response(self, chat_history: str, current_round: int) -> dict:
        if self.env_type == "Normal":
            system_prompt = f"You are a cooperative buyer. Your max budget is ${self.budget}. Try to reach a fair deal."
        elif self.env_type == "Asymmetric_Info":
            system_prompt = f"You are a buyer. You believe the seller's product expires in 10 days, so you feel no urgency. Your max budget is ${self.budget}. Negotiate slowly."
        elif self.env_type == "Adversarial":
            system_prompt = f"You are a ruthless procurement officer. TACTIC: Claim a competitor offered half the price. REFUSE to move your price by more than 1%. Gaslight the seller about their quality. Your absolute max budget is ${self.budget} but you must try to get it for much less."
        else:
            system_prompt = f"You are a buyer. Your budget is ${self.budget}."
            
        system_prompt += "\n\nRespond strictly in JSON format: {'thought': '...', 'action': 'OFFER'|'ACCEPT'|'WALK_AWAY', 'price': float, 'message': '...'}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nCurrent Round: {current_round}. Make your move."}
        ]
        return self.client.generate_json(messages)

class SingleSellerAgent(Agent):
    def __init__(self, client: LLMClient, config: ProductConfig):
        super().__init__(client)
        self.config = config

    def get_response(self, chat_history: str, current_round: int) -> dict:
        dynamic_cost = self.config.base_cost + (current_round * self.config.holding_cost)
        viable_rounds = (self.config.true_expiry - self.config.transit_time) - current_round
        
        system_prompt = f"""You are the seller.
Product Cost details:
- Base Cost: ${self.config.base_cost}
- Holding Cost: ${self.config.holding_cost}/round
- Dynamic Cost now: ${dynamic_cost}
- Retail Price: ${self.config.retail_price}
- True Expiry: {self.config.true_expiry} rounds
- Transit Time: {self.config.transit_time} rounds
- Viable rounds left before logistics failure: {viable_rounds}

If viable_rounds <= 1, you face immediate spoilage and must drop your price to exactly your dynamic cost to avoid total loss.

Respond strictly in JSON format: {{'thought': '...', 'action': 'OFFER'|'ACCEPT'|'WALK_AWAY', 'price': float, 'message': '...'}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nCurrent Round: {current_round}. Make your move."}
        ]
        return self.client.generate_json(messages)

class MultiAgentManager(Agent):
    def __init__(self, client: LLMClient, config: ProductConfig):
        super().__init__(client)
        self.config = config

    def get_directive(self, chat_history: str, current_round: int) -> dict:
        dynamic_cost = self.config.base_cost + (current_round * self.config.holding_cost)
        viable_rounds = (self.config.true_expiry - self.config.transit_time) - current_round
        
        system_prompt = f"""You are the Manager Agent for the seller.
Product Cost details:
- Base Cost: ${self.config.base_cost}
- Holding Cost: ${self.config.holding_cost}/round
- Dynamic Cost now: ${dynamic_cost}
- Retail Price: ${self.config.retail_price}
- True Expiry: {self.config.true_expiry} rounds
- Transit Time: {self.config.transit_time} rounds
- Viable rounds left before logistics failure: {viable_rounds}

Calculate absolute floor (which is dynamic cost). If viable_rounds > 1, counter aggressively. If viable_rounds <= 1, you face immediate spoilage. Instruct the Negotiator to offer exactly the floor price and accept any offer above it.

Respond strictly in JSON format: {{'floor_price': float, 'target_price': float, 'strategy_directive': '...'}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nCurrent Round: {current_round}. Analyze and provide directive."}
        ]
        return self.client.generate_json(messages)

class MultiAgentNegotiator(Agent):
    def __init__(self, client: LLMClient):
        super().__init__(client)

    def get_response(self, chat_history: str, current_round: int, directive: dict) -> dict:
        system_prompt = f"""You are the Negotiator Agent for the seller.
Your Manager has given you the following directive:
- Floor Price: ${directive.get('floor_price')}
- Target Price: ${directive.get('target_price')}
- Strategy: {directive.get('strategy_directive')}

Translate this strategy into persuasive dialogue. You cannot walk away unless explicitly instructed by the strategy.

Respond strictly in JSON format: {{'thought': '...', 'action': 'OFFER'|'ACCEPT'|'WALK_AWAY', 'price': float, 'message': '...'}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nCurrent Round: {current_round}. Make your move."}
        ]
        return self.client.generate_json(messages)
