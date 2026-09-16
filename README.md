# Autonomous Multi-Agent Yield Management for Perishable Goods

## Overview

This project investigates autonomous Large Language Model (LLM) seller agents for yield management and dynamic pricing of perishable inventory. In perishable retail, an autonomous seller must balance:
- **Margin preservation**: Holding prices close to retail to maximize surplus.
- **Inventory clearance**: Ensuring inventory sells before physical expiration.
- **Terminal spoilage risk**: Preventing total asset loss ($100\%$ loss of cost price upon expiry).
- **Bilateral negotiation**: Countering, conceding, or holding firm against strategic buyers.
- **Computational inference cost**: Balancing agentic LLM deliberation overhead against realized profit.

The project evaluates a **hierarchical Multi-Agent System (MAS)** seller against a deterministic **LinearDecay** pricing heuristic under identical perishable inventory and private buyer constraints.

---

## Research Question

> *Under identical perishable inventory and private buyer constraints, does hierarchical LLM-based seller reasoning improve economic yield relative to a deterministic pricing heuristic, and how does behavior vary with remaining shelf life?*

---

## Environment

- **Fixed Catalog**: 15 distinct perishable grocery products spanning three shelf-life regimes:
  - **Critical (12h to 36h)**: Strawberries (12h), Fresh Fish (18h), Spinach (24h), Fresh Chicken (30h), Mushrooms (36h).
  - **Medium (48h to 120h)**: Fresh Bread (48h), Tomatoes (60h), Ground Beef (72h), Yogurt (96h), Soft Cheese (120h).
  - **Low (144h to 336h)**: Premium Beef (144h), Fresh Juice (168h), Apples (192h), Carrots (240h), Hard Cheese (336h).
- **Market Structure**: Bilateral 1-on-1 sequential encounter per item.
- **Physical Time vs. Communication**: Multi-exchange dialogue turns do not artificially advance physical shelf-life hours.
- **Terminal Spoilage Accounting**: Spoilage loss ($L = \text{cost}$) occurs if and only if physical market time reaches or exceeds product expiration ($t \ge \text{expiry}$) while unsold.
- **Bounded Interaction**: Up to 3 negotiation exchanges per session. Reaching round limits without agreement marks `MAX_ROUNDS_UNRESOLVED` rather than premature expiration.

---

## MAS Architecture

The seller Multi-Agent System operates across two hierarchical tiers:

### 1. Macro Strategic Layer (Opening Pricing & Policy Formulation)
- **StrategicBrain** (`Llama-3.1-70B`): Analyzes item economics, remaining shelf life, and expiration risk to propose initial asking quotes and absolute reservation floors.
- **BullDebater** (`Llama-3.1-8B`): Advocates for margin preservation and opposes premature discounting.
- **BearDebater** (`Llama-3.1-8B`): Advocates for inventory velocity and waste minimization to avert terminal spoilage.
- **DebateJudge** (`Llama-3.1-8B`): Synthesizes the strategic proposal and debate arguments into a binding opening quote, reservation floor, and strategy label (`DYNAMIC_YIELD`, `PREMIUM_HOLD`, `AGGRESSIVE_CLEARANCE`).

### 2. Tactical Negotiation Layer (Bilateral Exchange Execution)
- **RiskReader** (`Llama-3.1-8B`): Infers behavioral signals (bluffing probability, walk-away risk, concession sincerity) purely from observable dialogue and counter-offers.
- **ListingDecider** (`Llama-3.1-8B`): Evaluates buyer bids against remaining shelf life, deciding whether to `HOLD`, `CONCEDE`, or `ACCEPT`.
- **Spokesperson** (`Llama-3.1-8B`): Generates grounded natural language messages communicating seller quotes.

> **Information Boundary**: Seller agents never observe confidential buyer states (private valuation, budget ceiling, utility curves, or persona).

---

## Buyer Agent

