# Reproducibility Guide

This document provides complete instructions for inspecting, verifying, and replicating the experimental results presented in this repository.

---

## 1. System Requirements & Environment Setup

### Prerequisites
- **Python Version**: Python 3.10, 3.11, or 3.12.
- **Operating System**: Linux, macOS, or Windows (PowerShell / Bash).
- **Core Dependencies**:
  ```bash
  pip install httpx pydantic python-dotenv pandas numpy
  ```

### API Configuration
The benchmark uses Groq API endpoints for LLM model calls.
Create a local `.env` file in the root directory (this file is excluded from Git via `.gitignore`):
```bash
# Example .env (Do NOT commit actual keys to version control)
GROQ_API_KEYS="gsk_key1,gsk_key2"
# Or single key:
GROQ_API_KEY="gsk_key1"
```

The system automatically rotates keys round-robin to mitigate rate limits during high-throughput agent deliberation.

---

## 2. Experimental Architecture & Integrity Guarantees

### Fixed Catalog Integrity
The benchmark uses a fixed 15-item catalog defined in `kanishka_revised_mas/catalog.py`.
Before every benchmark execution, the runner verifies the cryptographic hash of the catalog:
- **Catalog SHA-256 Checksum**: `b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`
If the catalog has been tampered with or modified, execution aborts immediately.

### Paired Buyer State Replay
To eliminate extraneous market noise, both seller policies (**Hierarchical MAS** and **LinearDecay**) face the exact same buyer private state for every product in every trial:
- For each trial $t \in \{1, 2, 3, 4, 5\}$, buyer private states (budget ceiling, private valuation, urgency, price sensitivity, persona) are generated using fixed seeds:
  - Trial 1: Seed 142
  - Trial 2: Seed 242
  - Trial 3: Seed 342
  - Trial 4: Seed 442
  - Trial 5: Seed 542
- Buyer states are cryptographically hashed and saved into the checkpoint before any transaction occurs.
- The LinearDecay trial loads and replays the identical buyer states generated for the MAS trial.

### Strict Information Boundaries & Zero-Leakage Privacy Audit
- Seller agents receive only observable market state: product name, category, cost, retail reference, current remaining shelf life, and dialogue history.
- Confidential buyer variables (`budget_ceiling`, `private_valuation`, `persona`, `urgency`, `price_sensitivity`) are strictly encapsulated in the buyer agent.
- An automated privacy audit inspects every prompt sent to all seller agents (`StrategicBrain`, `BullDebater`, `BearDebater`, `DebateJudge`, `RiskReader`, `ListingDecider`, `Spokesperson`). If any private variable name or private value appears in a seller prompt, the audit flags a critical violation.
- In the final $N=5$ benchmark, **0 privacy leaks occurred across all 546 LLM calls** (`results/final_integrity_audit.md`).

### Independent Physical Time Tracking
- Communication exchanges within a negotiation session do not advance physical shelf life.
- Simulated physical time progresses based on environmental market intervals.
- Terminal spoilage loss occurs if and only if physical market time reaches or exceeds the item's expiration deadline ($t \ge \text{expiry}$) while unsold.
- Unresolved exchanges at the round limit ($ex=3$) terminate as `MAX_ROUNDS_UNRESOLVED` with zero spoilage if shelf life remains.

---

## 3. Verification & Validation Commands

All verification commands below are strictly non-experimental and consume **zero LLM tokens**:

### 1. Deterministic Environment Audit
Run the 8-test unit test suite verifying physical time separation, terminal state categorization, true spoilage accounting, and bid preservation:
```bash
python -m kanishka_revised_mas.test_environment_audit
```
*Expected Output: `ALL 8/8 DETERMINISTIC AUDIT TESTS PASSED SUCCESSFULLY!`*

### 2. Time Reachability Diagnostics
Run the deterministic clock analysis across the catalog:
```bash
python -m kanishka_revised_mas.buyer_calibration_test.time_expiry_test.run_diagnostics
```
*Artifacts produced in `kanishka_revised_mas/buyer_calibration_test/time_expiry_test/results/`.*

### 3. File Integrity Verification
Verify that production code matches the frozen benchmark checksums:
```bash
python -c "
import hashlib
files = [
    'kanishka_revised_mas/catalog.py',
    'kanishka_revised_mas/buyer.py',
    'kanishka_revised_mas/mas_agents.py',
    'kanishka_revised_mas/environment.py',
    'kanishka_revised_mas/linear_decay.py',
    'kanishka_revised_mas/runner.py',
]
for f in files:
    with open(f, 'rb') as fp:
        print(f'{f}: {hashlib.sha256(fp.read()).hexdigest()[:16]}...')
"
```

---

## 4. Checkpoint & Artifact Hierarchy

All raw transaction data, conversation histories, and agent reasoning traces are preserved in structured JSON and CSV formats:

```
kanishka_revised_mas/results/
├── checkpoints/
│   ├── MAS_T1.json ... MAS_T5.json               # Full raw trial data (15 items each)
│   └── LinearDecay_T1.json ... LinearDecay_T5.json # Paired baseline trial data
├── logs/
│   ├── call_records_MAS_T1.jsonl ...             # Complete prompt/response LLM logs
│   └── call_records_LinearDecay_T1.jsonl ...
├── final_summary.csv                              # Summary statistics per condition
├── final_perishability_analysis.csv              # Expiry regime breakdown
├── final_token_analysis.csv                      # Token usage and computational efficiency
└── final_benchmark_report.md                     # Comprehensive academic report
```

---

## 5. Token Accounting & Hardware Efficiency

Token usage is tracked directly from provider API response headers (`usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`):
- **MAS Costs**: Sum of all 7 seller agent invocations.
- **Baseline Costs**: LinearDecay consumes 0 seller tokens (heuristic logic); token records capture only the buyer agent responses.
- **Metric**: $\text{Economic Efficiency} = \frac{\text{True Net Profit}}{\text{Total Tokens} / 1000}$.
