"""
Linear Price Decay Baseline — the standard Operations Research heuristic
for perishable goods yield management.

Used as the NeurIPS/ICML-required math baseline. Our MAS must beat this
to justify using LLMs at all.

Reference: Gallego & van Ryzin (1994), "A stochastic model of the high-to-low
pricing problem for perishable goods." Operations Research.

Strategy:
- Start at retail_price × 1.20 (20% premium)
- Decay linearly to cost_price × 1.05 (5% above cost) by end of simulation
- Accept any offer >= current_price at that hour
"""
from typing import Dict, Any


class LinearDecayBaseline:
    """
    Pure math baseline. No LLMs. No architecture.
    Implements classic exponential price decay for perishable goods.
    """

    def get_quote(self, item: Dict[str, Any], current_hour: int, max_hours: int) -> float:
        """Compute the current ask price for an item at this hour."""
        t          = current_hour / max_hours          # 0.0 → 1.0
        start_price = item["selling_price"] * 1.20     # 20% premium at hour 0
        end_price   = item["cost_price"]   * 1.05      # 5% above cost at hour max
        price       = start_price + (end_price - start_price) * t
        return round(max(end_price, price), 2)

    def get_floor(self, item: Dict[str, Any]) -> float:
        """Minimum acceptable price — always cost + 5%."""
        return round(item["cost_price"] * 1.05, 2)

    def respond_to_offer(
        self,
        item: Dict[str, Any],
        buyer_offer: float,
        current_hour: int,
        max_hours: int,
    ) -> Dict[str, Any]:
        """
        Pure math response to a buyer counter-offer.
        No negotiation text — just accept/counter with the decay price.
        """
        current_price = self.get_quote(item, current_hour, max_hours)
        floor         = self.get_floor(item)

        if buyer_offer >= current_price:
            return {"action": "ACCEPT", "new_quote": buyer_offer, "message": "Deal."}
        elif buyer_offer >= floor:
            # Late game: accept anything above floor
            if current_hour / max_hours > 0.70:
                return {"action": "ACCEPT", "new_quote": buyer_offer, "message": "Accepted."}
        # Counter at current decay price
        return {
            "action":    "COUNTER",
            "new_quote": current_price,
            "message":   f"Our price is ${current_price:.2f}.",
        }


# Singleton
linear_decay_baseline = LinearDecayBaseline()
