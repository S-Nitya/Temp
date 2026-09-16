"""
Asynchronous LLM Client with exact API token usage tracking, key rotation, and exponential backoff.
"""
import os
import time
import json
import re
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Load API keys
NVIDIA_API_KEYS = [k.strip() for k in os.getenv("NVIDIA_API_KEYS", "").split(",") if k.strip()]
if not NVIDIA_API_KEYS and os.getenv("NVIDIA_API_KEY"):
    NVIDIA_API_KEYS = [os.getenv("NVIDIA_API_KEY")]

GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
if not GROQ_API_KEYS and os.getenv("GROQ_API_KEY"):
    GROQ_API_KEYS = [os.getenv("GROQ_API_KEY")]

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

MODEL_REGISTRY = {
    "StrategicBrain": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-120b",
    },
    "BullDebater": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-20b",
    },
    "BearDebater": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-20b",
    },
    "DebateJudge": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-20b",
    },
    "RiskReader": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-20b",
    },
    "ListingDecider": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-20b",
    },
    "Spokesperson": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-20b",
    },
    "Buyer": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-20b",
    },
}


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0


class CallRecord(BaseModel):
    trial_id: int
    item_id: str
    agent_name: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_seconds: float
    raw_prompt: str = ""
    raw_response: str = ""


class LLMClient:
    def __init__(self, max_concurrent: int = 2):
        self.providers = {
            "nvidia": {"keys": NVIDIA_API_KEYS, "url": NVIDIA_BASE_URL, "index": 0},
            "groq":   {"keys": GROQ_API_KEYS,   "url": GROQ_BASE_URL,   "index": 0},
        }
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.call_records: List[CallRecord] = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

    def _get_next_key(self, provider_name: str) -> Optional[str]:
        prov = self.providers.get(provider_name)
        if not prov or not prov["keys"]:
            return None
        key = prov["keys"][prov["index"] % len(prov["keys"])]
        prov["index"] += 1
        return key

    @staticmethod
    def safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        text = text.strip()
        # Direct parse
        try:
            return json.loads(text)
        except Exception:
            pass
        # Markdown fence extraction
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                pass
        # Bracket hunting
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return None

    async def call_agent(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        trial_id: int = 1,
        item_id: str = "general",
        temperature: float = 0.2,
        retries: int = 8,
    ) -> Dict[str, Any]:
        """Execute structured LLM call with exact token logging and retry handling."""
        cfg = MODEL_REGISTRY.get(agent_name, {"provider": "groq", "model_id": "openai/gpt-oss-20b"})
        provider_name = cfg["provider"]
        model_id = cfg["model_id"]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw_prompt_text = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"

        async with self.semaphore:
            for attempt in range(retries):
                api_key = self._get_next_key(provider_name)
                prov_cfg = self.providers.get(provider_name)
                if not api_key or not prov_cfg:
                    alt_provider = "groq"
                    api_key = self._get_next_key(alt_provider)
                    if not api_key:
                        return {"error": "NO_API_KEY", "action": "API_ERROR"}
                    prov_cfg = self.providers[alt_provider]
                    provider_name = alt_provider
                    model_id = "openai/gpt-oss-20b"

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model_id,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 1024,
                    "stream": False,
                }

                start_t = time.time()
                try:
                    async with httpx.AsyncClient(timeout=45.0) as http:
                        resp = await http.post(prov_cfg["url"], headers=headers, json=payload)
                    latency = round(time.time() - start_t, 3)

                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"].strip()
                        usage = data.get("usage", {})
                        p_tok = usage.get("prompt_tokens", len(raw_prompt_text) // 4)
                        c_tok = usage.get("completion_tokens", len(content) // 4)
                        t_tok = usage.get("total_tokens", p_tok + c_tok)

                        record = CallRecord(
                            trial_id=trial_id,
                            item_id=item_id,
                            agent_name=agent_name,
                            model_name=model_id,
                            prompt_tokens=p_tok,
                            completion_tokens=c_tok,
                            total_tokens=t_tok,
                            latency_seconds=latency,
                            raw_prompt=raw_prompt_text,
                            raw_response=content,
                        )
                        self.call_records.append(record)
                        self.total_prompt_tokens += p_tok
                        self.total_completion_tokens += c_tok
                        self.total_tokens += t_tok

                        parsed = self.safe_parse_json(content)
                        # Pacing delay to respect RPM/TPM limits
                        await asyncio.sleep(0.35)

                        if parsed is not None:
                            parsed["_token_usage"] = {
                                "prompt_tokens": p_tok,
                                "completion_tokens": c_tok,
                                "total_tokens": t_tok,
                                "latency_seconds": latency,
                            }
                            return parsed

                        # JSON parse retry
                        if attempt < retries - 1:
                            messages.append({"role": "assistant", "content": content})
                            messages.append({"role": "user", "content": "Return ONLY valid JSON matching the schema."})
                            continue
                        return {"error": "JSON_PARSE_FAILED", "raw": content[:200], "action": "API_ERROR"}

                    elif resp.status_code == 429:
                        retry_after_hdr = resp.headers.get("retry-after")
                        if retry_after_hdr:
                            try:
                                wait = float(retry_after_hdr) + 1.5
                            except ValueError:
                                wait = min(35.0, (2 ** attempt) * 2.0 + 3.0)
                        else:
                            wait = min(35.0, (2 ** attempt) * 2.0 + 3.0)
                        print(f" [RATE LIMIT 429] Waiting {wait:.1f}s before retry (attempt {attempt+1}/{retries})...", flush=True)
                        await asyncio.sleep(wait)
                        continue
                    else:
                        if attempt < retries - 1:
                            await asyncio.sleep(1.5)
                            continue
                        return {"error": f"HTTP_{resp.status_code}", "action": "API_ERROR"}

                except Exception as e:
                    if attempt < retries - 1:
                        await asyncio.sleep(2.0)
                        continue
                    return {"error": str(e), "action": "API_ERROR"}

            return {"error": "RETRIES_EXHAUSTED", "action": "API_ERROR"}
