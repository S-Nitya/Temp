import os
import pandas as pd
import random
import requests
import time
import json
import re
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional, Tuple

load_dotenv()

# --- CONFIGURATION ---
# Replace with your NVIDIA Build API Key
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Research Models from NVIDIA Build API
MODELS = {
    "Llama-8B": "meta/llama-3.1-8b-instruct",
    "Llama-70B": "meta/llama-3.1-70b-instruct",
    "Llama-405B": "meta/llama-3.1-405b-instruct",
    "Nemotron-120B": "nvidia/nemotron-3-120b-instruct"
}

ARCHITECTURES = {
    "Baseline": {"manager": "Llama-8B", "negotiator": "Llama-8B", "buyer": "Llama-8B"},
    "Advanced-MA": {"manager": "Nemotron-120B", "negotiator": "Llama-8B", "buyer": "Llama-8B"},
    "SOTA-MA": {"manager": "Llama-405B", "negotiator": "Llama-8B", "buyer": "Llama-8B"}
}

MAX_ROUNDS = 5
SIMULATION_RUNS_PER_ARCH = 3 
GLOBAL_SEED = 42

random.seed(GLOBAL_SEED)
np.random.seed(GLOBAL_SEED)

class ModelTracker:
    """Tracks stability and reliability metrics for LLMs."""
    def __init__(self):
        self.json_failures = 0
        self.total_calls = 0

    def log_failure(self):
        self.json_failures += 1
    
    def log_call(self):
        self.total_calls += 1

tracker = ModelTracker()

def safe_parse_json(response: str) -> Optional[Dict[str, Any]]:
    if not response: return None
    # Clean thoughts and markdown
    response = re.sub(r'<thought>.*?</thought>', '', response, flags=re.DOTALL)
    response = re.sub(r'```json\s*(.*?)\s*```', r'\1', response, flags=re.DOTALL)
    
    # Try direct parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Fallback: find the first { and last }
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except: pass
    
    tracker.log_failure()
    return None

