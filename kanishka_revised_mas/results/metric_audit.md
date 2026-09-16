# Independent Metric Audit & Verification Report

**Date**: 2026-09-08  
**Scope**: Verification of raw item-level records vs. summary aggregation logic for Trials 1 & 2 across `MAS` and `LinearDecay`.

---

## 1. Summary of Identified Discrepancies & Resolutions

| Metric | Stored / Reported Summary Value | Recomputed Value (Item/Trial Level) | Recomputed Pooled Value | Mathematical Cause | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MAS Tokens / Sold Item** | `27,772.5` | T1: `48,435.0`<br>T2: `7,110.0`<br>Mean: `27,772.5 ± 20,662.5` | `10,866.8` (119,535 tokens / 11 sold items) | Macro-average of trial ratios vs Pooled micro-average. (T1 had 1 sale $\to$ 48.4k tokens/sold; T2 had 10 sales $\to$ 7.1k tokens/sold). | **RESOLVED & DISAMBIGUATED** |
| **MAS Profit / 1k Total Tokens ($)** | `-$0.5118` | T1: `-$1.0881`<br>T2: `+$0.0646`<br>Mean: `-$0.5118 ± $0.5763` | `-$0.4025` (-$48.11 / 119.535k tokens) | Macro-average of trial efficiency ratios vs Pooled net profit / total pooled tokens. | **RESOLVED & DISAMBIGUATED** |
| **LinearDecay Tokens / Sold Item** | `785.0` | T1: `825.3`<br>T2: `744.7`<br>Mean: `785.0 ± 40.3` | `785.0` (10,990 tokens / 14 sold items) | Matches macro-average (both trials had exactly 7 sales). | **VERIFIED** |
| **LinearDecay Profit / 1k Tokens ($)** | `-$3.5246` | T1: `-$3.6940`<br>T2: `-$3.3551`<br>Mean: `-$3.5246 ± $0.1695` | `-$3.5332` (-$38.83 / 10.990k tokens) | Macro-average of trial ratios vs Pooled micro-average. | **RESOLVED & DISAMBIGUATED** |

---

## 2. Validation of Core Economic Accounting Identities

### True Net Profit Identity: $\text{True Net Profit} = \text{Gross Profit} - \text{Spoilage Loss}$

For every individual item $i \in \{1 \dots 15\}$:
$$\text{Contribution}_i = \begin{cases} P_{\text{sale}, i} - P_{\text{cost}, i} & \text{if SOLD} \\ -P_{\text{cost}, i} & \text{if UNSOLD (Spoiled)} \end{cases}$$

$$\text{Gross Profit} = \sum_{i \in \text{SOLD}} (P_{\text{sale}, i} - P_{\text{cost}, i}), \quad \text{Spoilage Loss} = \sum_{i \in \text{UNSOLD}} P_{\text{cost}, i}$$

#### Audit Check Across Checkpoint Files:
- **MAS Trial 1**:
  - Sold Items: 1 (Strawberries, $P_{\text{sale}} = \$4.30, P_{\text{cost}} = \$3.00 \to \text{Gross} = +\$1.30$)
  - Unsold Items: 14 ($\text{Spoilage Loss} = \$54.00$)
  - $\text{True Net Profit} = \$1.30 - \$54.00 = -\$52.70$ (Identity holds exactly: $1.30 - 54.00 = -52.70$)
- **MAS Trial 2**:
  - Sold Items: 10 ($\text{Gross Profit} = \$23.09$)
  - Unsold Items: 5 (Strawberries, Fresh Fish, Spinach, Carrots, Hard Cheese $\to \text{Spoilage Loss} = \$18.50$)
  - $\text{True Net Profit} = \$23.09 - \$18.50 = +\$4.59$ (Identity holds exactly: $23.09 - 18.50 = +4.59$)
- **LinearDecay Trial 1**:
  - Sold Items: 7 ($\text{Gross Profit} = \$7.66$)
  - Unsold Items: 8 ($\text{Spoilage Loss} = \$29.00$)
  - $\text{True Net Profit} = \$7.66 - \$29.00 = -\$21.34$ (Identity holds exactly: $7.66 - 29.00 = -21.34$)
- **LinearDecay Trial 2**:
  - Sold Items: 7 ($\text{Gross Profit} = \$11.51$)
  - Unsold Items: 8 ($\text{Spoilage Loss} = \$29.00$)
  - $\text{True Net Profit} = \$11.51 - \$29.00 = -\$17.49$ (Identity holds exactly: $11.51 - 29.00 = -17.49$)

---

## 3. Profit Capture Ratio (PCR) Verification

$$\text{Item PCR} = \frac{P_{\text{sale}} - P_{\text{cost}}}{P_{\text{retail}} - P_{\text{cost}}}$$

- **Item Level**: Recomputed directly from raw transaction logs for all sold items. All values match $100\%$ within $10^{-6}$ numerical tolerance.
- **Trial Mean PCR**: Arithmetic mean of Item PCR values over completed sales in that trial.
  - MAS T1: $0.6500$ ($1$ sale)
  - MAS T2: $0.8203$ ($10$ sales)
  - LinearDecay T1: $0.3925$ ($7$ sales)
  - LinearDecay T2: $0.5482$ ($7$ sales)
- **Zero Sold Items Policy**: If a trial has $0$ sales, Trial Mean PCR returns `NA` (not $0.0000$ or $1.0000$) to prevent skewing condition aggregates.

---

## 4. Token Efficiency Metric Definitions & Denominators

To eliminate all ambiguity in multi-trial reporting:
1. **Total LLM Tokens**: $\text{Prompt Tokens} + \text{Completion Tokens}$ across all model calls in the trial.
2. **Buyer Tokens**: Tokens consumed exclusively by the autonomous Buyer agent.
3. **Seller MAS Tokens**: Tokens consumed by MAS seller agents (`StrategicBrain`, `BullDebater`, `BearDebater`, `DebateJudge`, `RiskReader`, `ListingDecider`, `Spokesperson`).
4. **Tokens per Item Transaction**: $\frac{\text{Total Tokens in Trial}}{15}$.
5. **Tokens per Sold Item (Trial Ratio)**: $\frac{\text{Total Tokens in Trial}}{\text{Number of Sold Items in Trial}}$ (or `NA` if $0$ sold).
6. **Tokens per Sold Item (Pooled)**: $\frac{\sum \text{Total Tokens across All Trials}}{\sum \text{Sold Items across All Trials}}$.
7. **Profit per 1,000 Total Tokens ($)**: $\frac{\text{True Net Profit}}{(\text{Total Tokens} / 1000)}$.
8. **Profit per 1,000 Seller Tokens ($)**: $\frac{\text{True Net Profit}}{(\text{Seller MAS Tokens} / 1000)}$ (`NA` for LinearDecay as seller uses deterministic code).
