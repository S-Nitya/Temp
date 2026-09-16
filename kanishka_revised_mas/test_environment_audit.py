"""
Deterministic Unit Test Suite for Environment Semantics (Part F: Tests 1 to 8).
Verifies physical time separation, terminal states, true spoilage accounting,
and buyer bid preservation before any benchmark rerun.
"""
import asyncio
from typing import Dict, Any, List, Optional
from kanishka_revised_mas.buyer import BuyerPrivateState
from kanishka_revised_mas.environment import NegotiationEnvironment


class MockLLMClient:
    """Mock LLM client producing deterministic responses for unit testing."""
    def __init__(self, buyer_responses: List[Dict[str, Any]], seller_responses: Optional[List[Dict[str, Any]]] = None):
        self.buyer_responses = list(buyer_responses)
        self.seller_responses = list(seller_responses) if seller_responses else []
        self.call_records = []

    async def call_agent(self, agent_name: str, **kwargs) -> Dict[str, Any]:
        if agent_name == "Buyer":
            if self.buyer_responses:
                return self.buyer_responses.pop(0)
            return {"action": "WALK_AWAY", "counter_offer": None, "message": "Passing."}
        elif agent_name == "StrategicBrain":
            return {"opening_quote": 10.0, "seller_floor": 7.0, "strategy_label": "DYNAMIC_YIELD", "rationale": "Test"}
        elif agent_name == "BullDebater":
            return {"recommended_quote": 10.5, "recommended_floor": 7.5, "argument": "Bull"}
        elif agent_name == "BearDebater":
            return {"recommended_quote": 9.5, "recommended_floor": 7.0, "argument": "Bear"}
        elif agent_name == "DebateJudge":
            return {"final_opening_quote": 10.0, "final_seller_floor": 7.0, "strategy_label": "DYNAMIC_YIELD"}
        elif agent_name == "RiskReader":
            return {"bluffing_probability": 0.2, "walk_away_probability": 0.1, "detected_tactic": "SINCERE_CONCESSION"}
        elif agent_name == "ListingDecider":
            if self.seller_responses:
                return self.seller_responses.pop(0)
            return {"action": "HOLD", "target_price": 10.0, "rationale": "Holding price"}
        elif agent_name == "Spokesperson":
            return {"message": "We can offer this price."}
        return {"action": "HOLD"}


