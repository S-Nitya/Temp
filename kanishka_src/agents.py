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
        import re
        viable_rounds = (self.config.true_expiry - self.config.transit_time) - current_round
        
        last_buyer_offer = "None"
        matches = re.findall(r"\[Round \d+\] Buyer: \$([\d\.]+)", chat_history)
        if matches:
            last_buyer_offer = matches[-1]
            
        system_prompt = f"""You are the internal Pricing Strategist for a perishable goods seller. DO NOT talk to the buyer directly.
Product: Generic Perishable Goods. Base Cost: ${self.config.base_cost}. Retail Price: ${self.config.retail_price}.
Holding Cost Incurred Per Round: ${self.config.holding_cost}. 
Current Round: {current_round} out of 10.
URGENT LOGISTICS: You have exactly {viable_rounds} rounds left to strike a deal before shipping fails.

Buyer's last offer: ${last_buyer_offer}.

STRATEGY RULES:
1. DETERMINE YOUR FLOOR: You know your base cost, and you know you incur a holding cost for every round that passes. You must deduce your own absolute break-even price for today. NEVER set a target below your break-even point.
2. ADVERSARIAL DETECTION: Analyze the buyer's last offer. If they are aggressively lowballing (e.g., anchoring near $40 while retail is $80) or claiming a competitor offered a lower price, they are using adversarial tactics. DO NOT counter aggressively near the retail price, as this causes gridlock.
3. SMART CONCESSION: If the buyer is adversarial, calculate a "Compromise Target" that is slightly above their last offer (but still safely above your deduced floor price). Instruct the Negotiator to offer this Compromise Target to trap them into a deal, providing sales tactics to justify the premium.
4. COOPERATIVE CONCESSION: If the buyer is normal and making fair concessions, meet them halfway.
5. PANIC MODE: If viable_rounds <= 1, you face immediate spoilage. Instruct the Negotiator to offer exactly your deduced floor price and accept ANY offer above it.

Output strictly valid JSON:
{{"thought": "Deduce the break-even floor price here, then plan the strategy.", "floor_price": float, "target_price": float, "strategy_directive": "string"}}
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

class StatisticianAgent(Agent):
    def __init__(self, client: LLMClient, config: ProductConfig):
        super().__init__(client)
        self.config = config

    def get_analysis(self, chat_history: str, current_round: int) -> dict:
        viable_rounds = (self.config.true_expiry - self.config.transit_time) - current_round
        
        system_prompt = f"""You are the quantitative Statistician for a perishable goods seller.
Product: Generic Perishable Goods. Base Cost: ${self.config.base_cost}. Retail Price: ${self.config.retail_price}.
Holding Cost Per Round: ${self.config.holding_cost}. Current Round: {current_round}/10.
URGENT LOGISTICS: You have exactly {viable_rounds} rounds left to strike a deal before shipping fails (spoilage).

Your ONLY job is to calculate the cold, hard facts.
1. Calculate the dynamic floor price: Base Cost + (Current Round * Holding Cost).
2. Assess the time risk.

Output strictly valid JSON:
{{"dynamic_floor_price": float, "viable_rounds_left": int, "risk_assessment": "string detailing the objective math risk"}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nCurrent Round: {current_round}. Perform calculation."}
        ]
        return self.client.generate_json(messages)

