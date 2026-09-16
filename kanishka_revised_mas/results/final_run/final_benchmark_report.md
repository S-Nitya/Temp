# Final Benchmark Report: Hierarchical MAS vs. LinearDecay (N=5 Trials)

## 1. Executive Summary & Core Research Question

> **Research Question**: Under identical perishable inventory and private buyer constraints, does a hierarchical LLM-based seller achieve better true net profit than a deterministic LinearDecay pricing policy, and how does performance vary with remaining shelf life?

### Final Condition Summary Table (Mean ± Standard Deviation)

| Metric | Hierarchical MAS (N=5) | LinearDecay Baseline (N=5) | Delta (Δ) |
| :--- | :--- | :--- | :--- |
| **True Net Profit ($)** | .28 ± .92 | **.61 ± .99** | -.33 |
| **Gross Profit ($)** | .28 ± .92 | **.61 ± .99** | -.33 |
| **Spoilage Loss ($)** | .00 ± .00 | .00 ± .00 | .00 |
| **Profit Capture Ratio (PCR)** | 0.8288 ± 0.0188 | **0.9143 ± 0.0220** | -0.0855 |
| **Clearance Rate (%)** | **100.0% (75/75)** | 98.7% (74/75) | +1.3% |
| **Average Sale Price / Retail** | 0.9258 ± 0.0084 | **0.9620 ± 0.0098** | -0.0362 |
| **Instant Clear Rate (%)** | **74.7%** | 53.3% | +21.4% |
| **Negotiated Sale Rate (%)** | 25.3% | 45.3% | -20.0% |
| **Walk Away Rate (%)** | **0.0%** | 1.3% | -1.3% |
| **Total Tokens / Trial** | 84,915 ± 6,216 | **11,792 ± 808** | +73,123 |
| **Tokens / Sold Item (Trial Ratio)** | 5,661.0 ± 414.5 | **797.2 ± 55.7** | +4,863.8 |
| **Profit / 1,000 Total Tokens ($)** | .4065 ± .0392 | **.2076 ± .2688** | -.8011 |
| **Profit / 1,000 Seller Tokens ($)** | .4655 ± .0473 | NA (Deterministic Policy) | — |

---

## 2. Individual Trial Results

### Hierarchical MAS Trials (N=5)
| Trial | Seed | Net Profit ($) | Gross Profit ($) | Spoilage ($) | Sold/15 | Expired/15 | Unresolved/15 | Mean PCR | Price/Retail | Total Tokens |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| T1 | 142 | .23 | .23 | .00 | 15 | 0 | 0 | 0.8341 | 0.9277 | 88,997 |
| T2 | 242 | .70 | .70 | .00 | 15 | 0 | 0 | 0.8211 | 0.9205 | 79,718 |
| T3 | 342 | .81 | .81 | .00 | 15 | 0 | 0 | 0.8228 | 0.9228 | 87,976 |
| T4 | 442 | .12 | .12 | .00 | 15 | 0 | 0 | 0.8612 | 0.9411 | 75,627 |
| T5 | 542 | .53 | .53 | .00 | 15 | 0 | 0 | 0.8046 | 0.9168 | 92,259 |

### LinearDecay Baseline Trials (N=5)
| Trial | Seed | Net Profit ($) | Gross Profit ($) | Spoilage ($) | Sold/15 | Expired/15 | Unresolved/15 | Mean PCR | Price/Retail | Total Tokens |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| T1 | 142 | .10 | .10 | .00 | 15 | 0 | 0 | 0.9117 | 0.9615 | 11,332 |
| T2 | 242 | .54 | .54 | .00 | 15 | 0 | 0 | 0.9130 | 0.9608 | 11,448 |
| T3 | 342 | .09 | .09 | .00 | 14 | 0 | 0 | 0.9377 | 0.9723 | 11,595 |
| T4 | 442 | .41 | .41 | .00 | 15 | 0 | 0 | 0.9336 | 0.9706 | 11,197 |
| T5 | 542 | .91 | .91 | .00 | 15 | 0 | 0 | 0.8757 | 0.9446 | 13,388 |

---

## 3. Perishability Regime Breakdown (Critical vs. Medium vs. Low Expiry)