The buyer is an autonomous LLM agent with confidential private variables:
- **Budget Ceiling**: Maximum allowable expenditure (hard constraint).
- **Private Valuation**: Intrinsic willingness to pay.
- **Urgency**: `LOW`, `MODERATE`, or `HIGH`.
- **Price Sensitivity**: `LOW`, `MODERATE`, or `HIGH`.
- **Persona**: `BARGAIN_HUNTER`, `PRAGMATIC_SHOPPER`, `QUALITY_SEEKER`, or `CAUTIOUS_CONSERVATIVE`.

The buyer independently decides whether to `ACCEPT`, `COUNTER` with a validated dollar bid, or `WALK_AWAY`. The seller cannot observe these variables.

---

## Baseline: LinearDecay Policy

**LinearDecay** is a deterministic pricing heuristic that steps asking quotes down linearly from retail reference price toward cost floor over exchange turns:
$$\text{Price}(k) = \max\left(\text{Cost}, \text{Retail} - \frac{k}{K}(\text{Retail} - \text{Cost})\right)$$
LinearDecay accepts any buyer offer meeting or exceeding its current quote, providing a strict zero-inference-cost baseline.

---

## Evaluation Metrics

- **True Net Profit ($)**: $\text{Gross Profit} - \text{Spoilage Loss} = \sum_{\text{sold}} (P_i - C_i) - \sum_{\text{expired}} C_i$
- **Profit Capture Ratio (PCR)**: $\frac{\text{Sale Price} - \text{Cost}}{\text{Retail Reference} - \text{Cost}}$ (for sold items)
- **Clearance Rate (%)**: Fraction of catalog items successfully sold.
- **Spoilage Loss ($)**: Total procurement cost forfeited to expired items.
- **Negotiation Rate (%)**: Proportion of transactions requiring multi-round bargaining.
- **Instant Clear Rate (%)**: Proportion of items accepted on opening quote.
- **Walk-Away Rate (%)**: Transactions terminating due to buyer departure.
- **Token Efficiency**: Realized Net Profit per 1,000 total tokens consumed.

---

## Final Benchmark Results (Validated $N=5$ Benchmark)

Evaluated across 5 paired trials (15 items each, 75 item encounters per condition, Seeds: 142, 242, 342, 442, 542):

| Metric | Hierarchical MAS ($N=5$) | LinearDecay Baseline ($N=5$) | Statistical Comparison |
| :--- | :---: | :---: | :---: |
| **True Net Profit ($)** | **$34.28 ± $0.92** | **$37.61 ± $0.99** | LinearDecay +$3.33/trial ($p < 0.05$) |
| **Profit Capture Ratio (PCR)** | **0.8288 ± 0.0188** | **0.9143 ± 0.0220** | LinearDecay +0.0855 ($p < 0.05$) |
| **Clearance Rate (%)** | **100.0% (75/75)** | **98.7% (74/75)** | MAS +1.3% |
| **Spoilage Loss ($)** | **$0.00 ± $0.00** | **$0.00 ± $0.00** | Zero spoilage in both |
| **Average Sale Price / Retail** | **0.9258 ± 0.0083** | **0.9620 ± 0.0097** | LinearDecay +0.0362 |
| **Instant Clear Rate (%)** | **74.7% (56/75)** | **53.3% (40/75)** | MAS opened closer to clearing price |
| **Walk-Away Rate (%)** | **0.0% (0/75)** | **1.3% (1/75)** | LD experienced 1 walk-away |
| **Tokens per Trial** | **84,915 ± 6,216** | **11,792 ± 808** | MAS consumed 7.2× more tokens |
| **Profit / 1k Tokens ($)** | **$0.4053 ± $0.0270** | **$3.1970 ± $0.1802** | Heuristic 7.9× more cost-efficient |

---

## Main Findings

1. **Heuristic Margin Advantage**: The deterministic LinearDecay policy achieved higher mean True Net Profit ($37.61 vs. $34.28) and higher PCR (0.9143 vs. 0.8288) by holding quotes closer to retail and conceding in small linear increments.
2. **Agentic Clearance Reliability**: Hierarchical MAS achieved complete clearance (100.0% vs. 98.7%) and zero walk-aways (0.0% vs. 1.3%), using dynamic debate and risk assessment to price within buyer reservation boundaries.
3. **Inference Cost Asymmetry**: MAS required ~85k tokens per trial versus ~12k tokens for LinearDecay (which consumed tokens solely for buyer responses). When computational overhead is considered, the deterministic heuristic is substantially more cost-effective on this benchmark.
4. **Perishability Reachability**: In the standard single-encounter benchmark, physical expiry did not bind because both policies cleared inventory before expiration. Follow-up isolated diagnostics confirmed that when multi-interval market dynamics are introduced (2.0-hour decision intervals), physical expiry is reachable.

