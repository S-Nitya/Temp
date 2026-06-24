import asyncio
import os
import sys
sys.path.append(os.getcwd())

from kanishka_src.llm_client import client

async def test():
    print("Testing Gemini-2.5-Flash...")
    res_flash25 = await client.call("Gemini-2.5-Flash", [{"role": "user", "content": "Return exactly: {'action': 'SUCCESS'}"}], retries=1)
    print(f"Result 2.5 Flash: {res_flash25}")
    
    print("\nTesting Gemini-3.5-Flash...")
    res_flash35 = await client.call("Gemini-3.5-Flash", [{"role": "user", "content": "Return exactly: {'action': 'SUCCESS'}"}], retries=1)
    print(f"Result 3.5 Flash: {res_flash35}")
    
    print(f"\nStatus Logs: {client.status_logs}")

if __name__ == "__main__":
    asyncio.run(test())
