import os
from dotenv import load_dotenv

load_dotenv()

# --- API SETTINGS ---
NVIDIA_API_KEYS = [os.getenv("NVIDIA_API_KEY"), os.getenv("NVIDIA_API_KEY_2")]
NVIDIA_API_KEYS = [k for k in NVIDIA_API_KEYS if k]
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

GROQ_API_KEYS = [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY_2")]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k]
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- MODEL MAPPING ---
# Open-weight models only — required for NeurIPS reproducibility
MODELS = {
    "Llama-70B-NV": {"id": "meta/llama-3.3-70b-instruct", "provider": "nvidia"},
    "Llama-8B-NV":  {"id": "meta/llama-3.1-8b-instruct",  "provider": "nvidia"},
    "Llama-70B-GR": {"id": "llama-3.3-70b-versatile",     "provider": "groq"},
    "Llama-8B-GR":  {"id": "llama-3.1-8b-instant",        "provider": "groq"},
    "Mixtral-8x7B-GR": {"id": "mixtral-8x7b-32768",       "provider": "groq"},
}

# --- NEURIPS ARCHITECTURE CONFIG ---
# StrategicBrain uses 70B for autonomous strategy discovery
# Micro-negotiation agents use 8B for speed/cost
NEURIPS_CONFIG = {
    "strategic_brain":    "Llama-70B-NV",
    "tactical_negotiator": "Llama-8B-NV",
    "chaos_injector":     "Llama-70B-NV",
}

# --- SIMULATION PARAMETERS ---
N_BUYERS     = 15
MAX_HOURS    = 10
SIM_CLOCK_TICK = 2
GLOBAL_SEED  = 42

# --- PERSUASION MULTIPLIERS (fixed, defensible OR math) ---
# Applied to buyer's base max_acceptable ceiling when seller uses specific tactics
# Source: Cialdini's Influence principles adapted to perishable goods context
TACTIC_MULTIPLIERS = {
    "scarcity":          1.08,  # "only 2 left", "expires tomorrow" → 8% ceiling expansion
    "quality_assurance": 1.05,  # "premium grade", "certified organic" → 5% ceiling expansion
    "partnership":       1.03,  # "loyalty deal", "returning customer" → 3% ceiling expansion
    "none":              1.00,  # No or generic message → no expansion
}