class TraderAgent(Agent):
    def __init__(self, client: LLMClient):
        super().__init__(client)

    def get_strategy(self, chat_history: str, current_round: int, statistician_json: dict) -> dict:
        import re
        last_buyer_price = "None"
        matches = re.findall(r"\[Round \d+\] Buyer: \$([\d\.]+)", chat_history)
        if matches:
            last_buyer_price = matches[-1]
            
        system_prompt = f"""You are the ruthless Lead Trader. 
You must read the Statistician's Data: {statistician_json}
You must read the Buyer's last offer: ${last_buyer_price}.

YOUR GOAL: Maximize profit (Efficiency).
1. ADVERSARIAL DETECTION: Read the chat history. Is the buyer bluffing, lying about competitors, or artificially anchoring low? 
2. RISK STRATEGY: Do NOT panic just because viable rounds are ticking down. Call the buyer's bluffs. Hold your price high unless `viable_rounds_left` is exactly 0 or 1.
3. Determine the exact `target_price` the Salesman must offer this round.

Output strictly valid JSON:
{{"buyer_is_bluffing": boolean, "target_price": float, "trading_strategy": "string giving ruthless, profit-maximizing instructions to the Salesman"}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nCurrent Round: {current_round}. Determine strategy."}
        ]
        return self.client.generate_json(messages)

class SalesmanAgent(Agent):
    def __init__(self, client: LLMClient):
        super().__init__(client)

    def get_response(self, chat_history: str, current_round: int, trader_json: dict) -> dict:
        system_prompt = f"""You are the charismatic Salesman. 
Your Lead Trader has given you this strict directive: {trader_json}

YOUR MISSION:
1. You MUST offer exactly the `target_price` commanded by the Trader. If the Trader says to ACCEPT, do so.
2. Draft the message to the buyer. Use advanced sales psychology. If the Trader noted the buyer is bluffing, smoothly deflect their complaints. Emphasize product superiority, scarcity, or partnership to justify the Trader's price.

Output strictly valid JSON:
{{"thought": "how I will persuade the buyer", "action": "OFFER"|"ACCEPT"|"WALK_AWAY", "price": float, "message": "your persuasive reply to the buyer"}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nCurrent Round: {current_round}. Make your move."}
        ]
        return self.client.generate_json(messages)


# =====================================================================
# ARCHITECTURE 04 — "Listing Agent" (Qualitative, No-Formula Negotiation)
# =====================================================================

class StateTrackerAgent(Agent):
    """Compresses raw chat history into a structured deal memo to prevent context bloat."""
    def __init__(self, client: LLMClient):
        super().__init__(client)

    def get_memo(self, chat_history: str, current_round: int) -> dict:
        system_prompt = """You are a deal tracker. Your job is to read the full negotiation transcript and compress it into a concise, structured deal memo that other agents can quickly read.

Output strictly valid JSON:
{"deal_memo": "A 2-3 sentence summary of where the negotiation stands right now",
 "rounds_elapsed": int,
 "seller_last_offer": float or null,
 "buyer_last_offer": float or null,
 "trend": "one of: converging, diverging, stalled, just_started"}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Full negotiation transcript:\n{chat_history}\n\nCurrent Round: {current_round}. Summarize the deal state."}
        ]
        return self.client.generate_json(messages)


class AppraiserAgent(Agent):
    """Qualitative appraiser — reasons like a seasoned broker doing a CMA. No formula injected."""
    def __init__(self, client: LLMClient, config: ProductConfig, env_type: str):
        super().__init__(client)
        self.config = config
        self.env_type = env_type

    def get_appraisal(self, deal_memo: dict, current_round: int, max_rounds: int) -> dict:
        # Product context given as NARRATIVE, not formula inputs
        product_narrative = f"""You are appraising a lot of premium perishable goods.