async def run_environment_audit_tests():
    print("=" * 60)
    print("RUNNING DETERMINISTIC ENVIRONMENT AUDIT TEST SUITE (PART F)")
    print("=" * 60)
    passed = 0
    total = 8

    # Item fixtures
    item_18h = {"item_id": "fresh_fish_2", "product_name": "Fresh Fish", "cost_price": 7.0, "retail_reference": 11.0, "starting_remaining_hours": 18.0, "expiry_regime": "Critical"}
    item_336h = {"item_id": "hard_cheese_15", "product_name": "Hard Cheese", "cost_price": 5.0, "retail_reference": 9.0, "starting_remaining_hours": 336.0, "expiry_regime": "Low"}
    item_2h = {"item_id": "strawberries_fast", "product_name": "Fast Expiry", "cost_price": 3.0, "retail_reference": 5.0, "starting_remaining_hours": 2.0, "expiry_regime": "Critical"}

    b_state = BuyerPrivateState(
        buyer_id="test_b",
        target_item_id="test_item",
        product_name="Test Product",
        budget_ceiling=15.0,
        private_valuation=12.0,
        urgency="MODERATE",
        price_sensitivity="MODERATE",
        persona="PRAGMATIC_SHOPPER"
    )

    # -------------------------------------------------------------------------
    # TEST 1: 18 hour item, 3 exchanges, physical time remains below expiry
    # Expected: NOT EXPIRED (final_status == "MAX_ROUNDS_UNRESOLVED", spoilage_loss == 0.0)
    # -------------------------------------------------------------------------
    llm1 = MockLLMClient(
        buyer_responses=[
            {"action": "COUNTER", "counter_offer": 8.0, "message": "8.0"},
            {"action": "COUNTER", "counter_offer": 8.2, "message": "8.2"},
            {"action": "COUNTER", "counter_offer": 8.4, "message": "8.4"},
            {"action": "COUNTER", "counter_offer": 8.5, "message": "8.5"},
        ],
        seller_responses=[
            {"action": "HOLD", "target_price": 10.0},
            {"action": "HOLD", "target_price": 10.0},
            {"action": "HOLD", "target_price": 10.0},
        ]
    )
    env1 = NegotiationEnvironment(mode="MAS", llm_client=llm1, max_exchanges=3, time_per_exchange=1.0)
    res1 = await env1.execute_item_transaction(item_18h, b_state)
    assert res1["final_status"] == "MAX_ROUNDS_UNRESOLVED", f"Test 1 failed: status was {res1['final_status']}"
    assert res1["spoilage_loss"] == 0.0, f"Test 1 failed: spoilage was {res1['spoilage_loss']}"
    assert res1["current_simulated_time"] == 3.0, f"Test 1 failed: simulated time was {res1['current_simulated_time']}"
    assert res1["remaining_shelf_life"] == 15.0, f"Test 1 failed: remaining shelf life was {res1['remaining_shelf_life']}"
    print(" [PASS] Test 1: 18h item with 3 exchanges -> NOT EXPIRED (MAX_ROUNDS_UNRESOLVED, Spoilage=$0.00).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 2: 336 hour item, 3 exchanges, physical time remains below expiry
    # Expected: NOT EXPIRED (final_status == "MAX_ROUNDS_UNRESOLVED", spoilage_loss == 0.0)
    # -------------------------------------------------------------------------
    llm2 = MockLLMClient(
        buyer_responses=[
            {"action": "COUNTER", "counter_offer": 6.0, "message": "6.0"},
            {"action": "COUNTER", "counter_offer": 6.2, "message": "6.2"},
            {"action": "COUNTER", "counter_offer": 6.4, "message": "6.4"},
            {"action": "COUNTER", "counter_offer": 6.5, "message": "6.5"},
        ],
        seller_responses=[
            {"action": "HOLD", "target_price": 8.0},
            {"action": "HOLD", "target_price": 8.0},
            {"action": "HOLD", "target_price": 8.0},
        ]
    )
    env2 = NegotiationEnvironment(mode="MAS", llm_client=llm2, max_exchanges=3, time_per_exchange=1.0)
    res2 = await env2.execute_item_transaction(item_336h, b_state)
    assert res2["final_status"] == "MAX_ROUNDS_UNRESOLVED", f"Test 2 failed: status was {res2['final_status']}"
    assert res2["spoilage_loss"] == 0.0, f"Test 2 failed: spoilage was {res2['spoilage_loss']}"
    assert res2["current_simulated_time"] == 3.0, f"Test 2 failed: simulated time was {res2['current_simulated_time']}"
    assert res2["remaining_shelf_life"] == 333.0, f"Test 2 failed: remaining shelf life was {res2['remaining_shelf_life']}"
    print(" [PASS] Test 2: 336h item with 3 exchanges -> NOT EXPIRED (MAX_ROUNDS_UNRESOLVED, Spoilage=$0.00).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 3: Buyer COUNTER with valid bid
    # Expected: RiskReader invoked, Decider invoked, buyer bid preserved exactly
    # -------------------------------------------------------------------------
    llm3 = MockLLMClient(
        buyer_responses=[
            {"action": "COUNTER", "counter_offer": 8.75, "message": "I offer exactly $8.75."},
            {"action": "ACCEPT", "counter_offer": None, "message": "Accepted."},
        ],
        seller_responses=[
            {"action": "CONCEDE", "target_price": 9.0},
        ]
    )
    env3 = NegotiationEnvironment(mode="MAS", llm_client=llm3, max_exchanges=3, time_per_exchange=1.0)
    res3 = await env3.execute_item_transaction(item_18h, b_state)
    # Check timeline step 0 for preserved buyer bid, and step 1 for tactical pipeline invocation
    t_step0 = res3["timeline"][0]
    t_step1 = res3["timeline"][1]
    assert t_step0["buyer_bid"] == 8.75, f"Test 3 failed: buyer bid not preserved (got {t_step0['buyer_bid']})"
    assert t_step1["risk_reader_invoked"] is True, "Test 3 failed: RiskReader was not invoked"
    assert t_step1["decider_invoked"] is True, "Test 3 failed: Decider was not invoked"
    assert t_step1["spokesperson_invoked"] is True, "Test 3 failed: Spokesperson was not invoked"
    print(" [PASS] Test 3: Buyer COUNTER -> RiskReader & Decider invoked, buyer bid ($8.75) strictly preserved.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 4: Buyer COUNTER with malformed/missing bid
    # Expected: retry or INVALID_BUYER_RESPONSE. Never interpret as $0.00.
    # -------------------------------------------------------------------------
    llm4 = MockLLMClient(
        buyer_responses=[
            {"action": "COUNTER", "counter_offer": "none", "message": "bad bid"},
            {"action": "COUNTER", "counter_offer": None, "message": "missing bid"},
            {"action": "COUNTER", "counter_offer": 0.0, "message": "zero bid"},
        ]
    )
    env4 = NegotiationEnvironment(mode="MAS", llm_client=llm4, max_exchanges=3, time_per_exchange=1.0)
    res4 = await env4.execute_item_transaction(item_18h, b_state)
    assert res4["final_status"] == "INVALID_BUYER_RESPONSE", f"Test 4 failed: status was {res4['final_status']}"
    assert res4["timeline"][0]["buyer_bid"] is None, f"Test 4 failed: bid was interpreted as {res4['timeline'][0]['buyer_bid']}"
    assert res4["spoilage_loss"] == 0.0, f"Test 4 failed: spoilage charged on invalid response {res4['spoilage_loss']}"
    print(" [PASS] Test 4: Malformed/Missing bid -> INVALID_BUYER_RESPONSE (never interpreted as $0.00).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 5: Maximum negotiation rounds reached before expiry
    # Expected: MAX_ROUNDS_UNRESOLVED, No spoilage
    # -------------------------------------------------------------------------
    llm5 = MockLLMClient(
        buyer_responses=[
            {"action": "COUNTER", "counter_offer": 7.5, "message": "7.5"},
            {"action": "COUNTER", "counter_offer": 7.6, "message": "7.6"},
            {"action": "COUNTER", "counter_offer": 7.7, "message": "7.7"},
            {"action": "COUNTER", "counter_offer": 7.8, "message": "7.8"},
        ],
        seller_responses=[
            {"action": "HOLD", "target_price": 9.5},
            {"action": "HOLD", "target_price": 9.5},
            {"action": "HOLD", "target_price": 9.5},
        ]
    )
    env5 = NegotiationEnvironment(mode="MAS", llm_client=llm5, max_exchanges=3, time_per_exchange=1.0)
    res5 = await env5.execute_item_transaction(item_18h, b_state)
    assert res5["final_status"] == "MAX_ROUNDS_UNRESOLVED"
    assert res5["spoilage_loss"] == 0.0
    assert res5["number_of_exchanges"] == 3
    print(" [PASS] Test 5: Max rounds reached before expiry -> MAX_ROUNDS_UNRESOLVED, Spoilage=$0.00.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 6: Physical time reaches expiry while unsold
    # Expected: EXPIRED, Spoilage loss equals item cost
    # -------------------------------------------------------------------------
    llm6 = MockLLMClient(
        buyer_responses=[
            {"action": "COUNTER", "counter_offer": 3.2, "message": "3.2"},
            {"action": "COUNTER", "counter_offer": 3.3, "message": "3.3"},
            {"action": "COUNTER", "counter_offer": 3.4, "message": "3.4"},
        ],
        seller_responses=[
            {"action": "HOLD", "target_price": 4.5},
            {"action": "HOLD", "target_price": 4.5},
        ]
    )
    # item_2h has 2 hours remaining. 3 exchanges at 1h/exchange exceeds 2h expiry.
    env6 = NegotiationEnvironment(mode="MAS", llm_client=llm6, max_exchanges=3, time_per_exchange=1.0)
    res6 = await env6.execute_item_transaction(item_2h, b_state)
    assert res6["final_status"] == "EXPIRED", f"Test 6 failed: status was {res6['final_status']}"
    assert res6["spoilage_loss"] == item_2h["cost_price"], f"Test 6 failed: spoilage was {res6['spoilage_loss']}"
    assert res6["item_profit"] == -item_2h["cost_price"], f"Test 6 failed: profit was {res6['item_profit']}"
    print(f" [PASS] Test 6: Physical time reached expiry while unsold -> EXPIRED (Spoilage=${res6['spoilage_loss']:.2f} == Cost).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 7: Item sold before expiry
    # Expected: SOLD, Spoilage loss = 0
    # -------------------------------------------------------------------------
    llm7 = MockLLMClient(
        buyer_responses=[
            {"action": "COUNTER", "counter_offer": 8.0, "message": "8.0"},
            {"action": "ACCEPT", "counter_offer": None, "message": "Deal at 9.0."},
        ],
        seller_responses=[
            {"action": "CONCEDE", "target_price": 9.0},
        ]
    )
    env7 = NegotiationEnvironment(mode="MAS", llm_client=llm7, max_exchanges=3, time_per_exchange=1.0)
    res7 = await env7.execute_item_transaction(item_18h, b_state)
    assert res7["final_status"] == "SOLD", f"Test 7 failed: status was {res7['final_status']}"
    assert res7["spoilage_loss"] == 0.0, f"Test 7 failed: spoilage was {res7['spoilage_loss']}"
    assert res7["final_price"] == 9.0, f"Test 7 failed: sale price was {res7['final_price']}"
    assert res7["item_profit"] == 2.0, f"Test 7 failed: item profit was {res7['item_profit']}"
    print(" [PASS] Test 7: Item sold before expiry -> SOLD (Sale=$9.00, Spoilage=$0.00).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 8: Buyer WALK_AWAY before expiry
    # Expected: BUYER_WALK_AWAY, No spoilage at that moment
    # -------------------------------------------------------------------------
    llm8 = MockLLMClient(
        buyer_responses=[
            {"action": "WALK_AWAY", "counter_offer": None, "message": "I pass."},
        ]
    )
    env8 = NegotiationEnvironment(mode="MAS", llm_client=llm8, max_exchanges=3, time_per_exchange=1.0)
    res8 = await env8.execute_item_transaction(item_18h, b_state)
    assert res8["final_status"] == "BUYER_WALK_AWAY", f"Test 8 failed: status was {res8['final_status']}"
    assert res8["spoilage_loss"] == 0.0, f"Test 8 failed: spoilage was {res8['spoilage_loss']}"
    assert res8["item_profit"] == 0.0, f"Test 8 failed: item profit was {res8['item_profit']}"
    print(" [PASS] Test 8: Buyer WALK_AWAY before expiry -> BUYER_WALK_AWAY (Spoilage=$0.00).")
    passed += 1

    print("=" * 60)
    print(f"ALL {passed}/{total} DETERMINISTIC AUDIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    asyncio.run(run_environment_audit_tests())
