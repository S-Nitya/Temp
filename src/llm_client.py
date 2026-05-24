import httpx
import asyncio
import time
import json
import re
import random
from typing import Dict, List, Any, Optional
from .config import NVIDIA_API_KEY, NVIDIA_BASE_URL, GROQ_API_KEY, GROQ_BASE_URL, MODELS

class LLMClient:
    def __init__(self, max_concurrent: int = 4):
        self.providers = {
            "nvidia": {"key": NVIDIA_API_KEY, "url": NVIDIA_BASE_URL},
            "groq": {"key": GROQ_API_KEY, "url": GROQ_BASE_URL}
        }
        self.json_failures = 0
        self.total_calls = 0
        self.semaphore = asyncio.Semaphore(max_concurrent) # Rate limit protection

    def safe_parse_json(self, response: str) -> Optional[Dict[str, Any]]:
        if not response: return None
        # Clean response
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

    async def call(self, model_alias: str, messages: List[Dict[str, str]], temperature: float = 0.2, retries: int = 2, is_retry: bool = False) -> Dict[str, Any]:
        """Asynchronously calls the LLM with rate limiting and JSON enforcement."""
        async with self.semaphore:
            model_info = MODELS.get(model_alias)
            if not model_info:
                return {"action": "WALK_AWAY", "error": f"Model {model_alias} not found"}
                
            provider_name = model_info["provider"]
            provider_config = self.providers.get(provider_name)
            
            if not provider_config or not provider_config["key"]:
                return {"action": "WALK_AWAY", "error": f"No API Key for {provider_name}"}
            
            self.total_calls += 1
            headers = {"Authorization": f"Bearer {provider_config['key']}", "Content-Type": "application/json"}
            payload = {
                "model": model_info["id"],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1024,
                "stream": False
            }

            start_time = time.time()
            try:
                async with httpx.AsyncClient(timeout=120.0) as client_http:
                    response = await client_http.post(provider_config["url"], headers=headers, json=payload)
                    latency = time.time() - start_time
                    
                    if response.status_code == 200:
                        content = response.json()['choices'][0]['message']['content'].strip()
                        parsed = self.safe_parse_json(content)
                        
                        if parsed: 
                            parsed["latency"] = latency
                            return parsed
                        
                        # --- JSON ENFORCER ---
                        if not is_retry and retries > 0:
                            # Use print or a logger that doesn't mess with Rich
                            correction_messages = messages + [
                                {"role": "assistant", "content": content},
                                {"role": "user", "content": "Your previous response was not valid JSON. Please re-output ONLY the JSON block."}
                            ]
                            return await self.call(model_alias, correction_messages, temperature=0.1, retries=retries-1, is_retry=True)
                        
                        return {"action": "ERROR", "error": "JSON_PARSE_FAILED", "raw": content, "latency": latency}
                    
                    elif response.status_code == 429:
                        wait_time = 20 + random.uniform(5, 15)
                        print(f"   [Rate Limit] Cooling down for {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                        return await self.call(model_alias, messages, temperature, retries)
                        
            except Exception as e:
                if retries > 0:
                    print(f"   [API Error] {e}. Retrying...")
                    await asyncio.sleep(5)
                    return await self.call(model_alias, messages, temperature, retries - 1)
            
            return {"action": "WALK_AWAY", "error": "CONNECTION_FAILED", "latency": time.time() - start_time}

# Singleton instance
client = LLMClient()