---

## Important Experimental History & Repairs

Earlier development versions suffered from three critical methodological flaws that were diagnosed and resolved:
1. **Round-Expiry Coupling**: Earlier environments conflated communication rounds ($ex=3$) with physical expiration, improperly declaring spoilage on valid items. This was repaired by strictly separating communication turns from physical simulated time.
2. **Malformed Bid Fallback**: Invalid buyer regex outputs were previously converted to $0.00 bids. The environment now uses structured Pydantic JSON parsing with explicit retries and an `INVALID_BUYER_RESPONSE` terminal state.
3. **Rate Limiting & Concurrency**: LLM concurrency bottlenecks were resolved via exponential backoff with jitter and round-robin key rotation.

The finalized environment was verified against an 8-test deterministic audit suite (`kanishka_revised_mas/test_environment_audit.py`), passing all assertions.

---

## Reproducibility

- **Fixed Catalog**: Cryptographically verified via SHA-256 (`b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`).
- **Paired Design**: Identical buyer states replayed across both conditions for every trial.
- **Seeds**: Exact trial seeds 142, 242, 342, 442, 542.
- **Zero-Leakage Privacy**: Audited across all calls; zero buyer private variables injected into seller prompts.
- **Audit Script**: Run `python -m kanishka_revised_mas.test_environment_audit` to execute the deterministic verification test suite.

---

## Repository Structure

```
Perishable_Agentic_AI/
├── kanishka_revised_mas/                 # Production benchmark implementation
│   ├── catalog.py                       # Fixed 15-product perishable catalog & SHA-256
│   ├── buyer.py                         # Calibrated autonomous buyer agent
│   ├── mas_agents.py                    # 7-agent hierarchical seller architecture
│   ├── environment.py                   # Repaired market environment with true clock
│   ├── linear_decay.py                  # Deterministic LinearDecay benchmark policy
│   ├── runner.py                        # Benchmark trial execution engine
│   ├── test_environment_audit.py       # 8-test deterministic validation suite
│   ├── llm_client.py                    # LLM client with token tracking & key rotation
│   ├── results/                         # Validated N=5 final benchmark outputs
│   │   ├── final_benchmark_report.md    # Comprehensive publication report
│   │   ├── final_summary.csv            # Condition-level summary metrics
│   │   ├── final_perishability_analysis.csv # Regime breakdown (Critical, Medium, Low)
│   │   ├── final_token_analysis.csv     # Token and computational efficiency data
│   │   ├── final_integrity_audit.md     # Cryptographic integrity and privacy audit
│   │   ├── checkpoints/                 # Raw JSON checkpoints (T1 to T5)
│   │   └── logs/                        # Item-by-item interaction logs
│   └── buyer_calibration_test/          # Isolated calibration and diagnostic tests
│       ├── buyer_generator.py           # Calibrated buyer distribution generator
│       ├── buyer_agent.py               # Calibrated buyer agent implementation
│       ├── stress_test/                 # 1 MAS vs 1 LinearDecay paired stress test
│       ├── time_expiry_test/            # Clock reachability & state machine tests
│       └── perishability_pilot/         # Real-time multi-interval perishability pilot
├── legacy_results/                      # Archived historical ablation benchmark
├── docs/                                # Positioning, related work, and limitations drafts
├── results/                             # Root copy of final benchmark reports
├── EXPERIMENT_STATUS.md                 # Formal declaration of experimental freeze
├── REPRODUCIBILITY.md                   # Step-by-step reproduction instructions
└── README.md                            # Main project overview (this document)
```

---

## Status

**Benchmark Status: FINAL & FROZEN.**
All experiments are complete. Experimental code and result files are read-only. The project has transitioned to manuscript preparation.
