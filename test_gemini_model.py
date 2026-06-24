import asyncio
import os
from kanishka_src.llm_client import client
from kanishka_src.config import MODELS
from google import genai

async def test_model():
    print("Testing standard gemini-3.1-pro-preview...")
    MODELS["Test-Model"] = {"id": "gemini-3.1-pro-preview", "provider": "google"}
    
    res = await client.call("Test-Model", [{"role": "user", "content": "Return exactly: {'action': 'SUCCESS'}"}], retries=1)
    print(f"Result for gemini-3.1-pro-preview: {res}")
    print(f"Status Logs: {client.status_logs}")

if __name__ == "__main__":
    asyncio.run(test_model())
