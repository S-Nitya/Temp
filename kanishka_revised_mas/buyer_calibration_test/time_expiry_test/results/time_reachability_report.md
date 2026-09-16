# Isolated Time / Expiry Reachability Report

**Date**: 2026-09-14  
**Scope**: Clock Mechanics & Physical Expiry Reachability Diagnostics  
**Catalog SHA-256**: `b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`  
**Status**: COMPLETE (Deterministic Diagnostics, Zero LLM Tokens Consumed)

---

## 1. Executive Summary: Primary 5 Items Reachability Table

| Item | Expiry | Time / Epoch | Epochs to Expiry | Reachable in Current Benchmark? |
| :--- | :---: | :---: | :---: | :---: |
| **Strawberries** | 12h | 3.0h | 4 | **NO** |
| **Fresh Fish** | 18h | 3.0h | 6 | **NO** |
| **Spinach** | 24h | 3.0h | 8 | **NO** |
| **Fresh Chicken** | 30h | 3.0h | 10 | **NO** |
| **Hard Cheese** | 336h | 3.0h | 112 | **NO** |

> **Core Diagnostic Conclusion**:  
> In the current benchmark architecture, **physical product expiry is mathematically unreachable for 100% of catalog items (0/15)**. Even the shortest-lived product in the catalog (Strawberries at 12 hours) requires **4 full negotiation epochs** (12 exchanges) to reach expiry, but the benchmark execution policy permits exactly **1 epoch (maximum 3 exchanges = 3.0 hours)** per item.

---

## 2. Code-Level Inspection: Current Time Increments

Direct inspection of `kanishka_revised_mas/environment.py` and `kanishka_revised_mas/runner.py` reveals the exact clock rules:

1. **Time advance per exchange**:  
   - **`1.0 hour`** (`self.time_per_exchange = 1.0` in `NegotiationEnvironment.__init__`).  
   - Every exchange turn increment in the negotiation loop executes: `current_simulated_time += self.time_per_exchange`.
2. **Time advance per epoch**:  
   - **`0.0 hours`** if buyer executes instant `ACCEPT` at opening evaluation (Exchange 0).  
   - **`1.0 hour`** if buyer executes immediate `WALK_AWAY` or `INVALID_BUYER_RESPONSE` at opening evaluation.  
   - **`1.0 to 3.0 hours`** for negotiated exchanges (1.0h per exchange turn).  
   - **`3.0 hours`** for a full 3-exchange epoch (`max_exchanges = 3`).
3. **Time advance after maximum rounds**:  
   - **`3.0 hours`** total simulated elapsed time.
4. **Time advance after buyer walk-away**:  
   - Opening walk-away: **`1.0 hour`**.  
   - Negotiated walk-away at exchange $k$: **`k * 1.0 hour`** (max 3.0h).
5. **Time advance after unresolved negotiation**:  
   - **`3.0 hours`** (`current_simulated_time = 3.0`, remaining shelf life = `expiry - 3.0`).

---

## 3. Full 15-Item Catalog Reachability Matrix

| Product Name | Expiry | Regime | Time/Epoch | Epochs Needed | Exchanges Needed | Max Benchmark Time | Min Remaining Life | Reachable in Benchmark? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Strawberries | 12h | Critical | 3.0h | 4 | 12 | 3.0h | 9.0h | **NO** |
| Fresh Fish | 18h | Critical | 3.0h | 6 | 18 | 3.0h | 15.0h | **NO** |
| Spinach | 24h | Critical | 3.0h | 8 | 24 | 3.0h | 21.0h | **NO** |
| Fresh Chicken | 30h | Critical | 3.0h | 10 | 30 | 3.0h | 27.0h | **NO** |
| Mushrooms | 36h | Critical | 3.0h | 12 | 36 | 3.0h | 33.0h | **NO** |
| Fresh Bread | 48h | Medium | 3.0h | 16 | 48 | 3.0h | 45.0h | **NO** |
| Tomatoes | 60h | Medium | 3.0h | 20 | 60 | 3.0h | 57.0h | **NO** |
| Ground Beef | 72h | Medium | 3.0h | 24 | 72 | 3.0h | 69.0h | **NO** |
| Yogurt | 96h | Medium | 3.0h | 32 | 96 | 3.0h | 93.0h | **NO** |
| Soft Cheese | 120h | Medium | 3.0h | 40 | 120 | 3.0h | 117.0h | **NO** |
| Premium Beef | 144h | Low | 3.0h | 48 | 144 | 3.0h | 141.0h | **NO** |
| Fresh Juice | 168h | Low | 3.0h | 56 | 168 | 3.0h | 165.0h | **NO** |
| Apples | 192h | Low | 3.0h | 64 | 192 | 3.0h | 189.0h | **NO** |
| Carrots | 240h | Low | 3.0h | 80 | 240 | 3.0h | 237.0h | **NO** |
| Hard Cheese | 336h | Low | 3.0h | 112 | 336 | 3.0h | 333.0h | **NO** |

