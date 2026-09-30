import os
from dotenv import load_dotenv

load_dotenv()

# --- API SETTINGS ---
NVIDIA_API_KEYS = [os.getenv("NVIDIA_API_KEY"), os.getenv("NVIDIA_API_KEY_2")]
NVIDIA_API_KEYS = [k for k in NVIDIA_API_KEYS if k] # Filter out None
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

GROQ_API_KEYS = [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY_2")]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k] # Filter out None
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- MODEL MAPPING ---
MODELS = {
    "Llama-70B-NV": {"id": "meta/llama-3.3-70b-instruct", "provider": "nvidia"},
    "Llama-70B-GR": {"id": "llama-3.3-70b-versatile", "provider": "groq"},
    "Mixtral-8x7B-GR": {"id": "mixtral-8x7b-32768", "provider": "groq"},
    "Llama-8B-GR": {"id": "llama-3.1-8b-instant", "provider": "groq"},
    "Gemini-2.5-Flash": {"id": "gemini-2.5-flash", "provider": "google"},
    "Gemini-3.5-Flash": {"id": "gemini-3.5-flash", "provider": "google"},
    "Gemini-3.1-Pro": {"id": "gemini-3.1-pro-preview", "provider": "google"}
}

# --- THE CONSOLIDATED HIVE (6 AGENTS) ---
HIVE_CONFIG = {
    "intelligence_hub": "Llama-8B-GR",
    "strategic_brain": "Llama-70B-NV",
    "tactical_negotiator": "Llama-8B-GR",
    "integrity_watchdog": "Llama-8B-GR",
    "chaos_injector": "Llama-70B-NV", # Switched to Llama-70B
    "critic": "Llama-8B-GR"
}

# --- SIMULATION PARAMETERS ---
N_BUYERS = 15
MAX_HOURS = 10
SIM_CLOCK_TICK = 2
GLOBAL_SEED = 42
