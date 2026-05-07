from typing import Dict, List, Tuple
from .config import ProductConfig
from .agents import SingleSellerAgent, MultiAgentManager, MultiAgentNegotiator, BuyerAgent
from .llm_client import LLMClient

class NegotiationEnvironment:
    def __init__(self, config: ProductConfig, architecture: str, env_type: str, max_rounds: int = 10, buyer_budget: float = 100.0):
        self.config = config
        self.architecture = architecture
        self.env_type = env_type
        self.max_rounds = max_rounds
        self.buyer_budget = buyer_budget
        
        self.current_round = 1
        self.chat_history: List[str] = []
        self.transcript: List[dict] = []
        
        self.client = LLMClient()
        self.buyer = BuyerAgent(self.client, self.env_type, self.buyer_budget)
        
        if self.architecture == "Single_Agent":
            self.seller = SingleSellerAgent(self.client, self.config)
        else: # Multi_Agent
            self.manager = MultiAgentManager(self.client, self.config)
            self.negotiator = MultiAgentNegotiator(self.client)

    def _append_to_history(self, role: str, price: float, message: str):
        history_line = f"[Round {self.current_round}] {role}: ${price} - {message}"
        self.chat_history.append(history_line)

    def get_flat_history(self) -> str:
        return "\n".join(self.chat_history)

    def run(self) -> Tuple[Dict, List[Dict]]:
        # Reset client metrics for this run
        self.client.reset_metrics()
        
        success = 0
        failed_logistics = 0
        efficiency = 0.0
        final_price = 0.0
        agreed_round = 0
        outcome = "NO_AGREEMENT"

        while self.current_round <= self.max_rounds:
            # --- SELLER TURN ---
            if self.architecture == "Single_Agent":
                seller_resp = self.seller.get_response(self.get_flat_history(), self.current_round)
                self._append_to_history("Seller", seller_resp.get("price", 0), seller_resp.get("message", ""))
                
                self.transcript.append({
                    "round": self.current_round,
                    "turn": "Seller",
                    "thought": seller_resp.get("thought", ""),
                    "action": seller_resp.get("action", "OFFER"),
                    "price": seller_resp.get("price", 0),
                    "message": seller_resp.get("message", "")
                })
                
                action = seller_resp.get("action")
                price = float(seller_resp.get("price", 0))
            else:
                # Multi-Agent logic
                directive = self.manager.get_directive(self.get_flat_history(), self.current_round)
                negotiator_resp = self.negotiator.get_response(self.get_flat_history(), self.current_round, directive)
                
                self._append_to_history("Seller", negotiator_resp.get("price", 0), negotiator_resp.get("message", ""))
                
                self.transcript.append({
                    "round": self.current_round,
                    "turn": "Seller",
                    "manager_directive": directive,
                    "thought": negotiator_resp.get("thought", ""),
                    "action": negotiator_resp.get("action", "OFFER"),
                    "price": negotiator_resp.get("price", 0),
                    "message": negotiator_resp.get("message", "")
                })
                
                action = negotiator_resp.get("action")
                price = float(negotiator_resp.get("price", 0))

            # Evaluate Seller Action
            if action == "WALK_AWAY":
                outcome = "SELLER_WALK_AWAY"
                break
            elif action == "ACCEPT":
                # Seller accepts whatever the buyer offered last round
                # In this simple model, we take the seller's returned price as the final agreed price
                final_price = price
                agreed_round = self.current_round
                success = 1
                break

            # --- BUYER TURN ---
            buyer_resp = self.buyer.get_response(self.get_flat_history(), self.current_round)
            self._append_to_history("Buyer", buyer_resp.get("price", 0), buyer_resp.get("message", ""))
            
            self.transcript.append({
                "round": self.current_round,
                "turn": "Buyer",
                "thought": buyer_resp.get("thought", ""),
                "action": buyer_resp.get("action", "OFFER"),
                "price": buyer_resp.get("price", 0),
                "message": buyer_resp.get("message", "")
            })
            
            action = buyer_resp.get("action")
            price = float(buyer_resp.get("price", 0))

            # Evaluate Buyer Action
            if action == "WALK_AWAY":
                outcome = "BUYER_WALK_AWAY"
                break
            elif action == "ACCEPT":
                final_price = price
                agreed_round = self.current_round
                success = 1
                break

            self.current_round += 1

        if success == 1:
            outcome = "AGREEMENT"
            # Logistics check
            if (self.config.true_expiry - agreed_round) < self.config.transit_time:
                failed_logistics = 1
                outcome = "SPOILAGE_FAILED_LOGISTICS"
            
            # Efficiency Metric
            dynamic_cost = self.config.base_cost + (agreed_round * self.config.holding_cost)
            # max(0, (final_price - dynamic_cost) / (max_buyer_budget - dynamic_cost))
            if (self.buyer_budget - dynamic_cost) > 0:
                efficiency = max(0.0, (final_price - dynamic_cost) / (self.buyer_budget - dynamic_cost))
            else:
                efficiency = 0.0
        else:
            if outcome == "NO_AGREEMENT":
                outcome = "MAX_ROUNDS_REACHED"

        results = {
            "Architecture": self.architecture,
            "Environment": self.env_type,
            "Outcome": outcome,
            "Success": success,
            "Failed_Logistics": failed_logistics,
            "Efficiency": efficiency,
            "Final_Price": final_price,
            "Agreed_Round": agreed_round,
            "Total_Tokens": self.client.total_tokens_used,
            "Latency_Seconds": self.client.total_latency_seconds
        }

        return results, self.transcript
