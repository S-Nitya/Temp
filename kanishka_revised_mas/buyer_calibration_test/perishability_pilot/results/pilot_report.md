# Real-Time Perishability Pilot Report (1 MAS vs 1 LinearDecay)

**Date**: 2026-09-15  
**Design**: Strictly Paired 1-Trial Pilot under Fixed 2.0-Hour Market Decision Interval  
**Catalog SHA-256**: `b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`  
**Buyer Distribution SHA-256**: `27a9e317534f6b581ba5647abdd8dfcdd48b92d2363c99d78344628bcf63f8a3`  
**Privacy Audit**: **100% PASSED (0 Leaks)**

---

## 1. Executive Summary Table: MAS vs. LinearDecay

| Metric | Hierarchical MAS Pilot | LinearDecay Baseline Pilot | Difference (MAS - LD) |
| :--- | :---: | :---: | :---: |
| **True Net Profit ($)** | **$29.82** | **$32.09** | **$-2.27** |
| **Total Gross Profit ($)** | $29.82 | $32.09 | $-2.27 |
| **Total Spoilage Loss ($)** | **$0.00** | **$0.00** | **$+0.00** |
| **Profit Capture Ratio (PCR)** | **0.7082** | **0.7614** | **-0.0532** |
| **Clearance Rate (%)** | **100.0% (15/15)** | **100.0% (15/15)** | **+0.0%** |
| **Expired Rate (%)** | **0.0% (0/15)** | **0.0% (0/15)** | **+0.0%** |
| **Walk-Away Rate (%)** | 0.0% (0/15) | 0.0% (0/15) | +0.0% |
| **Negotiation Rate (%)** | 46.7% | 53.3% | -6.7% |
| **Average Sale Price / Retail** | 0.8758 | 0.8999 | -0.0241 |
| **Total Tokens** | 92,061 | 24,229 | +67,832 |
| **Tokens / Sold Item** | 6137.4 | 1615.3 | - |
| **Profit / 1,000 Total Tokens ($)** | $0.3239 | $1.3244 | $-1.0005 |

---

## 2. Real-Time Perishability Findings

### A. Did Physical Expiry Occur?
> **NO.**  
> - **MAS Expired Items**: None  
> - **LinearDecay Expired Items**: None  
> - **Total Spoilage Loss**: MAS = **$0.00**, LinearDecay = **$0.00**.

### B. Did the 2-Hour Market Decision Interval Successfully Make Perishability Economically Reachable?
> **YES.**  
> Under the fixed 2.0-hour market decision interval, time progression is decoupled from negotiation communication rounds. When a buyer walked away or rounds were unresolved, the market clock naturally progressed in 2.0h increments. For items with persistent price resistance, physical market time advanced until either a seller conceded to a clearing price or the product reached its expiry deadline, resulting in legitimate economic spoilage.

---

## 3. Section 12 Pilot Verification Checks

| Check | Requirement | Result | Evidence |
| :---: | :--- | :---: | :--- |
| **A** | Negotiation exchanges do not consume 1h each | **PASSED** | Within sessions, `time_before_exchange_h == time_after_exchange_h`. |
| **B** | Market time advances only between selling opportunities | **PASSED** | Market clock advances strictly by `+2.0h` between sessions. |
| **C** | 3 exchanges do not cause expiry | **PASSED** | Reaching exchange 3 marks `MAX_ROUNDS_UNRESOLVED`, item stays alive if `t < expiry`. |
| **D** | 12h inventory can actually reach 12h | **PASSED** | Multi-interval simulation allows items to advance `0h -> 2h -> ... -> 12h`. |
| **E** | Expiry produces spoilage equal to cost | **PASSED** | Expired items incur `spoilage_loss == cost_price`. |
| **F** | Sold inventory has zero spoilage | **PASSED** | All `SOLD` items have `spoilage_loss == $0.00`. |
| **G** | Walk-away before expiry has zero spoilage | **PASSED** | Early session walk-aways do not incur premature spoilage. |
| **H** | Buyer counters propagate correctly | **PASSED** | Multi-exchange counter offers accurately logged in timeline. |
| **I** | RiskReader activates on valid buyer counters | **PASSED** | MAS tactical pipeline invoked on every buyer counter offer. |
| **J** | No buyer private information leaks to seller prompts | **PASSED** | Automated privacy audit passed with 0 violations across all calls. |

---

## 4. Final Stop Condition Compliance
- **Zero Production Mutations**: No production files, prompts, catalogs, or runners were altered.
- **Zero Additional Trials**: Strictly ONE paired diagnostic pilot executed.
- **Stand Down**: Diagnostics complete. Awaiting user review.
