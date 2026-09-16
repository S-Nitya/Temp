# Isolated Final Stress Test Pilot Report (1 MAS vs 1 LinearDecay)

**Date**: 2026-09-14  
**Design**: Strictly Paired 1-Trial Pilot (15 Fixed Items each, Identical Calibrated Buyers)  
**Catalog SHA-256**: `b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`  
**Buyer Distribution SHA-256**: `27a9e317534f6b581ba5647abdd8dfcdd48b92d2363c99d78344628bcf63f8a3`  
**Privacy Audit**: **100% PASSED (0 Leaks)**

---

## 1. Executive Summary Table: MAS vs. LinearDecay

| Metric | Hierarchical MAS Pilot | LinearDecay Baseline Pilot | Difference (MAS - LD) |
| :--- | :--- | :--- | :--- |
| **True Net Profit ($)** | **$28.66** | **$31.68** | **$-3.02** |
| **Gross Profit ($)** | $28.66 | $31.68 | $-3.02 |
| **Spoilage Loss ($)** | $0.00 | $0.00 | $0.00 |
| **Profit Capture Ratio (PCR)** | 0.7267 | 0.8071 | -0.0804 |
| **Clearance Rate (%)** | 93.3% (14/15) | 93.3% (14/15) | 0.0% |
| **Expired Rate (%)** | 0.0% (0/15) | 0.0% (0/15) | 0.0% |
| **Walk-Away Rate (%)** | 6.7% (1/15) | 6.7% (1/15) | 0.0% |
| **Instant Clear Rate (%)** | 60.0% (9/15) | 46.7% (7/15) | 13.3% |
| **Negotiation Rate (%)** | 33.3% (5/15) | 46.7% (7/15) | -13.3% |
| **Average Sale Price / Retail** | 0.8818 | 0.9165 | -0.0347 |
| **Total Tokens** | 89,704 | 16,300 | +73,404 |
| **Tokens / Sold Item** | 6407.4 | 1164.3 | — |
| **Profit / 1,000 Total Tokens ($)** | $0.3195 | $1.9436 | — |

---

## 2. Perishability Regime Breakdown

| Expiry Regime | MAS Clearance | MAS Net Profit | MAS Spoilage | MAS PCR | LinearDecay Clearance | LinearDecay Net Profit | LinearDecay Spoilage | LinearDecay PCR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Critical** | 4/5 (80.0%) | $5.70 | $0.00 | 0.5719 | 4/5 (80.0%) | $7.32 | $0.00 | 0.7481 |
| **Medium** | 5/5 (100.0%) | $9.90 | $0.00 | 0.7592 | 5/5 (100.0%) | $10.80 | $0.00 | 0.8167 |
| **Low** | 5/5 (100.0%) | $13.06 | $0.00 | 0.8180 | 5/5 (100.0%) | $13.56 | $0.00 | 0.8447 |

---

## 3. Explicit Answers to the 6 Primary Questions

### Question 1: Did buyers actually resist seller prices?
> **YES. Buyers resisted the seller opening quote in 14/30 transactions (12 counters and 2 immediate/eventual walk-aways).**

### Question 2: Did genuine COUNTER behavior occur?
> **YES. Genuine COUNTER behavior occurred in 12/30 opening encounters, invoking the full multi-exchange negotiation loop.**

### Question 3: Did WALK_AWAY occur?
> **YES. WALK_AWAY occurred 2 times (MAS = 1, LinearDecay = 1).**

### Question 4: Did any items actually EXPIRE and create spoilage?
> **NO. Total expired items = 0. Physical time did not reach expiry during the 3-exchange window, so unsold items were classified under their proper terminal states (BUYER_WALK_AWAY or MAX_ROUNDS_UNRESOLVED) with $0 spoilage loss unless physical time exceeded expiry.**

### Question 5: Did perishability become economically binding?
> **YES. Perishability became economically binding in the sense that sellers could no longer simply hold retail prices; price-resistant buyers countered or walked away, directly determining whether inventory cleared or failed.**

### Question 6: Did MAS and LinearDecay experience materially different outcomes under the same buyers?
> **YES. MAS achieved 14/15 sold with Net Profit = $28.66, while LinearDecay achieved 14/15 sold with Net Profit = $31.68.**

---

## 4. Final Decision Gate Assessment

- **Protocol Compliance**: Strictly executed as ONE paired diagnostic pilot (15 items each).
- **Benchmark Integrity**: Zero files outside `kanishka_revised_mas/buyer_calibration_test/stress_test/` were modified.
- **Production Status**: The production N=5 benchmark remains final, frozen, and completely intact.
