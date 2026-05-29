import httpx
import asyncio
import time
import json
import re
import random
from typing import Dict, List, Any, Optional
from .config import NVIDIA_API_KEYS, NVIDIA_BASE_URL, GROQ_API_KEYS, GROQ_BASE_URL, MODELS

class LLMClient:
    def __init__(self, max_concurrent: int = 4):
        self.providers = {
            "nvidia": {"keys": NVIDIA_API_KEYS, "url": NVIDIA_BASE_URL, "index": 0},
            "groq": {"keys": GROQ_API_KEYS, "url": GROQ_BASE_URL, "index": 0}
        }
        self.json_failures = 0
        self.total_calls = 0
        self.status_logs = []
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._http_client = None

    async def get_http_client(self):
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    def _log_status(self, msg: str):
        self.status_logs.append(f"[LLM] {msg}")
        if len(self.status_logs) > 20: self.status_logs.pop(0)

    def _get_next_key(self, provider_name: str) -> Optional[str]:
        p = self.providers.get(provider_name)
        if not p or not p["keys"]: return None
        key = p["keys"][p["index"]]
        p["index"] = (p["index"] + 1) % len(p["keys"])
        return key

    def safe_parse_json(self, response: str) -> Optional[Dict[str, Any]]:
        if not response: return None
        response = re.sub(r'<thought>.*?</thought>', '', response, flags=re.DOTALL)
        response = re.sub(r'```json\s*(.*?)\s*```', r'\1', response, flags=re.DOTALL)
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except: pass
        self.json_failures += 1
        return None

    async def call(self, model_alias: str, messages: List[Dict[str, str]], temperature: float = 0.2, retries: int = 5) -> Dict[str, Any]:
        """Semaphore-protected entry point."""
        async with self.semaphore:
            return await self._internal_call(model_alias, messages, temperature, retries)

    async def _internal_call(self, model_alias: str, messages: List[Dict[str, str]], temperature: float = 0.2, retries: int = 5, is_retry: bool = False) -> Dict[str, Any]:
        """Actual call logic, can be called recursively without re-acquiring semaphore."""
        model_info = MODELS.get(model_alias)
        if not model_info:
            return {"action": "WALK_AWAY", "error": f"Model {model_alias} not found"}
            
        provider_name = model_info["provider"]
        api_key = self._get_next_key(provider_name)
        provider_config = self.providers.get(provider_name)
        
        if not api_key:
            return {"action": "WALK_AWAY", "error": f"No API Key for {provider_name}"}
        
        self.total_calls += 1
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model_info["id"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
            "stream": False
        }

        start_time = time.time()
        try:
            http_client = await self.get_http_client()
            response = await http_client.post(provider_config["url"], headers=headers, json=payload)
            latency = time.time() - start_time
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content'].strip()
                parsed = self.safe_parse_json(content)
                
                if parsed: 
                    parsed["latency"] = latency
                    return parsed
                
                if not is_retry and retries > 0:
                    self._log_status("JSON parse failed, retrying...")
                    correction_messages = messages + [
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": "Your previous response was not valid JSON. Please re-output ONLY the JSON block."}
                    ]
                    return await self._internal_call(model_alias, correction_messages, temperature=0.1, retries=retries-1, is_retry=True)
                
                return {"action": "ERROR", "error": "JSON_PARSE_FAILED", "raw": content, "latency": latency}
            
            elif response.status_code == 429:
                num_keys = len(self.providers[provider_name]["keys"])
                wait_time = 12 + random.uniform(2, 5)
                
                if num_keys > 1 and retries > 0:
                    self._log_status(f"Rate limited. Switching key (Retries left: {retries})...")
                    await asyncio.sleep(3) # Slightly longer delay
                    return await self._internal_call(model_alias, messages, temperature, retries - 1)
                else:
                    self._log_status(f"Rate limited. Waiting {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    if retries > 0:
                        return await self._internal_call(model_alias, messages, temperature, retries - 1)
            
            else:
                err_msg = response.text[:100]
                self._log_status(f"Error {response.status_code} on {model_info['id']} ({provider_name}): {err_msg}")
                
        except Exception as e:
            if retries > 0:
                self._log_status(f"Conn Error: {provider_name} ({str(e)[:20]}...)")
                await asyncio.sleep(3)
                return await self._internal_call(model_alias, messages, temperature, retries - 1)
        
        return {"action": "WALK_AWAY", "error": "CONNECTION_FAILED", "latency": time.time() - start_time}

# Singleton instance
client = LLMClient()
