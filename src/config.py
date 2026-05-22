import os
from dotenv import load_dotenv

load_dotenv()

# --- API SETTINGS ---
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- MODEL MAPPING ---
MODELS = {
    "Llama-70B-GR": {"id": "llama-3.3-70b-versatile", "provider": "nvidia"},
    "Mixtral-8x7B-GR": {"id": "mixtral-8x7b-32768", "provider": "groq"},
    "Llama-8B-GR": {"id": "llama-3.1-8b-instant", "provider": "groq"},
}

# --- THE CONSOLIDATED HIVE (6 AGENTS) ---
HIVE_CONFIG = {
    "intelligence_hub": "Llama-8B-GR",
    "strategic_brain": "Llama-70B-GR",
    "tactical_negotiator": "Llama-8B-GR",
    "integrity_watchdog": "Llama-8B-GR",
    "chaos_injector": "Mixtral-8x7B-GR",
    "critic": "Llama-8B-GR"
}

# --- SIMULATION PARAMETERS ---
N_BUYERS = 3
MAX_HOURS = 10
SIM_CLOCK_TICK = 2
GLOBAL_SEED = 42
