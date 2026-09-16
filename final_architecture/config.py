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
    "Llama-70B-NV": {"id": "openai/gpt-oss-120b", "provider": "groq"},
    "Llama-8B-NV":  {"id": "openai/gpt-oss-20b",  "provider": "groq"},
    "Llama-70B-GR": {"id": "openai/gpt-oss-120b", "provider": "groq"},
    "Llama-8B-GR":  {"id": "openai/gpt-oss-20b",  "provider": "groq"},
    "Mixtral-8x7B-GR": {"id": "openai/gpt-oss-20b", "provider": "groq"},
}

# --- FINAL ARCHITECTURE CONFIG ---
FINAL_CONFIG = {
    "strategic_brain":    "Llama-70B-GR",
    "tactical_negotiator": "Llama-70B-GR",
    "chaos_injector":     "Llama-70B-GR",
}

# --- SIMULATION PARAMETERS ---
N_BUYERS     = 15
MAX_HOURS    = 10
SIM_CLOCK_TICK = 2
GLOBAL_SEED  = 42

# --- TEMPERATURE SETTINGS (Adversarial Differentiation) ---
# Buyer uses higher temperature for behavioral stubbornness and realistic negotiation friction
# Seller agents use lower temperature for rational, strategic consistency
BUYER_TEMPERATURE = 0.7
SELLER_TEMPERATURE = 0.2

# --- BUYER UTILITY PERSONAS ---
# U = alpha * ln(V - P) - beta * max(0, T_deadline - T_current)
PERSONA_PROFILES = {
    "ESSENTIAL":  {"alpha": 0.8, "beta": 1.5, "desc": "High urgency procurement. Needs item critically for operations; accepts moderate price premium to secure supply before deadline."},
    "CALCULATED": {"alpha": 1.8, "beta": 0.4, "desc": "Ruthless margin maximizer. Price-sensitive, counters aggressively, walks away rather than overpaying."},
    "IMPULSE":    {"alpha": 1.2, "beta": 0.9, "desc": "Opportunistic buyer. Spontaneous but bounded by firm corporate budget limits."},
}