Here is what you know about this asset:
- It cost the seller approximately ${self.config.base_cost} to acquire.
- The retail asking price in this market is around ${self.config.retail_price}.
- The product has a true shelf life of about {self.config.true_expiry} days from acquisition.
- It takes roughly {self.config.transit_time} days to ship after a deal is struck.
- Every day the product sits unsold, the seller loses roughly ${self.config.holding_cost} in storage, quality degradation, and opportunity cost.
- We are currently on round {current_round} of {max_rounds} possible negotiation rounds."""

        # Scenario-specific context
        if self.env_type == "Asymmetric_Info":
            scenario_context = """PRIVATE INFORMATION (the buyer does NOT know this): The product actually has only about 72 hours (roughly 3 rounds) of viable shelf life remaining when you account for transit. The buyer believes it lasts 10 days. Factor this private knowledge — the real urgency — into your appraisal, but remember the buyer doesn't share this urgency."""
        elif self.env_type == "Adversarial":
            scenario_context = """MARKET WARNING: Buyers in this market are known to be aggressive. They frequently lie about competitor prices, anchor artificially low, and try to gaslight sellers about product quality. Your appraisal should factor in that the buyer's stated alternatives are likely fabricated. Do not let adversarial tactics erode your sense of the asset's true worth."""
        else:
            scenario_context = """MARKET CONDITIONS: This is a normal, transparent market. Both parties are reasonably informed. The buyer is expected to negotiate in good faith."""

        system_prompt = f"""You are a seasoned perishable goods broker — think of yourself like a Tsukiji fish market veteran or a real estate agent doing a Comparable Market Analysis (CMA).

{product_narrative}

{scenario_context}

Deal state so far: {deal_memo}

YOUR TASK: Appraise this asset. What would you actually accept for it today, given everything you know?

CRITICAL INSTRUCTION: Do NOT use a formula. Do NOT calculate "base cost + rounds × holding cost." Instead, reason qualitatively — mention spoilage pressure, comparable sales, quality premium, time urgency, buyer leverage — and let a number emerge naturally from your thinking. Think out loud like a broker advising a client.

Output strictly valid JSON:
{{"appraisal_reasoning": "Your detailed qualitative reasoning (3-5 sentences, think out loud)",
  "appraised_floor": float (the absolute minimum you'd accept today),
  "appraised_fair_value": float (what you think a fair deal would look like),
  "urgency_level": "one of: low, moderate, high, critical"}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Round {current_round} of {max_rounds}. What is your appraisal?"}
        ]
        return self.client.generate_json(messages)


class RiskReaderAgent(Agent):
    """Behavioral analyst — reads the buyer's messages and outputs a psychological profile."""
    def __init__(self, client: LLMClient, env_type: str):
        super().__init__(client)
        self.env_type = env_type

    def get_profile(self, chat_history: str, deal_memo: dict, current_round: int) -> dict:
        if self.env_type == "Asymmetric_Info":
            scenario_hint = """NOTE: The buyer is negotiating as if there is no urgency — they believe the product has a long shelf life. They don't know the seller is under real time pressure. Assess whether the buyer's slow pace is strategic or genuine lack of urgency."""
        elif self.env_type == "Adversarial":
            scenario_hint = """NOTE: The buyer is expected to employ aggressive tactics — bluffing, citing fake competitor prices, anchoring artificially low, and questioning product quality. Your job is to see through the posturing and assess their TRUE intent and walk-away probability."""
        else:
            scenario_hint = """NOTE: This is a normal negotiation environment. The buyer is expected to negotiate in good faith, but still look for standard tactics like anchoring or probing."""

        system_prompt = f"""You are a behavioral negotiation analyst — an expert at reading people in high-stakes deals.

{scenario_hint}

Deal state: {deal_memo}

Read the buyer's messages in the negotiation transcript below and produce a psychological profile.

Assess:
1. What tactic is the buyer using? (anchoring, probing, bluffing, cooperative, aggressive, passive)
2. Are they bluffing or serious? (rate 0-10, where 10 = definitely bluffing)
3. How close are they to walking away? (rate 0-10, where 10 = about to walk)
4. What should the seller's stance be given this buyer's psychology?

Output strictly valid JSON:
{{"buyer_profile": "2-3 sentence psychological assessment",
  "tactic_detected": "primary tactic name",
  "bluffing_probability": int 0-10,
  "walk_away_probability": int 0-10,
  "recommended_stance": "brief recommendation for the decision-maker"}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Negotiation transcript:\n{chat_history}\n\nCurrent Round: {current_round}. Profile the buyer."}
        ]
        return self.client.generate_json(messages)


class ListingAgentDecider(Agent):
    """The decision-maker — reads Appraiser's memo + Risk Reader's profile and makes the call."""
    def __init__(self, client: LLMClient):
        super().__init__(client)

    def get_decision(self, appraisal: dict, risk_profile: dict, deal_memo: dict, current_round: int, max_rounds: int) -> dict:
        system_prompt = f"""You are the Listing Agent — the senior decision-maker in this negotiation. You operate like a top real estate agent: anchor high, yield slowly, and never make the first big concession.

