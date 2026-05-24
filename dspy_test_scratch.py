import dspy
import os
from dotenv import load_dotenv

load_dotenv()

print(f"Key loaded: {bool(os.getenv('OPENROUTER_API_KEY'))}")

try:
    lm = dspy.LM(
        model="openrouter/meta-llama/llama-3.3-70b-instruct",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        max_tokens=100
    )
    dspy.configure(lm=lm)
    
    response = lm("Hello, what is 2+2? Reply with just the number.")
    print(f"Success! Response: {response}")
except Exception as e:
    print(f"Failed openrouter: {e}")

try:
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENROUTER_API_KEY", "")
    lm2 = dspy.LM(
        model="openai/meta-llama/llama-3.3-70b-instruct",
        api_base="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        max_tokens=100
    )
    dspy.configure(lm=lm2)
    
    response2 = lm2("Hello, what is 2+2? Reply with just the number.")
    print(f"Success! Response2: {response2}")
except Exception as e:
    print(f"Failed openai base: {e}")
