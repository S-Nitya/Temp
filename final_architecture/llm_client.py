"""
LLM Client with:
- Pydantic schema validation on all agent outputs
- Hard 90s timeout guard
- Key rotation + exponential backoff on 429
- Transient httpx clients (no connection reuse bugs)
"""
import httpx
import asyncio
import time
import json
import re
import random
import os
from typing import Dict, List, Any, Optional, Type, TypeVar
from pydantic import BaseModel, Field, field_validator, model_validator
from .config import NVIDIA_API_KEYS, NVIDIA_BASE_URL, GROQ_API_KEYS, GROQ_BASE_URL, MODELS

T = TypeVar("T", bound=BaseModel)

# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class StrategicDecision(BaseModel):
    market_analysis: str = Field(default="", description="Analyze time remaining, inventory levels, and spoilage risk.")
    chosen_strategy: str = Field(default="", description="Declare the current pricing strategy (e.g., margin defense, aggressive clearance).")
    quotes: Dict[str, float] = Field(default_factory=dict, description="The starting ask price per product.")
    floor_prices: Dict[str, float] = Field(default_factory=dict, description="The absolute minimum acceptable price per product.")
    priority_items: List[str] = Field(default_factory=list, description="Items most at risk of expiring unsold.")


class DeciderAction(BaseModel):
    risk_evaluation: str = Field(default="", description="Evaluate the RiskReader's bluff and walk-away scores against current TTE and inventory.")
    action: str = Field(default="HOLD", description="The chosen tactical action (HOLD, CONCEDE, ACCEPT).")
    target_price: float = Field(default=0.0, description="The price to counter with, if applicable.")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        v_upper = str(v).upper().strip()
        return v_upper if v_upper in ("HOLD", "CONCEDE", "ACCEPT") else "HOLD"

    @field_validator("target_price", mode="before")
    @classmethod
    def coerce_float(cls, v):
        try: return float(v)
        except: return 0.0


class BuyerResponse(BaseModel):
    internal_monologue: str = Field(default="", description="Evaluate the seller's argument. Update your perceived value and urgency based on their text and your remaining time. DO NOT exceed your max budget.")
    action: str = Field(default="COUNTER", description="ACCEPT, COUNTER, WALK_AWAY")
    bid_amount: float = Field(default=0.0, description="Your counter-offer, or 0 if walking away.")
    dialogue: str = Field(default="", description="Your natural language response to the seller.")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        v_upper = str(v).upper().strip()
        return v_upper if v_upper in ("ACCEPT", "COUNTER", "WALK_AWAY") else "COUNTER"

    @field_validator("bid_amount", mode="before")
    @classmethod
    def coerce_float(cls, v):
        try: return float(v)
        except: return 0.0


class RiskProfileSchema(BaseModel):
    buyer_profile: str = "Unknown"
    tactic_detected: str = "Unknown"
    bluffing_probability: int = 5
    walk_away_probability: int = 5
    recommended_stance: str = "Proceed with caution."

    @field_validator("bluffing_probability", "walk_away_probability", mode="before")
    @classmethod
    def clamp(cls, v):
        try: return max(0, min(10, int(v)))
        except: return 5


class SpokespersonSchema(BaseModel):
    thought: str = ""
    action: str = "COUNTER"
    new_quote: float = 0.0
    message: str = ""

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        return v if v in ("ACCEPT", "COUNTER", "WALK_AWAY") else "COUNTER"

    @field_validator("new_quote", mode="before")
    @classmethod
    def coerce_float(cls, v):
        try: return float(v)
        except: return 0.0


# Backward compatibility aliases
BuyerActionSchema = BuyerResponse
DecisionSchema = DeciderAction


# ─── LLM Client ──────────────────────────────────────────────────────────────

def validate_output(data: Optional[Dict], schema_class: Type[T]) -> Optional[T]:
    """Validate a parsed dict against a Pydantic schema. Returns None on failure."""
    if not data:
        return None
    try:
        return schema_class(**data)
    except Exception:
        # Try partial construction with field-by-field fallback
        try:
            filtered = {k: v for k, v in data.items()
                        if k in schema_class.model_fields}
            return schema_class(**filtered)
        except Exception:
            return None


