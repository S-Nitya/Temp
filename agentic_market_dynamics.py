import os
import pandas as pd
import random
import requests
import time
import numpy as np
from math import exp
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional

load_dotenv()

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
MAX_ROUNDS = 8
SIMULATION_RUNS = 25
SIGNAL_DECAY_RATE = 0.5  # Lambda for exponential decay

def retry_api_call(max_retries: int = 3, delay: float = 2.0):
    """Decorator for robust API handling."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                result = func(*args, **kwargs)
                if result: return result
                time.sleep(delay * (attempt + 1))
            return ""
        return wrapper
    return decorator

@retry_api_call()
def call_groq(model: str, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    """Helper function to call Groq API with retry logic."""
    if not GROQ_API_KEY:
        return ""
    
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": 512
    }
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
    except Exception:
        pass
    return ""

# --- ECONOMIC UTILITY FUNCTIONS ---

def sigmoid(x: float) -> float:
    """Standard sigmoid function with overflow protection."""
    x = max(-50, min(50, x))
    return 1 / (1 + exp(-x))

def calculate_utility(price: float, reservation_price: float, role: str) -> float:
    """Calculates economic surplus (utility)."""
    return (reservation_price - price) if role == "buyer" else (price - reservation_price)

class NegotiationSimulator:
    def __init__(self, product_data: Dict[str, Any], seller_model: str, buyer_model: str = DEFAULT_MODEL, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        self.product_data = product_data
        self.transit_time = product_data.get('transit_time', random.randint(1, 2))
        self.holding_cost = product_data.get('holding_cost', random.uniform(0.05, 0.2))
        
        self.seller_model = seller_model
        self.buyer_model = buyer_model
        
        self.urgency = random.uniform(0.5, 1.5)
        self.consumption_rate = random.uniform(0.8, 2.0)
        
        # Initial hidden state (FIX: Initialize expiry before calling calc methods)
        self.buyer_observed_expiry = self.product_data['days_until_expiry']
        self.buyer_max_price = self._calculate_buyer_max()
        self.seller_min_price = self._calculate_seller_min()
        
        self.history = []
        self.signals = {"urgency": 0.0, "confidence": 0.0, "desperation": 0.0}
        
        # Metrics
        self.total_decisions = 0
        self.accept_count = 0
        self.walk_away_count = 0
        self.irrational_accept = 0
        self.irrational_reject = 0
        self.zopa_exists = self.buyer_max_price >= self.seller_min_price

    def _calculate_buyer_max(self) -> float:
        sp = self.product_data['selling_price']
        expiry_factor = min(1.0, (self.buyer_observed_expiry * self.consumption_rate) / 10.0)
        return round(sp * (0.6 + 0.3 * expiry_factor + 0.1 * (self.urgency / 1.5)), 2)

    def _calculate_seller_min(self) -> float:
        cp = self.product_data['cost_price']
        expiry = self.product_data['days_until_expiry']
        risk_factor = 1.0 / (1.0 + expiry)
        return round(max(cp * 1.05, cp * (1.2 - 0.5 * risk_factor)), 2)

    def extract_and_update_signals(self, text: str):
        """Extracts and normalizes linguistic signals with exponential decay."""
        decay = exp(-SIGNAL_DECAY_RATE)
        for k in self.signals:
            self.signals[k] *= decay

        text = text.lower()
        word_count = max(1, len(text.split()))

        self.signals["urgency"] += min(0.5, (sum(1 for w in ["urgent", "expire", "now", "today", "fast"] if w in text) / word_count) * 10)
        self.signals["confidence"] += min(0.5, (sum(1 for w in ["firm", "final", "last", "non-negotiable"] if w in text) / word_count) * 10)
        self.signals["desperation"] += min(0.5, (sum(1 for w in ["please", "help", "need", "beg", "kindly"] if w in text) / word_count) * 10)

        for k in self.signals:
            self.signals[k] = min(1.0, self.signals[k])

    def decision_engine(self, suggested_price: float, role: str, round_num: int, 
                        current_buyer_max: float, current_seller_min: float, experiment_type: str) -> str:
        """Core decision logic combining Logistics Manager and Economic Negotiator."""
        self.total_decisions += 1
        
        remaining_life = self.product_data['days_until_expiry'] - round_num
        if remaining_life < self.transit_time:
            return "WALK_AWAY"

        res_price = current_buyer_max if role == "buyer" else current_seller_min
        utility = calculate_utility(suggested_price, res_price, role)
        
        if role == "seller":
            utility -= (self.holding_cost * round_num)

        zopa_width = max(1.0, abs(current_buyer_max - current_seller_min))
        norm_utility = utility / zopa_width
        
        time_pressure = (round_num / MAX_ROUNDS) * 1.5
        k = 5.0 if experiment_type == "LLM_Forced_Rational" else 3.0
        score = (norm_utility * k) + time_pressure
        
        signal_impact = (0.5 * self.signals["urgency"]) + (0.8 * self.signals["desperation"]) - (0.6 * self.signals["confidence"])
        accept_prob = sigmoid(score + signal_impact)
        
        if random.random() < accept_prob:
            if utility < -(zopa_width * 0.1) and experiment_type != "LLM_Forced_Rational":
                return "COUNTER"
            self.accept_count += 1
            if utility < 0: self.irrational_accept += 1
            return "ACCEPT"
        
        walk_away_score = -2.0 + 4.0 * (round_num / MAX_ROUNDS) - 2.0 * norm_utility
        if random.random() < sigmoid(walk_away_score):
            self.walk_away_count += 1
            return "WALK_AWAY"
        
        if utility > 0: self.irrational_reject += 1
        return "COUNTER"

    def run(self, experiment_type: str = "LLM_Normal") -> Dict[str, Any]:
        true_expiry = self.product_data['days_until_expiry']
        self.buyer_observed_expiry = true_expiry
        
        if experiment_type == "Asymmetric_Info":
            self.buyer_observed_expiry = max(1, true_expiry + random.randint(-3, 1))
        
        is_adversarial = (experiment_type == "Adversarial")
        adversarial_prompt = ""
        if is_adversarial:
            tactic = random.choice(["charity appeal", "false competitor quote", "bulk promise"])
            adversarial_prompt = f" MISSION: Use an adversarial tactic ({tactic}) to drive price down."

        last_seller_price = self.product_data['selling_price']
        last_buyer_offer = last_seller_price * 0.6
        status, final_price = "No Deal", 0.0

        for round_num in range(1, MAX_ROUNDS + 1):
            decay_factor = (true_expiry - round_num) / max(1, true_expiry)
            curr_seller_min = round(self.seller_min_price * (0.9 + 0.1 * decay_factor), 2)
            
            obs_decay = (self.buyer_observed_expiry - round_num) / max(1, self.buyer_observed_expiry)
            # Dynamic Belief Update
            self.buyer_max_price = self._calculate_buyer_max()
            curr_buyer_max = round(self.buyer_max_price * (0.8 + 0.2 * obs_decay), 2)

            # --- BUYER TURN ---
            concession = (curr_buyer_max - last_buyer_offer) * (0.1 + 0.1 * (round_num / MAX_ROUNDS))
            target_offer = round(last_buyer_offer + concession * random.uniform(0.8, 1.2), 2)
            
            buyer_inst = (f"Buyer. Limit ${curr_buyer_max}. Offer ${target_offer}. "
                          f"Observed expiry {self.buyer_observed_expiry}d. Round {round_num}. {adversarial_prompt}")
            
            buyer_msg = call_groq(self.buyer_model, [{"role": "system", "content": buyer_inst}] + self.history)
            if buyer_msg:
                self.history.append({"role": "assistant", "content": f"BUYER: {buyer_msg}"})
                self.extract_and_update_signals(buyer_msg)
            
            last_buyer_offer = target_offer

            # --- SELLER DECISION ---
            decision = self.decision_engine(last_buyer_offer, "seller", round_num, curr_buyer_max, curr_seller_min, experiment_type)
            if decision == "ACCEPT":
                status, final_price = "Deal", last_buyer_offer
                break
            elif decision == "WALK_AWAY":
                status = "Walk Away (Seller)"
                break

            # --- SELLER TURN ---
            seller_concession = (last_seller_price - curr_seller_min) * (0.1 + 0.05 * round_num)
            new_seller_price = round(max(curr_seller_min, last_seller_price - seller_concession), 2)
            
            seller_inst = f"Seller. Floor ${curr_seller_min}. Counter ${new_seller_price}. True expiry {true_expiry}d."
            seller_msg = call_groq(self.seller_model, [{"role": "system", "content": seller_inst}] + self.history)
            if seller_msg:
                self.history.append({"role": "user", "content": f"SELLER: {seller_msg}"})
                self.extract_and_update_signals(seller_msg)
            
            last_seller_price = new_seller_price

            # --- BUYER DECISION ---
            decision = self.decision_engine(last_seller_price, "buyer", round_num, curr_buyer_max, curr_seller_min, experiment_type)
            if decision == "ACCEPT":
                status, final_price = "Deal", last_seller_price
                break
            elif decision == "WALK_AWAY":
                status = "Walk Away (Buyer)"
                break

        return self._finalize_metrics(status, final_price, round_num, experiment_type, true_expiry)

    def _finalize_metrics(self, status: str, price: float, rounds: int, exp_type: str, true_expiry: int) -> Dict[str, Any]:
        deal = (status == "Deal")
        spoilage = 1 if (deal and (true_expiry - rounds) < self.transit_time) else 0
        
        zopa_max = self.buyer_max_price 
        zopa_min = self.seller_min_price

        # ZOPA check
        potential_surplus = max(0, zopa_max - zopa_min)

        # Actual surplus
        actual_surplus = 0
        if deal and not spoilage and potential_surplus > 0:
            actual_surplus = (zopa_max - price) + (price - zopa_min)

        # Efficiency (midpoint-based fairness)
        if deal and potential_surplus > 0:
            mid_price = (zopa_max + zopa_min) / 2
            price_deviation = abs(price - mid_price)
            efficiency = 1 - (price_deviation / potential_surplus)
        else:
            efficiency = 0

        # Surplus split (seller share)
        seller_surplus = max(0, price - zopa_min)
        surplus_split = (seller_surplus / actual_surplus) if actual_surplus > 0 else 0

        # Optional (for analysis)
        buyer_surplus_share = 1 - surplus_split if actual_surplus > 0 else 0

        return {
            "EXPERIMENT": exp_type,
            "SUCCESS": 1 if (deal and not spoilage) else 0,
            "FAILED_LOGISTICS": 1 if (not deal and (true_expiry - rounds) < self.transit_time) else 0,
            "FAILED_STRATEGIC": 1 if (not deal and potential_surplus > 0 and (true_expiry - rounds) >= self.transit_time) else 0,
            "SPOILAGE": spoilage,
            "ROUNDS": rounds,
            "FINAL_PRICE": price,
            "EFFICIENCY": round(efficiency, 3),
            "SELLER_SURPLUS_SHARE": round(surplus_split, 3),
            "BUYER_SURPLUS_SHARE": round(buyer_surplus_share, 3),
            "IRRATIONAL_ACTS": self.irrational_accept + self.irrational_reject
        }

def main():
    print("Starting Optimized Negotiation Research Simulation...")
    try:
        df = pd.read_csv("perishable_goods_management.csv").dropna(subset=['selling_price', 'cost_price', 'days_until_expiry'])
    except FileNotFoundError:
        print("Error: Dataset not found.")
        return

    experiment_types = ["LLM_Normal", "Asymmetric_Info", "Adversarial", "LLM_Forced_Rational"]
    results = []

    for i in range(SIMULATION_RUNS):
        print(f"\n" + "="*60 + f"\nRUN {i+1}/{SIMULATION_RUNS}\n" + "="*60)
        product_sample = df.sample(1).iloc[0].to_dict()
        run_seed = random.randint(0, 10000)
        
        for exp_type in experiment_types:
            sim = NegotiationSimulator(product_sample, seller_model=DEFAULT_MODEL, seed=run_seed)
            res = sim.run(exp_type)
            results.append(res)
            print(f"Run {i+1} | {exp_type}: {'Success' if res['SUCCESS'] else 'Fail'}")

    results_df = pd.DataFrame(results)
    print("\n" + "="*140 + "\nRESEARCH RESULTS SUMMARY\n" + "="*140)
    summary = results_df.groupby("EXPERIMENT").agg({
        "SUCCESS": "mean",
        "FAILED_LOGISTICS": "mean",
        "SPOILAGE": "mean",
        "EFFICIENCY": "mean",
        "ROUNDS": "mean"
    })
    print(summary.to_string())
    results_df.to_csv("negotiation_research_results.csv", index=False)

if __name__ == "__main__":
    main()
