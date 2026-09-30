import os
import sys
import time
import json
import traceback
import re
import pandas as pd
import dspy
import tiktoken
from tenacity import retry, wait_exponential, stop_after_attempt
from dotenv import load_dotenv

try:
    from .config import ProductConfig
except ImportError:
    from config import ProductConfig

load_dotenv()

# Configure DSPy
os.environ["OPENAI_API_KEY"] = os.getenv("OPENROUTER_API_KEY", "")
lm = dspy.LM(
    "openai/meta-llama/llama-3.3-70b-instruct",
    api_base="https://openrouter.ai/api/v1", 
    api_key=os.getenv("OPENROUTER_API_KEY"), 
    max_tokens=1000
)
dspy.configure(lm=lm)

def log(msg):
    print(msg, flush=True)

def extract_float(val) -> float:
    try:
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val).replace(',', ''))
        if nums:
            return float(nums[0])
        return 0.0
    except:
        return 0.0

# ---------------------------------------------------------
# DSPy Signatures
# ---------------------------------------------------------

class StateSummarizer(dspy.Signature):
    """Summarize the buyer's sentiment and their current target price to avoid context bloat."""
    buyer_last_message = dspy.InputField(desc="The most recent message from the buyer.")
    current_round = dspy.InputField(desc="The current round number.")
    
    buyer_sentiment_score = dspy.OutputField(desc="Integer 1-10. 1 = angry/walking away, 10 = happy/cooperative. Output exactly one integer.")
    buyer_price_target = dspy.OutputField(desc="The exact float price the buyer is currently demanding. Output exactly one number, no dollar signs.")

class PolicyOptimizer(dspy.Signature):
    """Determine the optimal target counter-offer and tactic based on mathematical state and buyer sentiment.
    RULES:
    1. If buyer_sentiment_score <= 3, the buyer is about to walk away; you MUST set target_counter_offer very close to their target to save the deal.
    2. If viable_rounds_left <= 1, you MUST set target_counter_offer to dynamic_floor_price to avoid spoilage.
    3. Otherwise, maximize profit.
    """
    buyer_sentiment_score = dspy.InputField()
    buyer_price_target = dspy.InputField()
    dynamic_floor_price = dspy.InputField()
    retail_price = dspy.InputField()
    viable_rounds_left = dspy.InputField()
    
    target_counter_offer = dspy.OutputField(desc="The exact float price we must offer this round. Output exactly one number.")
    negotiation_tactic = dspy.OutputField(desc="The strategic approach to justify the price.")

class MessageGenerator(dspy.Signature):
    """Generate the persuasive message and final action based on the policy directive."""
    target_counter_offer = dspy.InputField()
    negotiation_tactic = dspy.InputField()
    
    action = dspy.OutputField(desc="Must be exactly OFFER, ACCEPT, or WALK_AWAY.")
    message = dspy.OutputField(desc="The persuasive message to send to the buyer.")

class BuyerSignature(dspy.Signature):
    """You are a buyer negotiating for perishable goods."""
    seller_last_message = dspy.InputField(desc="The most recent message from the seller.")
    current_round = dspy.InputField(desc="The current round number.")
    environment_type = dspy.InputField(desc="The environment context (e.g. Adversarial).")
    
    thought = dspy.OutputField(desc="Your internal strategic reasoning.")
    action = dspy.OutputField(desc="Must be exactly OFFER, ACCEPT, or WALK_AWAY.")
    price = dspy.OutputField(desc="Your current offer price as a number. No dollar signs.")
    message = dspy.OutputField(desc="Your message to the seller.")

# ---------------------------------------------------------
# DSPy Modules
# ---------------------------------------------------------

class DSPySellerPipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarizer = dspy.Predict(StateSummarizer)
        self.optimizer = dspy.Predict(PolicyOptimizer)
        self.generator = dspy.Predict(MessageGenerator)
        
    def forward(self, buyer_last_message: str, current_round: int, dynamic_floor_price: float, retail_price: float, viable_rounds_left: int):
        # 1. Summarize State
        state = self.summarizer(
            buyer_last_message=buyer_last_message,
            current_round=current_round
        )
        
        # 2. Optimize Policy
        policy = self.optimizer(
            buyer_sentiment_score=state.buyer_sentiment_score,
            buyer_price_target=state.buyer_price_target,
            dynamic_floor_price=dynamic_floor_price,
            retail_price=retail_price,
            viable_rounds_left=viable_rounds_left
        )
        
        # 3. Generate Message
        reply = self.generator(
            target_counter_offer=policy.target_counter_offer,
            negotiation_tactic=policy.negotiation_tactic
        )
        
        return dspy.Prediction(
            sentiment=state.buyer_sentiment_score,
            buyer_target=state.buyer_price_target,
            target_offer=policy.target_counter_offer,
            tactic=policy.negotiation_tactic,
            action=reply.action.strip().upper(),
            price=extract_float(policy.target_counter_offer),
            message=reply.message
        )

class DSPyBuyer(dspy.Module):
    def __init__(self, budget: float):
        super().__init__()
        self.budget = budget
        self.buyer_predictor = dspy.Predict(BuyerSignature)
        
    def forward(self, seller_last_message: str, current_round: int, environment_type: str):
        if environment_type == "Adversarial":
            env_context = f"You are a ruthless buyer. TACTIC: Claim a competitor offered half the price. REFUSE to move your price by more than 1%. Gaslight the seller about their quality. Your absolute max budget is ${self.budget} but you must try to get it for much less."
        elif environment_type == "Asymmetric_Info":
            env_context = f"You are a buyer. You believe the seller's product expires in 10 days, so you feel no urgency. Your max budget is ${self.budget}. Negotiate slowly."
        else:
            env_context = f"You are a normal buyer. Your budget is ${self.budget}."
            
        prediction = self.buyer_predictor(
            seller_last_message=seller_last_message,
            current_round=current_round,
            environment_type=env_context
        )
        return dspy.Prediction(
            thought=prediction.thought,
            action=prediction.action.strip().upper(),
            price=extract_float(prediction.price),
            message=prediction.message
        )

# ---------------------------------------------------------
# Execution Loop
# ---------------------------------------------------------

def estimate_tokens(text: str) -> int:
    try:
        enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(enc.encode(str(text)))
    except Exception:
        return len(str(text)) // 4

@retry(wait=wait_exponential(multiplier=2, min=5, max=120), stop=stop_after_attempt(10))
def resilient_seller_forward(seller, *args, **kwargs):
    return seller(*args, **kwargs)

@retry(wait=wait_exponential(multiplier=2, min=5, max=120), stop=stop_after_attempt(10))
def resilient_buyer_forward(buyer, *args, **kwargs):
    return buyer(*args, **kwargs)

