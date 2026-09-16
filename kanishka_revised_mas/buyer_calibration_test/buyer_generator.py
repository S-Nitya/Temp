"""
Calibration-Only Buyer Generator.
Creates an economically heterogeneous buyer population to test price resistance and perishability constraints.
STRICTLY ISOLATED from the production benchmark.
"""
import random
from typing import Dict, Any, List
from pydantic import BaseModel


class CalibratedBuyerPrivateState(BaseModel):
    buyer_id: str
    target_item_id: str
    product_name: str
    retail_reference: float
    cost_price: float
    expiry_hours: float
    expiry_regime: str
    budget_ceiling: float
    private_valuation: float
    valuation_ratio: float  # private_valuation / retail_reference
    budget_ratio: float     # budget_ceiling / retail_reference
    urgency: str            # "HIGH", "MODERATE", "LOW"
    price_sensitivity: str  # "HIGH", "MODERATE", "LOW"
    persona: str            # "BARGAIN_HUNTER", "PRAGMATIC_SHOPPER", "QUALITY_SEEKER", "CAUTIOUS_CONSERVATIVE"


def generate_calibrated_buyer_states(catalog: List[Dict[str, Any]], seed: int = 999) -> Dict[str, CalibratedBuyerPrivateState]:
    """
    Generate an economically heterogeneous calibration buyer population across 15 catalog items.
    Spans:
      - Below-retail valuations (0.65 - 0.85x retail) -> Price-resistant / bargain seekers
      - Near-retail valuations (0.86 - 1.05x retail)  -> Pragmatic / fair-market shoppers
      - Above-retail valuations (1.06 - 1.25x retail) -> Inelastic / quality seekers
    """
    rng = random.Random(seed)

    urgencies = ["HIGH", "MODERATE", "LOW"]
    sensitivities = ["HIGH", "MODERATE", "LOW"]
    personas = ["BARGAIN_HUNTER", "PRAGMATIC_SHOPPER", "QUALITY_SEEKER", "CAUTIOUS_CONSERVATIVE"]

    buyer_states = {}
    for idx, item in enumerate(catalog):
        item_id = item["item_id"]
        retail = float(item["retail_reference"])
        cost = float(item["cost_price"])
        expiry_hours = float(item["starting_remaining_hours"])
        regime = item.get("expiry_regime", "Medium")

        # Cycle valuation profiles across items to guarantee coverage across all 3 expiry regimes
        # Profile 0: Below retail (0.68 - 0.85)
        # Profile 1: Near retail (0.88 - 1.05)
        # Profile 2: Above retail (1.08 - 1.25)
        profile = idx % 3
        if profile == 0:
            val_mult = rng.uniform(0.68, 0.85)
            budget_mult = rng.uniform(0.70, 0.90)
            chosen_persona = rng.choice(["BARGAIN_HUNTER", "CAUTIOUS_CONSERVATIVE"])
            chosen_sens = "HIGH"
        elif profile == 1:
            val_mult = rng.uniform(0.88, 1.05)
            budget_mult = rng.uniform(0.90, 1.10)
            chosen_persona = "PRAGMATIC_SHOPPER"
            chosen_sens = rng.choice(["MODERATE", "HIGH"])
        else:
            val_mult = rng.uniform(1.08, 1.25)
            budget_mult = rng.uniform(1.10, 1.30)
            chosen_persona = rng.choice(["QUALITY_SEEKER", "PRAGMATIC_SHOPPER"])
            chosen_sens = rng.choice(["LOW", "MODERATE"])

        private_val = round(retail * val_mult, 2)
        budget = round(retail * budget_mult, 2)
        # Economic coherence: budget is at least 90% of valuation
        budget = max(budget, round(private_val * 0.90, 2))

        chosen_urgency = rng.choice(urgencies)

        buyer_states[item_id] = CalibratedBuyerPrivateState(
            buyer_id=f"CALIB_B_{seed}_{item_id}",
            target_item_id=item_id,
            product_name=item["product_name"],
            retail_reference=retail,
            cost_price=cost,
            expiry_hours=expiry_hours,
            expiry_regime=regime,
            budget_ceiling=budget,
            private_valuation=private_val,
            valuation_ratio=round(private_val / retail, 4),
            budget_ratio=round(budget / retail, 4),
            urgency=chosen_urgency,
            price_sensitivity=chosen_sens,
            persona=chosen_persona,
        )

    return buyer_states