---

## 4. Synthetic Expiry State Machine Verification

To verify that the underlying state machine in `NegotiationEnvironment` functions correctly when physical time does cross expiry, an independent synthetic unit test was executed (`Strawberries`, Cost: $3.00, Retail: $5.00, Expiry: 12.0h):

1. **Before Expiry ($t = 11.0$h, 1h remaining)**:  
   - State: `IN_PROGRESS` (Not Expired)  
   - Spoilage Loss: **$0.00**  
   - Assertion: **PASSED**
2. **At Exact Expiry ($t = 12.0$h, 0h remaining)**:  
   - State: **`EXPIRED`**  
   - Spoilage Loss: **$3.00** (Full Cost)  
   - Net Profit: **-$3.00**  
   - Assertion: **PASSED**
3. **Post-Expiry ($t = 13.0$h, 0h remaining)**:  
   - State: **`EXPIRED`** (Terminal State Preserved)  
   - Spoilage Loss: **$3.00**  
   - Assertion: **PASSED**

### Separation of Concepts Verification
- **Round Limit != Expiry**: 3 exchanges elapsed on an 18h item results in `MAX_ROUNDS_UNRESOLVED` with **$0.00 spoilage loss** (Remaining shelf life = 15.0h). **PASSED**.
- **Time causes Expiry**: Unsold inventory when physical time >= expiry triggers `EXPIRED` with **Spoilage = Cost**. **PASSED**.
- **Sold Items Never Spoil**: Sale agreed at $t = 11.5$h (0.5h before expiry) yields `SOLD`, **Spoilage = $0.00**, Profit = **+$1.50**. **PASSED**.
- **Early Walk-Away != Spoilage**: Buyer walk-away at $t = 1.0$h on a 30h item yields `BUYER_WALK_AWAY` with **$0.00 spoilage loss** (Remaining shelf life = 29.0h). **PASSED**.

---

## 5. Explicit Answers to the 6 Required Questions

### Question 1: What is the current simulated time increment?
> **`1.0 hour per exchange`** (`time_per_exchange = 1.0`).  
> A full unresolved negotiation epoch advances simulated time by exactly **`3.0 hours`** (3 exchanges × 1.0h). An immediate opening walk-away advances simulated time by **`1.0 hour`**.

### Question 2: How many epochs are required for each expiry horizon?
> - **12h Expiry (Strawberries)**: **4 full epochs** (12 exchanges).
> - **18h Expiry (Fresh Fish)**: **6 full epochs** (18 exchanges).
> - **24h Expiry (Spinach)**: **8 full epochs** (24 exchanges).
> - **30h Expiry (Fresh Chicken)**: **10 full epochs** (30 exchanges).
> - **336h Expiry (Hard Cheese)**: **112 full epochs** (336 exchanges).

### Question 3: Can the current benchmark naturally reach 12h expiry?
> **NO.**  
> The current benchmark architecture executes exactly **1 epoch per item** against a single buyer. In a single epoch, maximum elapsed time is **3.0 hours**. For Strawberries (12.0h shelf life), a full 3-exchange unresolved negotiation leaves **9.0 hours of shelf life remaining**. Consequently, Strawberries can never naturally reach expiry in the current benchmark.

### Question 4: Can it naturally reach 336h expiry?
> **NO.**  
> Reaching 336h expiry requires **112 consecutive unresolved epochs** (336 exchanges). With a 1-epoch limit per item, the maximum time elapsed is 3.0 hours, leaving **333.0 hours of remaining shelf life**.

### Question 5: Is physical expiry actually capable of becoming a binding economic constraint?
> **NO, not under the current clock configuration and interaction policy.**  
> Because the benchmark restricts each item to a single 1-on-1 encounter with at most 3 exchanges, simulated time can never exceed 3.0 hours. Because the minimum shelf life across the entire 15-product catalog is 12.0 hours (12.0h > 3.0h), **physical expiry can never bind, and true terminal spoilage loss can never occur** during natural benchmark runs.

### Question 6: If not, is the limitation caused by the clock configuration rather than the LLM?
> **YES, ENTIRELY.**  
> The limitation is **100% structural and clock-driven**, not an LLM failure:
> 1. The LLMs (both buyer and seller) successfully negotiated, countered, and walked away.
> 2. The expiry state machine logic itself is mathematically and logically sound (as verified in Section 4).
> 3. However, the clock parameters (1.0h per exchange, maximum 3 exchanges per epoch, and strictly 1 epoch per item) establish an unreachable ceiling of 3.0h on physical elapsed time, while the catalog shelf lives range from 12h to 336h.

---

## 6. Freeze Rule Compliance
- **Zero Production Modifications**: No production files, prompts, catalogs, or runners were altered.
- **Zero Additional Trials**: No $N=5$ trials, no re-calibrations, and no heuristics were executed.
- **Diagnostic Complete**: Standing down as instructed.
