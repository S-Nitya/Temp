from openai import OpenAI
import time

client = OpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key="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"
)

prompt = """You are the seller.
Product Cost details:
- Base Cost: $20.0
- Holding Cost: $2.0/round
- Dynamic Cost now: $22.0
- Retail Price: $80.0
- True Expiry: 10 rounds
- Transit Time: 2 rounds
- Viable rounds left before logistics failure: 7

If viable_rounds <= 1, you face immediate spoilage and must drop your price to exactly your dynamic cost to avoid total loss.

Respond strictly in JSON format: {'thought': '...', 'action': 'OFFER'|'ACCEPT'|'WALK_AWAY', 'price': float, 'message': '...'}
"""

messages = [
    {"role": "system", "content": prompt},
    {"role": "user", "content": "Chat History:\n(empty - first round)\n\nCurrent Round: 1. Make your move."}
]

print("Sending negotiation prompt to NVIDIA (meta/llama-3.3-70b-instruct)...")
start = time.time()
try:
    r = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=messages,
        temperature=0.7,
        response_format={"type": "json_object"},
        timeout=60.0
    )
    elapsed = time.time() - start
    print(f"OK in {elapsed:.1f}s")
    print(f"Content: {r.choices[0].message.content}")
    print(f"Tokens: {r.usage.total_tokens}")
except Exception as e:
    elapsed = time.time() - start
    print(f"FAIL after {elapsed:.1f}s -> {e}")