You have two expert reports to read:

APPRAISER'S VALUATION:
- Reasoning: {appraisal.get('appraisal_reasoning', 'N/A')}
- Appraised Floor (minimum acceptable): ${appraisal.get('appraised_floor', 'N/A')}
- Appraised Fair Value: ${appraisal.get('appraised_fair_value', 'N/A')}
- Urgency Level: {appraisal.get('urgency_level', 'N/A')}

RISK READER'S BUYER PROFILE:
- Profile: {risk_profile.get('buyer_profile', 'N/A')}
- Tactic Detected: {risk_profile.get('tactic_detected', 'N/A')}
- Bluffing Probability: {risk_profile.get('bluffing_probability', 'N/A')}/10
- Walk-Away Probability: {risk_profile.get('walk_away_probability', 'N/A')}/10
- Recommended Stance: {risk_profile.get('recommended_stance', 'N/A')}

DEAL STATE: {deal_memo}
Round: {current_round} of {max_rounds}.

YOUR DECISION RULES:
1. NEVER offer below the Appraiser's floor — that is your absolute minimum.
2. If the buyer's walk-away probability is high (>= 7), consider a modest concession toward fair value to save the deal.
3. If the buyer is bluffing (bluffing probability >= 7), hold firm or counter-anchor higher.
4. If urgency is "critical", you may offer at or near the floor to close the deal immediately.
5. If the buyer's last offer is above your appraised fair value, ACCEPT immediately.
6. Otherwise, anchor high and yield slowly. Small concessions signal strength.

Make a specific decision with a specific dollar amount and clear reasoning.

Output strictly valid JSON:
{{"decision_reasoning": "Your strategic reasoning for this specific move",
  "action": "OFFER or ACCEPT or WALK_AWAY",
  "price": float,
  "stance": "one of: hold_firm, counter_anchor, modest_concession, close_deal, walk_away"}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Round {current_round}. Make your decision."}
        ]
        return self.client.generate_json(messages)


class SpokespersonAgent(Agent):
    """Translates the Listing Agent's decision into natural negotiation language matching the buyer's energy."""
    def __init__(self, client: LLMClient):
        super().__init__(client)

    def get_response(self, chat_history: str, decision: dict, risk_profile: dict, current_round: int) -> dict:
        system_prompt = f"""You are the Spokesperson — the public face of the seller in this negotiation. Your job is to translate the Listing Agent's internal decision into natural, persuasive negotiation language.

THE DECISION (from your Listing Agent):
- Action: {decision.get('action', 'OFFER')}
- Price: ${decision.get('price', 0)}
- Stance: {decision.get('stance', 'N/A')}
- Reasoning: {decision.get('decision_reasoning', 'N/A')}

BUYER PSYCHOLOGY (from your Risk Reader):
- Profile: {risk_profile.get('buyer_profile', 'N/A')}
- Tactic: {risk_profile.get('tactic_detected', 'N/A')}

YOUR RULES:
1. You MUST use exactly the price and action decided by the Listing Agent. You do NOT change the numbers.
2. Match the buyer's energy: if they're formal, be professional. If they're aggressive, be calm but firm. If they're friendly, be warm.
3. If the buyer is bluffing about competitors, acknowledge their concern without conceding — redirect to your product's value.
4. Never reveal internal strategy, floor prices, or urgency to the buyer.
5. Be concise — 2-3 sentences max in your message.

Output strictly valid JSON:
{{"thought": "Your internal reasoning about how to frame this message",
  "action": "{decision.get('action', 'OFFER')}",
  "price": {decision.get('price', 0)},
  "message": "Your natural, persuasive message to the buyer"}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chat History:\n{chat_history}\n\nRound {current_round}. Deliver the message."}
        ]
        return self.client.generate_json(messages)
