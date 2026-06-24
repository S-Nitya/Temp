import asyncio
import os
import sys
# Add workspace root to python path to import kanishka_src
sys.path.append(os.getcwd())

from kanishka_src.llm_client import client

async def test():
    print("Testing Llama-70B-GR (Groq)...")
    res_gr = await client.call("Llama-70B-GR", [{"role": "user", "content": "Return exactly: {'action': 'SUCCESS'}"}], retries=1)
    print(f"Result Groq: {res_gr}")
    
    print("\nTesting Llama-70B-NV (NVIDIA)...")
    res_nv = await client.call("Llama-70B-NV", [{"role": "user", "content": "Return exactly: {'action': 'SUCCESS'}"}], retries=1)
    print(f"Result NVIDIA: {res_nv}")
    
    print(f"\nStatus Logs: {client.status_logs}")

if __name__ == "__main__":
    asyncio.run(test())