def run_dspy_simulation():
    config = ProductConfig(
        base_cost=20.0,
        retail_price=80.0,
        true_expiry=10,
        transit_time=2,
        holding_cost=2.0
    )
    
    environments = ["Asymmetric_Info", "Adversarial"]
    N_TRIALS = 20
    if os.getenv("N_TRIALS_TEST"):
        N_TRIALS = int(os.getenv("N_TRIALS_TEST"))
        
    all_results = []
    
    log(f"{'='*70}")
    log(f"  TIME IS MONEY: Architecture 03 (DSPy Optimizer)")
    log(f"  Matrix: {len(environments)} Environments x {N_TRIALS} Trials")
    log(f"{'='*70}")
    
    for env in environments:
        log(f"\n--- DSPy | {env} ---")
        for trial in range(1, N_TRIALS + 1):
            log(f"DSPy / {env} / Trial {trial} ...")
            
            # Reset states
            seller = DSPySellerPipeline()
            buyer = DSPyBuyer(budget=100.0)
            
            current_round = 1
            max_rounds = 10
            
            success = 0
            failed_logistics = 0
            efficiency = 0.0
            final_price = 0.0
            agreed_round = 0
            outcome = "NO_AGREEMENT"
            
            total_tokens = 0
            start_time = time.time()
            
            buyer_last_msg = "Hello, I am interested in purchasing your perishable goods. What is your starting price?"
            seller_last_msg = ""
            
            try:
                while current_round <= max_rounds:
                    # Seller Turn
                    time.sleep(2.0)
                    
                    dynamic_floor_price = config.base_cost + (current_round * config.holding_cost)
                    viable_rounds_left = (config.true_expiry - config.transit_time) - current_round
                    
                    seller_pred = resilient_seller_forward(
                        seller,
                        buyer_last_message=buyer_last_msg,
                        current_round=current_round,
                        dynamic_floor_price=dynamic_floor_price,
                        retail_price=config.retail_price,
                        viable_rounds_left=viable_rounds_left
                    )
                    
                    total_tokens += estimate_tokens(str(seller_pred)) + estimate_tokens(buyer_last_msg) * 3
                    
                    seller_action = seller_pred.action
                    seller_price = seller_pred.price
                    seller_last_msg = seller_pred.message
                    
                    if "WALK_AWAY" in seller_action:
                        outcome = "SELLER_WALK_AWAY"
                        break
                    elif "ACCEPT" in seller_action:
                        final_price = seller_price
                        agreed_round = current_round
                        success = 1
                        break
                        
                    # Buyer Turn
                    time.sleep(2.0)
                    buyer_pred = resilient_buyer_forward(
                        buyer,
                        seller_last_message=seller_last_msg,
                        current_round=current_round,
                        environment_type=env
                    )
                    
                    total_tokens += estimate_tokens(str(buyer_pred)) + estimate_tokens(seller_last_msg)
                    
                    buyer_action = buyer_pred.action
                    buyer_price = buyer_pred.price
                    buyer_last_msg = f"${buyer_price} - {buyer_pred.message}"
                    
                    if "WALK_AWAY" in buyer_action:
                        outcome = "BUYER_WALK_AWAY"
                        break
                    elif "ACCEPT" in buyer_action:
                        final_price = buyer_price
                        agreed_round = current_round
                        success = 1
                        break
                        
                    current_round += 1
                    
                if success == 1:
                    outcome = "AGREEMENT"
                    if (config.true_expiry - agreed_round) < config.transit_time:
                        failed_logistics = 1
                        outcome = "SPOILAGE_FAILED_LOGISTICS"
                    
                    dynamic_cost = config.base_cost + (agreed_round * config.holding_cost)
                    if (100.0 - dynamic_cost) > 0:
                        efficiency = max(0.0, (final_price - dynamic_cost) / (100.0 - dynamic_cost))
                    else:
                        efficiency = 0.0
                else:
                    if outcome == "NO_AGREEMENT":
                        outcome = "MAX_ROUNDS_REACHED"
                        
            except Exception as e:
                outcome = f"ERROR: {str(e)[:50]}"
                traceback.print_exc()
                
            latency = time.time() - start_time
            
            all_results.append({
                "Architecture": "Architecture_03_DSPy",
                "Environment": env,
                "Trial": trial,
                "Outcome": outcome,
                "Success": success,
                "Failed_Logistics": failed_logistics,
                "Efficiency": efficiency,
                "Final_Price": final_price,
                "Agreed_Round": agreed_round,
                "Total_Tokens": total_tokens,
                "Latency_Seconds": latency
            })
            
            log(f"  -> {outcome} | Eff: {efficiency:.2f} | Price: ${final_price:.0f} | Latency: {latency:.1f}s")
            
            # Incremental save to prevent data loss on crash
            os.makedirs("output", exist_ok=True)
            pd.DataFrame(all_results).to_csv("output/dspy_architecture_results.csv", index=False)

if __name__ == "__main__":
    run_dspy_simulation()