class LLMClient:
    def __init__(self, max_concurrent: int = 4):
        self.providers = {
            "nvidia": {"keys": NVIDIA_API_KEYS, "url": NVIDIA_BASE_URL, "index": 0},
            "groq":   {"keys": GROQ_API_KEYS,   "url": GROQ_BASE_URL,   "index": 0},
        }
        self.json_failures = 0
        self.total_calls   = 0
        self.status_logs   = []
        self.semaphore     = asyncio.Semaphore(max_concurrent)

    def _log(self, msg: str):
        self.status_logs.append(f"[LLM] {msg}")
        if len(self.status_logs) > 30:
            self.status_logs.pop(0)

    def _get_next_key(self, provider_name: str) -> Optional[str]:
        p = self.providers.get(provider_name)
        if not p or not p["keys"]:
            return None
        key = p["keys"][p["index"]]
        p["index"] = (p["index"] + 1) % len(p["keys"])
        return key

    def safe_parse_json(self, response: str) -> Optional[Dict[str, Any]]:
        if not response:
            return None
        response = re.sub(r"<thought>.*?</thought>", "", response, flags=re.DOTALL)
        response = re.sub(r"```json\s*(.*?)\s*```", r"\1", response, flags=re.DOTALL)
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
        self.json_failures += 1
        return None

    async def call(
        self,
        model_alias: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """Semaphore-protected entry with hard 90s timeout."""
        async with self.semaphore:
            try:
                return await asyncio.wait_for(
                    self._internal_call(model_alias, messages, temperature, retries),
                    timeout=90.0,
                )
            except asyncio.TimeoutError:
                self._log(f"HARD TIMEOUT (90s) on {model_alias}")
                return {"action": "WALK_AWAY", "error": "HARD_TIMEOUT"}

    async def _internal_call(
        self,
        model_alias: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        retries: int = 3,
        is_retry: bool = False,
    ) -> Dict[str, Any]:
        model_info = MODELS.get(model_alias)
        if not model_info:
            return {"action": "WALK_AWAY", "error": f"Model {model_alias} not found"}

        provider_name = model_info["provider"]
        api_key       = self._get_next_key(provider_name)
        provider_cfg  = self.providers.get(provider_name)

        if not api_key:
            return {"action": "WALK_AWAY", "error": f"No API key for {provider_name}"}

        self.total_calls += 1
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model":       model_info["id"],
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  1024,
            "stream":      False,
        }

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.post(provider_cfg["url"], headers=headers, json=payload)
            latency = time.time() - start

            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                parsed  = self.safe_parse_json(content)
                if parsed:
                    parsed["latency"] = latency
                    return parsed
                # JSON parse failed — retry with correction prompt
                if not is_retry and retries > 0:
                    self._log("JSON parse failed — asking model to re-output JSON only")
                    correction = messages + [
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": "Your response was not valid JSON. Re-output ONLY the JSON object, nothing else."},
                    ]
                    return await self._internal_call(model_alias, correction, 0.1, retries - 1, is_retry=True)
                return {"action": "ERROR", "error": "JSON_PARSE_FAILED", "raw": content[:200], "latency": latency}

            elif resp.status_code == 429:
                wait = 10 + random.uniform(2, 5)
                if len(self.providers[provider_name]["keys"]) > 1 and retries > 0:
                    self._log(f"Rate limited — rotating key (retries left: {retries})")
                    await asyncio.sleep(3)
                    return await self._internal_call(model_alias, messages, temperature, retries - 1)
                else:
                    self._log(f"Rate limited — waiting {wait:.1f}s")
                    await asyncio.sleep(wait)
                    if retries > 0:
                        return await self._internal_call(model_alias, messages, temperature, retries - 1)

            else:
                self._log(f"HTTP {resp.status_code} on {model_alias}: {resp.text[:80]}")

        except Exception as e:
            if retries > 0:
                self._log(f"Connection error ({str(e)[:30]}) — retrying")
                await asyncio.sleep(3)
                return await self._internal_call(model_alias, messages, temperature, retries - 1)

        return {"action": "WALK_AWAY", "error": "CONNECTION_FAILED", "latency": time.time() - start}


# Singleton
client = LLMClient()
