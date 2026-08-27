import asyncio
import json
from final_architecture.llm_client import client, validate_output, DeciderAction
from final_architecture.config import FINAL_CONFIG, SELLER_TEMPERATURE

model_70b = FINAL_CONFIG.get("strategic_brain", "Llama-70B-GR")

prompts = [
    # Case 1: Tomatoes_8 (Trial 1, Hr 8, TTE=2)
    """You are the tactical execution agent.
Product: Tomatoes
Current floor is $3.55.
Target asking quote is $5.52.
Buyer's incoming bid is $5.35 (1 active bidder(s)).
RiskReader indicates Bluffing: 6/10, Walk-Away: 4/10.
TTE is 2 hours remaining.

OBJECTIVE & TACTICAL GUIDELINES:
Maximize expected revenue and avoid spoilage:
- When TTE >= 4h: If buyer bluffing score is high (>=6) and offer is low, choose HOLD ($5.52) or CONCEDE slightly to defend margin.
- When TTE <= 2h (Endgame): Spoilage penalty is imminent (-100% loss). If the buyer's incoming bid is >= $3.55, choose ACCEPT to guarantee volume clearance and avoid total waste loss.
- HOLD: Defend target asking quote ($5.52).
- CONCEDE: Counter with a discounted target_price (between $3.55 and $5.52).
- ACCEPT: Accept the buyer's bid ($5.35).

Respond ONLY in valid JSON matching this schema:
{
  "risk_evaluation": "Evaluate the RiskReader's bluff and walk-away scores against current TTE and inventory.",
  "action": "HOLD|CONCEDE|ACCEPT",
  "target_price": float
}""",

    # Case 2: Beef_11 (Trial 3, Hr 8, TTE=2)
    """You are the tactical execution agent.
Product: Beef
Current floor is $13.78.
Target asking quote is $21.32.
Buyer's incoming bid is $20.50 (1 active bidder(s)).
RiskReader indicates Bluffing: 4/10, Walk-Away: 6/10.
TTE is 2 hours remaining.

OBJECTIVE & TACTICAL GUIDELINES:
Maximize expected revenue and avoid spoilage:
- When TTE >= 4h: If buyer bluffing score is high (>=6) and offer is low, choose HOLD ($21.32) or CONCEDE slightly to defend margin.
- When TTE <= 2h (Endgame): Spoilage penalty is imminent (-100% loss). If the buyer's incoming bid is >= $13.78, choose ACCEPT to guarantee volume clearance and avoid total waste loss.
- HOLD: Defend target asking quote ($21.32).
- CONCEDE: Counter with a discounted target_price (between $13.78 and $21.32).
- ACCEPT: Accept the buyer's bid ($20.50).

Respond ONLY in valid JSON matching this schema:
{
  "risk_evaluation": "Evaluate the RiskReader's bluff and walk-away scores against current TTE and inventory.",
  "action": "HOLD|CONCEDE|ACCEPT",
  "target_price": float
}""",

    # Case 3: Beef_11 (Trial 5, Hr 6, TTE=4)
    """You are the tactical execution agent.
Product: Beef
Current floor is $13.78.
Target asking quote is $21.32.
Buyer's incoming bid is $20.82 (1 active bidder(s)).
RiskReader indicates Bluffing: 4/10, Walk-Away: 6/10.
TTE is 4 hours remaining.

OBJECTIVE & TACTICAL GUIDELINES:
Maximize expected revenue and avoid spoilage:
- When TTE >= 4h: If buyer bluffing score is high (>=6) and offer is low, choose HOLD ($21.32) or CONCEDE slightly to defend margin.
- When TTE <= 2h (Endgame): Spoilage penalty is imminent (-100% loss). If the buyer's incoming bid is >= $13.78, choose ACCEPT to guarantee volume clearance and avoid total waste loss.
- HOLD: Defend target asking quote ($21.32).
- CONCEDE: Counter with a discounted target_price (between $13.78 and $21.32).
- ACCEPT: Accept the buyer's bid ($20.82).

Respond ONLY in valid JSON matching this schema:
{
  "risk_evaluation": "Evaluate the RiskReader's bluff and walk-away scores against current TTE and inventory.",
  "action": "HOLD|CONCEDE|ACCEPT",
  "target_price": float
}""",

    # Case 4: Kombucha_1 (Trial 1, Hr 4, TTE=6)
    """You are the tactical execution agent.
Product: Kombucha
Current floor is $1.73.
Target asking quote is $3.10.
Buyer's incoming bid is $3.09 (1 active bidder(s)).
RiskReader indicates Bluffing: 2/10, Walk-Away: 4/10.
TTE is 6 hours remaining.

OBJECTIVE & TACTICAL GUIDELINES:
Maximize expected revenue and avoid spoilage:
- When TTE >= 4h: If buyer bluffing score is high (>=6) and offer is low, choose HOLD ($3.10) or CONCEDE slightly to defend margin.
- When TTE <= 2h (Endgame): Spoilage penalty is imminent (-100% loss). If the buyer's incoming bid is >= $1.73, choose ACCEPT to guarantee volume clearance and avoid total waste loss.
- HOLD: Defend target asking quote ($3.10).
- CONCEDE: Counter with a discounted target_price (between $1.73 and $3.10).
- ACCEPT: Accept the buyer's bid ($3.09).

Respond ONLY in valid JSON matching this schema:
{
  "risk_evaluation": "Evaluate the RiskReader's bluff and walk-away scores against current TTE and inventory.",
  "action": "HOLD|CONCEDE|ACCEPT",
  "target_price": float
}""",

    # Case 5: Kombucha_1 (Trial 2, Hr 4, TTE=6)
    """You are the tactical execution agent.
Product: Kombucha
Current floor is $1.73.
Target asking quote is $3.10.
Buyer's incoming bid is $3.09 (1 active bidder(s)).
RiskReader indicates Bluffing: 4/10, Walk-Away: 2/10.
TTE is 6 hours remaining.

OBJECTIVE & TACTICAL GUIDELINES:
Maximize expected revenue and avoid spoilage:
- When TTE >= 4h: If buyer bluffing score is high (>=6) and offer is low, choose HOLD ($3.10) or CONCEDE slightly to defend margin.
- When TTE <= 2h (Endgame): Spoilage penalty is imminent (-100% loss). If the buyer's incoming bid is >= $1.73, choose ACCEPT to guarantee volume clearance and avoid total waste loss.
- HOLD: Defend target asking quote ($3.10).
- CONCEDE: Counter with a discounted target_price (between $1.73 and $3.10).
- ACCEPT: Accept the buyer's bid ($3.09).

Respond ONLY in valid JSON matching this schema:
{
  "risk_evaluation": "Evaluate the RiskReader's bluff and walk-away scores against current TTE and inventory.",
  "action": "HOLD|CONCEDE|ACCEPT",
  "target_price": float
}"""
]

async def run_replays():
    print(f"Replaying against 70B model: {model_70b}\n")
    for i, p in enumerate(prompts, 1):
        raw = await client.call(model_70b, [{"role": "system", "content": p}], temperature=SELLER_TEMPERATURE)
        validated = validate_output(raw, DeciderAction)
        print(f"=== 70B REPLAY OUTPUT: Case {i} ===")
        if validated:
            print(f"Action: {validated.action}")
            print(f"Target Price: {validated.target_price}")
            print(f"Risk Evaluation: {validated.risk_evaluation}")
        else:
            print(f"Raw Output: {raw}")
        print()

if __name__ == "__main__":
    asyncio.run(run_replays())