| Expiry Regime | Metric | Hierarchical MAS | LinearDecay Baseline | Advantage |
| :--- | :--- | :--- | :--- | :--- |
| **Critical (12-36h)** | Clearance Rate | 25/25 (100.0%) | 25/25 (100.0%) | Parity |
| **Critical (12-36h)** | True Net Profit | .22 | **.01** | LinearDecay (+.79) |
| **Critical (12-36h)** | Gross Profit | .22 | **.01** | LinearDecay (+.79) |
| **Critical (12-36h)** | Spoilage Loss | .00 | .00 | Parity () |
| **Critical (12-36h)** | Profit Capture Ratio | 0.7913 | **0.9219** | LinearDecay (+0.1306) |
| **Critical (12-36h)** | Sale Price / Retail | 0.9145 | **0.9672** | LinearDecay (+0.0527) |
| **Critical (12-36h)** | Negotiation Rate | 8.0% (2/25) | 48.0% (12/25) | MAS faster clear |
| **Critical (12-36h)** | Tokens Consumed | 27,628 | 3,755 | LinearDecay 7.4x leaner |
| **Medium (48-120h)** | Clearance Rate | 25/25 (100.0%) | 25/25 (100.0%) | Parity |
| **Medium (48-120h)** | True Net Profit | .76 | **.07** | LinearDecay (+.31) |
| **Medium (48-120h)** | Gross Profit | .76 | **.07** | LinearDecay (+.31) |
| **Medium (48-120h)** | Spoilage Loss | .00 | .00 | Parity () |
| **Medium (48-120h)** | Profit Capture Ratio | 0.8329 | **0.9269** | LinearDecay (+0.0940) |
| **Medium (48-120h)** | Sale Price / Retail | 0.9261 | **0.9674** | LinearDecay (+0.0413) |
| **Medium (48-120h)** | Negotiation Rate | 24.0% (6/25) | 40.0% (10/25) | MAS faster clear |
| **Medium (48-120h)** | Tokens Consumed | 27,203 | 4,238 | LinearDecay 6.4x leaner |
| **Low (144-336h)** | Clearance Rate | **25/25 (100.0%)** | 24/25 (96.0%) | **MAS (+4.0%)** |
| **Low (144-336h)** | True Net Profit | .30 | **.53** | LinearDecay (+.23) |
| **Low (144-336h)** | Gross Profit | .30 | **.53** | LinearDecay (+.23) |
| **Low (144-336h)** | Spoilage Loss | .00 | .00 | Parity () |
| **Low (144-336h)** | Profit Capture Ratio | 0.8621 | **0.8924** | LinearDecay (+0.0303) |
| **Low (144-336h)** | Sale Price / Retail | 0.9367 | **0.9504** | LinearDecay (+0.0137) |
| **Low (144-336h)** | Negotiation Rate | 44.0% (11/25) | 48.0% (12/25) | Parity |
| **Low (144-336h)** | Tokens Consumed | 30,083 | 3,798 | LinearDecay 7.9x leaner |

---

## 4. Key Scientific Insights & Empirical Diagnosis

### 1. True Net Profit vs. Clearance Tradeoff
- **LinearDecay achieved higher True Net Profit** (.61 ± .99 vs. .28 ± .92, $\Delta = +\.33$) and a higher Profit Capture Ratio (0.9143 vs. 0.8288) across the 5 paired trials.
- **Hierarchical MAS achieved superior clearance robustness** (100.0%, 75/75 items sold with 0 walk-aways) compared to LinearDecay (98.7%, 74/75 items sold, suffering 1 buyer walk-away in Trial 3).

### 2. Strategic Brain & Tactical Pipeline Behavior
- **LinearDecay Anchoring Effect**: LinearDecay strictly initializes at 100% of the retail reference price ( = P_{	ext{retail}} - (P_{	ext{retail}} - P_{	ext{cost}}) \cdot rac{t}{T_{	ext{expiry}}}$ with =0$). For items with 24h to 336h shelf life, small physical elapsed times ( = 1.0	ext{h} - 2.0	ext{h}$) result in very shallow concessions ($pprox 1\% - 4\%$). Because a significant fraction of private buyers possessed valuations/budgets near retail, LinearDecay successfully extracted higher margins (0.9620 average sale price / retail).
- **MAS Preemptive Risk Discounting**: The StrategicBrain (120B) and Debate Judge explicitly evaluated perishability urgency and set competitive opening quotes (averaging 92.6% of retail). This pricing posture stimulated strong buyer demand, driving an **Instant Clear Rate of 74.7%** (vs. 53.3% for LinearDecay) and completely eliminating buyer walk-aways (0.0% vs. 1.3%), but surrendered ~3.6% in realized price.

### 3. Perishability Regime Sensitivity
- In the **Critical Regime (12–36h)**, MAS exhibited rapid clearance behavior: 92.0% of transactions cleared instantly (only 8.0% negotiated), securing .22 net profit vs. .01 for LinearDecay.
- In the **Low Regime (144–336h)**, where perishability pressure is minimal, the profit difference compressed drastically from .79 in Critical down to just .23 (.30 for MAS vs. .53 for LinearDecay). Crucially, LinearDecay suffered its only transaction breakdown in this regime (Trial 3 Apples, 192h, where the buyer walked away after rigid quotes), whereas MAS adapted to achieve 100% clearance.

### 4. Computational & Economic Efficiency
- LinearDecay operated with extreme computational efficiency: **.21 profit per 1,000 tokens** (using tokens solely for autonomous buyer evaluation).
- Hierarchical MAS required **84,915 tokens per trial**, generating **.41 profit per 1,000 tokens**. The multi-agent debate and risk analysis architecture achieved flawless clearance at the expense of higher token overhead.
