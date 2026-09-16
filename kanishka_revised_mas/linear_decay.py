"""
Deterministic LinearDecay Benchmark Pricing Policy over Time Ticks.
Does not use an LLM for pricing decisions; computes linear markdown deterministically.
"""
from typing import Dict, Any, List


class LinearDecayPolicy:
    """
    Deterministic LinearDecay seller policy.
    Decays price linearly from retail_reference towards cost_price over time/exchange ticks.
    """
    def __init__(self, item: Dict[str, Any], max_exchanges: int = 3):
        self.item = item
        self.cost = float(item["cost_price"])
        self.retail = float(item["retail_reference"])
        self.starting_hours = int(item["starting_remaining_hours"])
        self.max_exchanges = max_exchanges
        self.opening_quote = self.retail
        self.seller_floor = self.cost

    def get_quote_for_exchange(self, exchange_idx: int) -> float:
        """
        Calculate deterministic markdown price for exchange turn (0-indexed).
        Exchange 0: Retail Reference (100%)
        Exchange 1: Markdown step 1
        Exchange 2: Markdown step 2
        Floor is strictly bounded by cost.
        """
        if self.max_exchanges <= 1:
            fraction = 0.0
        else:
            fraction = exchange_idx / float(self.max_exchanges)

        # Decay from retail towards cost based on exchange progress
        decayed_price = self.retail - fraction * (self.retail - self.cost)
        return round(max(self.cost, decayed_price), 2)

    def evaluate_offer(self, buyer_offer: float, exchange_idx: int) -> Dict[str, Any]:
        """
        Deterministic decision rule:
        - If buyer_offer >= current decayed quote -> ACCEPT
        - If buyer_offer < current decayed quote -> COUNTER with current decayed quote
        """
        current_quote = self.get_quote_for_exchange(exchange_idx)

        if buyer_offer >= current_quote and buyer_offer >= self.cost:
            return {
                "action": "ACCEPT",
                "target_price": round(buyer_offer, 2),
                "spokesperson_message": f"We accept your offer of ${buyer_offer:.2f}.",
                "rationale": f"Deterministic: buyer offer ${buyer_offer:.2f} meets or exceeds markdown quote ${current_quote:.2f}.",
            }
        else:
            return {
                "action": "CONCEDE" if current_quote < self.retail else "HOLD",
                "target_price": current_quote,
                "spokesperson_message": f"Our current markdown price is ${current_quote:.2f}.",
                "rationale": f"Deterministic: countering at calculated linear markdown price ${current_quote:.2f}.",
            }
