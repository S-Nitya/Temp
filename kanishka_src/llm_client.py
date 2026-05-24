import os
import sys
import time
import json
import re
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from dotenv import load_dotenv

load_dotenv()

class JSONDecodeErrorCustom(Exception):
    pass

def log(msg):
    print(msg, flush=True)

class LLMClient:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
        
        if self.provider == "nvidia":
            api_key = os.getenv("NVIDIA_API_KEY")
            base_url = "https://integrate.api.nvidia.com/v1"
            self.default_model = "meta/llama-3.3-70b-instruct"
        elif self.provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            base_url = "https://api.groq.com/openai/v1"
            self.default_model = "llama-3.3-70b-versatile"
        else: # default to openrouter
            api_key = os.getenv("OPENROUTER_API_KEY")
            base_url = "https://openrouter.ai/api/v1"
            self.default_model = "qwen/qwen-2.5-72b-instruct"
            
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self.total_tokens_used = 0
        self.total_latency_seconds = 0.0

    def reset_metrics(self):
        self.total_tokens_used = 0
        self.total_latency_seconds = 0.0

    @retry(
        wait=wait_exponential(multiplier=2, min=5, max=300),
        stop=stop_after_attempt(15),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError, InternalServerError, JSONDecodeErrorCustom))
    )
    def generate_json(self, messages, model=None):
        model_to_use = model or self.default_model
        
        # Mandatory sleep to prevent rate limits
        time.sleep(2.0)
        
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"},
                timeout=60.0
            )
        except RateLimitError as e:
            # Parse retry-after from error message if available
            err_msg = str(e)
            log(f"  [RATE LIMITED] Waiting for cooldown... ({err_msg[:80]})")
            time.sleep(30)  # Extra 30s cooldown on top of tenacity backoff
            raise e
        except Exception as e:
            log(f"  [API ERROR] {str(e)[:100]}")
            raise e
            
        latency = time.time() - start_time
        self.total_latency_seconds += latency
        
        if response.usage:
            self.total_tokens_used += response.usage.total_tokens
            
        content = response.choices[0].message.content
        return self._parse_json(content)

    def _parse_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback regex extraction to handle markdown wrappers like ```json ... ```
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError as e:
                    raise JSONDecodeErrorCustom(f"Failed to parse extracted JSON: {e}")
            raise JSONDecodeErrorCustom("No JSON object found in response.")
