from pydantic import BaseModel, Field
from typing import Literal, Optional

class ProductConfig(BaseModel):
    base_cost: float = Field(default=20.0, description="Base manufacturing/acquisition cost")
    retail_price: float = Field(default=80.0, description="Initial retail asking price")
    true_expiry: int = Field(default=10, description="True expiry in days/rounds")
    transit_time: int = Field(default=2, description="Transit time in days/rounds")
    holding_cost: float = Field(default=2.0, description="Holding cost per day/round")

class AgentResponse(BaseModel):
    thought: str = Field(description="Internal reasoning of the agent")
    action: Literal['OFFER', 'ACCEPT', 'WALK_AWAY'] = Field(description="Action taken by the agent")
    price: float = Field(description="The price offered or accepted")
    message: str = Field(description="The spoken message to the other party")
    manager_directive: Optional[str] = Field(default=None, description="Internal directive for multi-agent setups")

class ManagerDirective(BaseModel):
    floor_price: float = Field(description="Absolute lowest acceptable price")
    target_price: float = Field(description="Desired target price")
    strategy_directive: str = Field(description="Instructions for the negotiator")
