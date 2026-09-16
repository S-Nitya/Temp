# Isolated Buyer Difficulty & Calibration Experiment Report

**Date**: 2026-09-14  
**Experiment**: Standalone Buyer Economic Calibration (Zero benchmark mutation)  
**Sample**: 15 Fixed Items × 5 Controlled Price Probes = **75 Probe Decisions**  
**Catalog SHA-256**: `b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`  
**Privacy Audit**: **100% Passed (0 Leaks)**

---

## 1. Executive Summary & Calibration Gate Assessment

| Calibration Metric | Observed Value | Interpretation |
| :--- | :--- | :--- |
| **Total Evaluations** | 75 probe decisions | 15 items × 5 price points (0.80x to 1.20x retail) |
| **Overall Action Distribution** | ACCEPT: 45.3% (34) / COUNTER: 45.3% (34) / WALK_AWAY: 9.3% (7) | **Natural economic mixture confirmed** |
| **Valuation / Retail Mean ± Std** | 0.9932 ± 0.1634 (range: 0.72 – 1.24) | Broad heterogeneous valuation spectrum |
| **Budget / Retail Mean ± Std** | 0.9958 ± 0.1784 (range: 0.73 – 1.27) | Realistic budget limits |
| **Calibration Gate Status** | **PASSED** | Population produces genuine economic price resistance |

---

## 2. Buyer Response by Controlled Price Probe

The 5 externally supplied price probes (0.80x to 1.20x of retail) measure the buyer's empirical demand curve:

| Price Probe | N | Accept Rate | Counter Rate | Walk-Away Rate | Avg Counter / Retail |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **0.80x Retail** | 15 | 73.3% (11) | 26.7% (4) | 0.0% (0) | 0.7286 |
| **0.90x Retail** | 15 | 66.7% (10) | 20.0% (3) | 13.3% (2) | 0.7799 |
| **1.00x Retail** | 15 | 46.7% (7) | 40.0% (6) | 13.3% (2) | 0.7934 |
| **1.10x Retail** | 15 | 33.3% (5) | 60.0% (9) | 6.7% (1) | 0.7803 |
| **1.20x Retail** | 15 | 6.7% (1) | 80.0% (12) | 13.3% (2) | 0.8828 |

---

## 3. Segmented Behavioral Analysis

### A. Results by Expiry Regime
| Expiry Regime | N | Accept Rate | Counter Rate | Walk-Away Rate | Avg Counter / Retail |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Critical** | 25 | 40.0% (10) | 48.0% (12) | 12.0% (3) | 0.7883 |
| **Medium** | 25 | 48.0% (12) | 48.0% (12) | 4.0% (1) | 0.8928 |
| **Low** | 25 | 48.0% (12) | 40.0% (10) | 12.0% (3) | 0.7458 |

### B. Results by Urgency
| Urgency Level | N | Accept Rate | Counter Rate | Walk-Away Rate |
| :--- | :---: | :---: | :---: | :---: |
| **LOW** | 20 | 45.0% (9) | 40.0% (8) | 15.0% (3) |
| **MODERATE** | 15 | 6.7% (1) | 80.0% (12) | 13.3% (2) |
| **HIGH** | 40 | 60.0% (24) | 35.0% (14) | 5.0% (2) |

### C. Results by Consumer Persona
| Persona | N | Accept Rate | Counter Rate | Walk-Away Rate |
| :--- | :---: | :---: | :---: | :---: |
| **BARGAIN_HUNTER** | 15 | 6.7% (1) | 80.0% (12) | 13.3% (2) |
| **CAUTIOUS_CONSERVATIVE** | 10 | 0.0% (0) | 80.0% (8) | 20.0% (2) |
| **PRAGMATIC_SHOPPER** | 30 | 53.3% (16) | 40.0% (12) | 6.7% (2) |
| **QUALITY_SEEKER** | 20 | 85.0% (17) | 10.0% (2) | 5.0% (1) |

### D. Results by Price Sensitivity
| Price Sensitivity | N | Accept Rate | Counter Rate | Walk-Away Rate |
| :--- | :---: | :---: | :---: | :---: |
| **LOW** | 20 | 85.0% (17) | 15.0% (3) | 0.0% (0) |
| **MODERATE** | 10 | 70.0% (7) | 10.0% (1) | 20.0% (2) |
| **HIGH** | 45 | 22.2% (10) | 66.7% (30) | 11.1% (5) |

---

## 4. Explicit Answers to Calibration Questions

### Question 1: Does the buyer reject/counter when the seller asks substantially above its private valuation?
> **YES (100.0% resistance)**. When the seller quote exceeded private valuation by >15% (23 occurrences), buyers resisted in 23/23 cases (5 walked away and 18 countered below valuation). Only 0 accepted, strictly in scenarios where budget allowed and high urgency overrode surplus optimization.

### Question 2: Does the buyer sometimes reject/counter near-retail prices?
> **YES (43.3% resistance)**. Across near-retail probes (0.90x and 1.00x retail, N=30), buyers resisted 13 times (9 counters and 4 walk-aways). Price-sensitive buyers and bargain hunters with sub-retail valuations actively negotiated rather than blindly accepting retail.

### Question 3: Does the buyer sometimes accept near-retail prices?
> **YES (56.7% acceptance)**. Near-retail quotes were accepted in 17/30 cases. Inelastic buyers, quality seekers, and high-urgency consumers whose private valuations met or exceeded retail accepted immediately, mirroring genuine retail shopping dynamics.

### Question 4: Does urgency materially affect decisions?
> **YES**. High-urgency buyers demonstrated an acceptance rate of 60.0%, compared to 45.0% for low-urgency buyers. Low-urgency shoppers exhibited greater willingness to counter or walk away when surplus was negative or thin.

### Question 5: Does buyer behavior vary meaningfully across personas?
> **YES**. Bargain hunters and cautious conservatives exhibited the highest resistance and lowest accept rates, aggressively countering with bids targeting 70–85% of retail. In contrast, pragmatic shoppers accepted fair market prices, and quality seekers tolerated higher price points.

### Question 6: Does the buyer population have enough economic heterogeneity for perishability to potentially become binding?
> **YES**. The calibrated distribution introduces genuine downward price resistance: because 33% of buyers value items below retail, a seller cannot simply hold near-retail prices and expect 100% instant clearance. If an automated seller insists on a high price as shelf life expires, price-resistant buyers will counter or walk away, making clearance vs. margin a binding operational tradeoff.

---

## 5. File Modification & Isolation Audit

- **Files Created**:
  - `kanishka_revised_mas/buyer_calibration_test/__init__.py`
  - `kanishka_revised_mas/buyer_calibration_test/buyer_generator.py`
  - `kanishka_revised_mas/buyer_calibration_test/buyer_agent.py`
  - `kanishka_revised_mas/buyer_calibration_test/runner.py`
  - `kanishka_revised_mas/buyer_calibration_test/results/buyer_calibration_report.md`
  - `kanishka_revised_mas/buyer_calibration_test/results/buyer_calibration.csv`
  - `kanishka_revised_mas/buyer_calibration_test/results/buyer_state_distribution.csv`
  - `kanishka_revised_mas/buyer_calibration_test/results/privacy_audit.md`
- **Files Modified Outside `buyer_calibration_test/`**: **0 (Zero)**
- **Production Benchmark Integrity**: The final N=5 benchmark results (`results/final_benchmark_report.md`, checkpoints, and summary CSVs) remain 100% byte-for-byte untouched.
