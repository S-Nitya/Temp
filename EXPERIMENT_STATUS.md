# Experiment Status: Final Benchmark Freeze

**Date of Freeze**: 2026-09-16  
**Status**: **EXPERIMENTATION COMPLETE — BENCHMARK FROZEN**  
**Action Item**: No further benchmark executions, prompt alterations, or agent tuning are permitted. The repository has officially transitioned from empirical experimentation to paper manuscript drafting.

---

## 1. Experimental Track Categorization

This repository contains three clearly distinguished tracks of empirical work:

```
                                  REPOSITORY EVIDENCE MAP
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      ▼                                      ▼                                      ▼
[1. FINAL BENCHMARK]               [2. CALIBRATION & DIAGNOSTICS]            [3. LEGACY RESULTS]
- 5 MAS vs 5 LinearDecay Trials    - Isolated Buyer Calibration              - Deprecated N=5 Ablation
- 75 Transactions / Condition      - Paired Stress Test (Seed 999)           - Mixed Legacy Catalogs
- Seeds: 142, 242, 342, 442, 542   - Time Reachability Diagnostics           - Archived in archive/legacy_results/
- Frozen in results/               - Perishability Pilot (2h intervals)      - Strictly READ-ONLY
```

---

## 2. Track 1: Final Validated Benchmark (Production)

- **Location**: [`kanishka_revised_mas/results/`](kanishka_revised_mas/results/) and [`results/`](results/)
- **Protocol**: Strictly paired $N=5$ trials per condition across the fixed 15-item catalog (`SHA-256: b49a8fd5...`).
- **Trial Seeds**: 142, 242, 342, 442, 542.
- **Audits Passed**:
  - **Deterministic Environment Audit**: 8/8 test assertions passed (`kanishka_revised_mas/test_environment_audit.py`).
  - **Privacy Audit**: 0 confidential buyer state variables leaked across all 546 LLM calls.
  - **Catalog Integrity**: 100% byte-for-byte consistency across all trials.
- **Summary Metrics**:
  - **Hierarchical MAS**: True Net Profit = **$34.28 ± $0.92**, PCR = **0.8288 ± 0.0188**, Clearance = **100.0%**, Spoilage = **$0.00**, Tokens = **84,915 ± 6,216**.
  - **LinearDecay Baseline**: True Net Profit = **$37.61 ± $0.99**, PCR = **0.9143 ± 0.0220**, Clearance = **98.7%**, Spoilage = **$0.00**, Tokens = **11,792 ± 808**.

---

## 3. Track 2: Calibration & Diagnostic Experiments (Isolated)

All calibration and diagnostic scripts, data, and reports are strictly confined inside [`kanishka_revised_mas/buyer_calibration_test/`](kanishka_revised_mas/buyer_calibration_test/):

1. **Buyer Population Calibration** ([`buyer_calibration_test/results/`](kanishka_revised_mas/buyer_calibration_test/results/)):
   - Generated a calibrated, heterogeneous buyer distribution across 4 distinct personas (`BARGAIN_HUNTER`, `PRAGMATIC_SHOPPER`, `QUALITY_SEEKER`, `CAUTIOUS_CONSERVATIVE`) with valuation ratios spanning $0.72\times$ to $1.24\times$ retail.
2. **Paired Stress Test Pilot** ([`buyer_calibration_test/stress_test/results/`](kanishka_revised_mas/buyer_calibration_test/stress_test/results/)):
   - Evaluated 1 MAS vs. 1 LinearDecay trial (Seed 999) under the calibrated buyer population.
   - Demonstrated genuine buyer resistance (53.3% resistance on opening quotes) and confirmed emergence of multi-exchange counter offers and walk-away behavior.
3. **Time / Expiry Reachability Diagnostics** ([`buyer_calibration_test/time_expiry_test/results/`](kanishka_revised_mas/buyer_calibration_test/time_expiry_test/results/)):
   - Proved mathematically that a single 3-exchange transaction ceiling ($3.0\text{h}$) cannot naturally reach the minimum $12.0\text{h}$ catalog shelf life.
   - Verified that the state machine independently triggers `EXPIRED` with full cost loss when $t \ge \text{expiry}$.
4. **Real-Time Perishability Pilot** ([`buyer_calibration_test/perishability_pilot/results/`](kanishka_revised_mas/buyer_calibration_test/perishability_pilot/results/)):
   - Implemented fixed 2.0-hour market decision intervals with communication-only exchange turns.
   - Demonstrated clock progression from $t = 0\text{h} \rightarrow 2\text{h}$ upon buyer walk-away (e.g., Strawberries clearing in Session 2).

---

## 4. Track 3: Legacy Results (Archived)

- **Location**: [`archive/legacy_results/`](archive/legacy_results/)
- **Description**: Contains historical results from early multi-model and ablation studies (Full MAS, No RiskReader, No StrategicBrain, LinearDecay).
- **Status**: **DEPRECATED / ARCHIVED AS LEGACY**. These files are preserved for historical record-keeping and provenance but are **not** part of the active production benchmark.

---

## 5. Decision Gate Log

| Checkpoint | Gate Criteria | Result | Action Taken |
| :--- | :--- | :---: | :--- |
| **Gate 1: Metric & Audit Repair** | Eliminate round-coupling & regex errors | **PASSED** | Repaired environment; verified with 8/8 unit tests. |
| **Gate 2: $N=5$ Benchmark Replication** | 5 paired trials with full checkpointing | **PASSED** | 10 checkpoint files generated; final report compiled. |
| **Gate 3: Buyer Calibration** | Natural resistance without forced logic | **PASSED** | Calibrated heterogeneous distribution generated. |
| **Gate 4: Time Reachability Test** | Determine physical clock limits | **PASSED** | Diagnosed 3h horizon constraint mathematically. |
| **Gate 5: Real-Time Perishability Pilot** | Validate 2h market decision interval | **PASSED** | Verified multi-session clock progression. |
| **Gate 6: Final Freeze** | Complete audit, cleanup, commit & push | **ACTIVE** | All experimental execution permanently halted. |

---

## 6. Final Certification

I certify that the empirical data reported in `results/final_benchmark_report.md` represents the complete, unmodified, and final experimental benchmark for this project. No additional runs, tuning iterations, or parameter modifications will be conducted.