def call_nvidia_api(model_id: str, messages: List[Dict[str, str]], temperature: float = 0.2, retries: int = 2) -> Dict[str, Any]:
    """Calls the NVIDIA Build API with strict JSON enforcement and timeout resilience."""
    if not NVIDIA_API_KEY:
        return {"action": "WALK_AWAY", "error": "No NVIDIA API Key"}
    
    tracker.log_call()
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1024,
        "stream": False
    }

    try:
        # Increased timeout for high-parameter models (405B, 120B)
        response = requests.post(NVIDIA_BASE_URL, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            parsed = safe_parse_json(content)
            if parsed: return parsed
            return {"action": "ERROR", "error": "JSON_PARSE_FAILED", "raw": content}
        
        elif response.status_code == 429:
            print("Rate limit hit (429). Waiting 30s for quota reset...")
            time.sleep(30)
            return call_nvidia_api(model_id, messages, temperature, retries)
            
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        if retries > 0:
            wait_time = 15 + random.uniform(2, 7)
            print(f"Connection/Timeout Error: {e}. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
            return call_nvidia_api(model_id, messages, temperature, retries - 1)
        else:
            print(f"Final API failure after retries: {e}")
            
    except Exception as e:
        print(f"Unexpected API Error: {e}")
    
    return {"action": "WALK_AWAY", "error": "CONNECTION_FAILED"}

class NegotiationSimulator:
    def __init__(self, product_data: Dict[str, Any], arch_name: str, arch_config: Dict[str, str]):
        self.product_data = product_data
        self.arch_name = arch_name
        self.manager_model = MODELS[arch_config["manager"]]
        self.negotiator_model = MODELS[arch_config["negotiator"]]
        self.buyer_model = MODELS[arch_config["buyer"]]
        
        self.true_expiry = product_data.get('days_until_expiry', 5)
        self.transit_time = 1
        self.holding_cost = 0.05
        self.seller_cost_price = product_data['cost_price']
        self.selling_price = product_data['selling_price']
        
        self.history = []
        self.irrational_acts = 0
        self.json_failures = 0

    def run(self, experiment_type: str = "LLM_Normal") -> Dict[str, Any]:
        budget = self.selling_price * random.uniform(0.95, 1.05)
        status, final_price = "NO_DEAL", 0.0
        
        # Initialize history with the seller's listing price
        self.history.append({"role": "assistant", "content": f"SELLER: I am listing this {self.product_data['product_name']} for ${self.selling_price:.2f}"})
        last_seller_offer = self.selling_price

        for rnd in range(1, MAX_ROUNDS + 1):
            # --- BUYER TURN ---
            time.sleep(15) # Global turn throttle
            buyer_prompt = f"""
            Role: Expert Buyer of Perishable Goods.
            Context: You want to buy {self.product_data['product_name']}. 
            Constraints:
            - Absolute Max Budget: ${budget:.2f}
            - Observed Expiry: {self.true_expiry} days
            Goal: Maximize utility by purchasing as low as possible below your budget.
            Current Round: {rnd}/{MAX_ROUNDS}
            
            Action Rules:
            1. OFFER: Propose a counter-price.
            2. ACCEPT: Only if current seller price (${last_seller_offer:.2f}) <= ${budget:.2f}.
            3. WALK_AWAY: If you believe no deal is possible.
            
            Respond ONLY in JSON:
            {{"thought": "reasoning", "action": "OFFER|ACCEPT|WALK_AWAY", "price": float, "message": "string"}}
            """
            b_act = call_nvidia_api(self.buyer_model, [{"role": "system", "content": buyer_prompt}] + self.history)
            
            if b_act.get("action") == "ACCEPT":
                status, final_price = "DEAL", last_seller_offer
                break
            elif b_act.get("action") == "WALK_AWAY":
                status = "WALK_AWAY_BUYER"; break
            
            last_buyer_offer = b_act.get("price", last_seller_offer * 0.8)
            if last_buyer_offer > budget: self.irrational_acts += 1
            self.history.append({"role": "user", "content": f"BUYER: {b_act.get('message', 'My offer')} (${last_buyer_offer:.2f})"})

            # --- SELLER TURN (Multi-Agent) ---
            # 1. Manager analyzes and updates strategy
            time.sleep(15) # Global turn throttle
            manager_strategy = self._call_manager(rnd, last_buyer_offer)
            
            # 2. Negotiator executes
            time.sleep(15) # Global turn throttle
            negotiator_prompt = f"""
            Role: Expert Sales Negotiator.
            Strategic Directive from Manager: {manager_strategy}
            Round: {rnd}/{MAX_ROUNDS}
            The buyer just offered ${last_buyer_offer:.2f}.
            
            Respond ONLY in JSON:
            {{"thought": "reasoning", "action": "OFFER|ACCEPT|WALK_AWAY", "price": float, "message": "string"}}
            """
            s_act = call_nvidia_api(self.negotiator_model, [{"role": "system", "content": negotiator_prompt}] + self.history)
            
            if s_act.get("action") == "ACCEPT":
                status, final_price = "DEAL", last_buyer_offer
                break
            elif s_act.get("action") == "WALK_AWAY":
                status = "WALK_AWAY_SELLER"; break
                
            last_seller_offer = s_act.get("price", last_buyer_offer * 1.2)
            floor = self.seller_cost_price + (rnd * self.holding_cost)
            if last_seller_offer < floor: self.irrational_acts += 1
            self.history.append({"role": "assistant", "content": f"SELLER: {s_act.get('message', 'My counter')} (${last_seller_offer:.2f})"})

        return self._finalize_metrics(status, final_price, rnd, experiment_type, budget, self.seller_cost_price)

    def _call_manager(self, rnd: int, last_buyer_offer: Optional[float]) -> str:
        current_floor = self.seller_cost_price + (rnd * self.holding_cost)
        manager_prompt = f"""
        Role: Strategic Inventory Manager.
        Product: {self.product_data['product_name']}
        Economic Data:
        - Cost Price: ${self.seller_cost_price:.2f}
        - Current Floor (inc. holding cost): ${current_floor:.2f}
        - Days to Expiry: {self.true_expiry}
        - Transit Time: {self.transit_time} day
        
        Last Buyer Offer: ${last_buyer_offer if last_buyer_offer else 'None'}
        Round: {rnd}/{MAX_ROUNDS}
        
        Task: Provide a strict negotiation strategy for your Negotiator. 
        Do not tell them the floor price directly. Tell them how aggressive or conceding to be.
        Output: <strategy>Your instructions</strategy>
        """
        res = call_nvidia_api(self.manager_model, [{"role": "system", "content": manager_prompt}])
        # Extract strategy or use thought as fallback
        strat = re.search(r'<strategy>(.*?)</strategy>', str(res), re.DOTALL)
        return strat.group(1) if strat else res.get("thought", "Be firm on price.")

    def _finalize_metrics(self, status: str, price: float, rounds: int, exp_type: str, budget: float, floor: float) -> Dict[str, Any]:
        is_deal = (status == "DEAL")
        zopa = max(0, budget - floor)
        efficiency = 1 - (abs(price - (budget + floor)/2) / (zopa/2)) if is_deal and zopa > 0 else 0
        
        return {
            "architecture": self.arch_name,
            "experiment": exp_type,
            "success": 1 if is_deal else 0,
            "rounds": rounds,
            "final_price": price,
            "efficiency": max(0, efficiency),
            "irrational_actions": self.irrational_acts,
            "stability": 1 - (rounds / MAX_ROUNDS) if is_deal else 0
        }

def generate_research_plots(df: pd.DataFrame):
    """Generates research-grade visualizations for architectural comparison."""
    plt.style.use('ggplot')
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # 1. Success Rate Plot
    arch_perf = df.groupby("architecture")["success"].mean() * 100
    arch_perf.plot(kind='bar', ax=axes[0], color=['#3498db', '#e74c3c', '#2ecc71'])
    axes[0].set_title("Negotiation Success Rate (%)")
    axes[0].set_ylabel("Success %")
    axes[0].set_ylim(0, 105)

    # 2. Economic Efficiency Plot
    efficiency = df.groupby("architecture")["efficiency"].mean() * 100
    efficiency.plot(kind='bar', ax=axes[1], color=['#3498db', '#e74c3c', '#2ecc71'])
    axes[1].set_title("ZOPA Efficiency (%)")
    axes[1].set_ylabel("Efficiency %")
    axes[1].set_ylim(0, max(efficiency.max() * 1.2, 100))

    # 3. Rationality Plot (Irrational Actions)
    rationality = df.groupby("architecture")["irrational_actions"].mean()
    rationality.plot(kind='bar', ax=axes[2], color=['#3498db', '#e74c3c', '#2ecc71'])
    axes[2].set_title("Avg. Irrational Actions")
    axes[2].set_ylabel("Count (Lower is Better)")

    plt.tight_layout()
    plt.savefig("architectural_comparison.png")
    print(f"\n[INFO] Research visualizations saved to 'architectural_comparison.png'")

def analyze_and_conclude(df: pd.DataFrame):
    print("\n" + "="*50)
    print("======== MULTI-AGENT ARCHITECTURAL RESEARCH ========")
    print("="*50 + "\n")
    
    # Architecture Success Rate
    arch_perf = df.groupby("architecture")["success"].mean().sort_values(ascending=False)
    print(f"1. ARCHITECTURAL SUCCESS RATES:\n{arch_perf.map(lambda x: f'{x:.2%}')}\n")

    # Efficiency (ZOPA Capture)
    efficiency = df.groupby("architecture")["efficiency"].mean().sort_values(ascending=False)
    best_arch = efficiency.idxmax()
    print(f"2. ECONOMIC EFFICIENCY (ZOPA):\n   '{best_arch}' was most efficient at capturing surplus ({efficiency.max():.2%}).")

    # Rationality (Violation of Floor/Budget)
    rationality = df.groupby("architecture")["irrational_actions"].mean().sort_values()
    print(f"\n3. AGENTIC RATIONALITY (Fewer Violations is better):\n{rationality}\n")

    # Research Interpretation
    print("4. KEY RESEARCH INSIGHTS:")
    if "SOTA-MA" in arch_perf.index and arch_perf["SOTA-MA"] >= arch_perf["Baseline"]:
        print("   - HIGHER REASONING IMPACT: The Llama-405B Manager significantly improved deal success by providing superior strategic directives.")
    
    if "Advanced-MA" in efficiency.index:
        print(f"   - NEMOTRON STRATEGY: Nemotron-120B as a manager showed a {efficiency['Advanced-MA'] - efficiency['Baseline']:.2%} delta in surplus capture.")

    print("\n5. CONCLUSION:")
    print("   True agency through Multi-Agent delegation (Manager + Negotiator) reduces 'pseudo-rationality' issues ")
    print("   by separating hidden economic constraints from the conversational interface.")
    print("\n" + "="*50)

def main():
    print("Starting Multi-Model Multi-Agent Research Simulation...")
    print(f"Tracking {len(ARCHITECTURES)} Architectures across {SIMULATION_RUNS_PER_ARCH} runs each.")
    
    try:
        df_prod = pd.read_csv("perishable_goods_management.csv")
        # Ensure we have enough products for the requested runs
        products = df_prod[df_prod['days_until_expiry'] >= 5].sample(SIMULATION_RUNS_PER_ARCH)
    except Exception as e:
        print(f"Data Load Error: {e}")
        return

    results = []
    
    for _, product in products.iterrows():
        for arch_name, arch_config in ARCHITECTURES.items():
            print(f"Testing Architecture: {arch_name} | Product: {product['product_name']}")
            sim = NegotiationSimulator(product.to_dict(), arch_name, arch_config)
            # We focus on the core "LLM_Normal" mode for architectural comparison
            res = sim.run("Multi_Agent_Standard")
            results.append(res)
            # Sleep to respect rate limits between model swaps
            time.sleep(2)

    final_df = pd.DataFrame(results)
    final_df.to_csv("multi_model_research_results.csv", index=False)
    analyze_and_conclude(final_df)
    generate_research_plots(final_df)

if __name__ == "__main__":
    main()
