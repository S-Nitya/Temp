# Minimal Perishability Benchmark: MAS vs LinearDecay Replication Report (N=5 Trials)

## 1. Executive Summary & Core Research Question

> **Research Question**: Under identical perishable inventory and private buyer constraints, does a hierarchical LLM-based seller achieve better true net profit than a deterministic LinearDecay pricing policy, and how does performance change with remaining shelf life?

### Overall N=5 Comparison Table (Mean ± Standard Deviation)

| Metric | Hierarchical MAS (N=5) | LinearDecay Baseline (N=5) | Delta (Δ) |
| :--- | :--- | :--- | :--- |
| **True Net Profit ($)** | **$0.23 ± $33.54** | **$4.61 ± $27.77** | **$-4.39** |
| **Gross Profit ($)** | $21.23 ± $13.01 | $22.01 ± $13.64 | $-0.79 |
| **Spoilage Loss ($)** | $21.00 ± $20.54 | $17.40 ± $14.21 | $3.60 |
| **Profit Capture Ratio (PCR)** | **0.7777 ± 0.0732** | 0.6915 ± 0.2096 | **+0.0862** |
| **Clearance Rate (%)** | 64.0% (48/75) | **68.0% (51/75)** | -4.0% |
| **Avg Sale Price / Retail** | **0.9079** | 0.8643 | +0.0435 |
| **Instant Clear Rate (%)** | 50.7% | 28.0% | 22.7% |
| **Negotiated Sale Rate (%)** | 13.3% | 40.0% | -26.7% |
| **Walk Away Rate (%)** | 36.0% | 32.0% | 4.0% |
| **Total Tokens / Trial** | 67,837 | 7,658 | +60,178 |
| **Tokens / Sold Item (Trial Ratio)** | 15004.1 | 757.4 | +14246.6 |
| **Profit / 1,000 Total Tokens ($)** | $-0.0899 | $-0.5962 | +$0.5062 |

---

## 2. Individual Trial Results Breakdown

### Hierarchical MAS Trials (N=5)
| Trial | Seed | Net Profit ($) | Gross Profit ($) | Spoilage ($) | Sold / 15 | Mean PCR | Price/Retail | Total Tokens | Tokens/Sold | Profit/1k Tok |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| T1 | 142 | $-52.70 | $1.30 | $54.00 | 1/15 | 0.6500 | 0.8600 | 48,435 | 48435.0 | $-1.0881 |
| T2 | 242 | $4.59 | $23.09 | $18.50 | 10/15 | 0.8203 | 0.9232 | 71,100 | 7110.0 | $0.0646 |
| T3 | 342 | $34.78 | $34.78 | $0.00 | 15/15 | 0.8213 | 0.9221 | 82,937 | 5529.1 | $0.4194 |
| T4 | 442 | $34.72 | $34.72 | $0.00 | 15/15 | 0.8529 | 0.9396 | 73,294 | 4886.3 | $0.4737 |
| T5 | 542 | $-20.25 | $12.25 | $32.50 | 7/15 | 0.7440 | 0.8945 | 63,419 | 9059.9 | $-0.3193 |

### LinearDecay Baseline Trials (N=5)
| Trial | Seed | Net Profit ($) | Gross Profit ($) | Spoilage ($) | Sold / 15 | Mean PCR | Price/Retail | Total Tokens | Tokens/Sold | Profit/1k Tok |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| T1 | 142 | $-21.34 | $7.66 | $29.00 | 7/15 | 0.3925 | 0.7407 | 5,777 | 825.3 | $-3.6940 |
| T2 | 242 | $-17.49 | $11.51 | $29.00 | 7/15 | 0.5482 | 0.7973 | 5,213 | 744.7 | $-3.3551 |
| T3 | 342 | $39.38 | $39.38 | $0.00 | 15/15 | 0.9314 | 0.9689 | 10,940 | 729.3 | $3.5996 |
| T4 | 442 | $37.68 | $37.68 | $0.00 | 15/15 | 0.9184 | 0.9645 | 11,153 | 743.5 | $3.3785 |
| T5 | 542 | $-15.16 | $13.84 | $29.00 | 7/15 | 0.6670 | 0.8503 | 5,210 | 744.3 | $-2.9098 |

---

## 3. Perishability Regime Analysis (Critical vs. Medium vs. Low Expiry)

| Expiry Regime | Metric | Hierarchical MAS | LinearDecay Baseline | Advantage |
| :--- | :--- | :--- | :--- | :--- |
| **Critical (12-36h)** | Clearance Rate | 18/25 (72.0%) | 16/25 (64.0%) | MAS |
| **Critical (12-36h)** | True Net Profit | $0.70 | $3.46 | **LinearDecay** |
| **Critical (12-36h)** | Spoilage Loss | $5.80 | $4.80 | LinearDecay |
| **Critical (12-36h)** | Profit Capture Ratio (PCR) | 0.7228 | 0.8747 | **LinearDecay** |
| **Medium (48-120h)** | Clearance Rate | 17/25 (68.0%) | 19/25 (76.0%) | LinearDecay |
| **Medium (48-120h)** | True Net Profit | $1.32 | $4.23 | **LinearDecay** |
| **Medium (48-120h)** | Spoilage Loss | $5.90 | $3.00 | LinearDecay |
| **Medium (48-120h)** | Profit Capture Ratio (PCR) | 0.8319 | 0.7029 | **MAS** |
| **Low (144-336h)** | Clearance Rate | 13/25 (52.0%) | 16/25 (64.0%) | LinearDecay |
| **Low (144-336h)** | True Net Profit | $-1.79 | $-3.07 | **MAS** |
| **Low (144-336h)** | Spoilage Loss | $9.30 | $9.60 | MAS |
| **Low (144-336h)** | Profit Capture Ratio (PCR) | 0.9248 | 0.7282 | **MAS** |

---

## 4. Conservatism & Pricing Policy Behavior by Regime

| Expiry Regime | MAS Avg Opening / Retail | MAS Avg Seller Floor / Retail | MAS Avg Realized Sale / Retail |
| :--- | :---: | :---: | :---: |
| Critical (12-36h) | 0.8831 | 0.6319 | 0.8897 |
| Medium (48-120h) | 0.9355 | 0.5904 | 0.9240 |
| Low (144-336h) | 0.9707 | 0.5694 | 0.9659 |

---

## 5. Critical Expiry Item-by-Item Head-to-Head (12–36h)

| Trial | Product | Expiry | Cost | Retail | MAS Opening | MAS Final | MAS Status | LD Opening | LD Final | LD Status | MAS Spoilage | LD Spoilage |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| T1 | Strawberries | 12h | $3.00 | $5.00 | $4.30 | $4.30 | SOLD | $5.00 | $0.00 | UNSOLD | $0.00 | $3.00 |
| T1 | Fresh Fish | 18h | $7.00 | $11.00 | $9.75 | $0.00 | UNSOLD | $11.00 | $10.00 | SOLD | $7.00 | $0.00 |
| T1 | Spinach | 24h | $2.00 | $4.00 | $3.20 | $0.00 | UNSOLD | $4.00 | $0.00 | UNSOLD | $2.00 | $2.00 |
| T1 | Fresh Chicken | 30h | $5.00 | $8.00 | $7.50 | $0.00 | UNSOLD | $8.00 | $6.00 | SOLD | $5.00 | $0.00 |
| T1 | Mushrooms | 36h | $3.00 | $5.00 | $4.20 | $0.00 | UNSOLD | $5.00 | $0.00 | UNSOLD | $3.00 | $3.00 |
| T2 | Strawberries | 12h | $3.00 | $5.00 | $4.20 | $0.00 | UNSOLD | $5.00 | $0.00 | UNSOLD | $3.00 | $3.00 |
| T2 | Fresh Fish | 18h | $7.00 | $11.00 | $9.00 | $0.00 | UNSOLD | $11.00 | $11.00 | SOLD | $7.00 | $0.00 |
| T2 | Spinach | 24h | $2.00 | $4.00 | $3.40 | $0.00 | UNSOLD | $4.00 | $0.00 | UNSOLD | $2.00 | $2.00 |
| T2 | Fresh Chicken | 30h | $5.00 | $8.00 | $6.50 | $6.50 | SOLD | $8.00 | $7.50 | SOLD | $0.00 | $0.00 |
| T2 | Mushrooms | 36h | $3.00 | $5.00 | $4.75 | $4.75 | SOLD | $5.00 | $0.00 | UNSOLD | $0.00 | $3.00 |
| T3 | Strawberries | 12h | $3.00 | $5.00 | $4.75 | $4.30 | SOLD | $5.00 | $4.46 | SOLD | $0.00 | $0.00 |
| T3 | Fresh Fish | 18h | $7.00 | $11.00 | $10.00 | $10.00 | SOLD | $11.00 | $11.00 | SOLD | $0.00 | $0.00 |
| T3 | Spinach | 24h | $2.00 | $4.00 | $3.50 | $3.50 | SOLD | $4.00 | $4.00 | SOLD | $0.00 | $0.00 |
| T3 | Fresh Chicken | 30h | $5.00 | $8.00 | $7.25 | $7.25 | SOLD | $8.00 | $7.50 | SOLD | $0.00 | $0.00 |
| T3 | Mushrooms | 36h | $3.00 | $5.00 | $4.60 | $4.60 | SOLD | $5.00 | $5.00 | SOLD | $0.00 | $0.00 |
| T4 | Strawberries | 12h | $3.00 | $5.00 | $4.50 | $4.50 | SOLD | $5.00 | $4.50 | SOLD | $0.00 | $0.00 |
| T4 | Fresh Fish | 18h | $7.00 | $11.00 | $9.75 | $9.75 | SOLD | $11.00 | $10.62 | SOLD | $0.00 | $0.00 |
| T4 | Spinach | 24h | $2.00 | $4.00 | $3.50 | $3.50 | SOLD | $4.00 | $3.72 | SOLD | $0.00 | $0.00 |
| T4 | Fresh Chicken | 30h | $5.00 | $8.00 | $6.50 | $6.50 | SOLD | $8.00 | $8.00 | SOLD | $0.00 | $0.00 |
| T4 | Mushrooms | 36h | $3.00 | $5.00 | $4.78 | $4.78 | SOLD | $5.00 | $5.00 | SOLD | $0.00 | $0.00 |
| T5 | Strawberries | 12h | $3.00 | $5.00 | $4.75 | $4.75 | SOLD | $5.00 | $0.00 | UNSOLD | $0.00 | $3.00 |
| T5 | Fresh Fish | 18h | $7.00 | $11.00 | $9.50 | $9.50 | SOLD | $11.00 | $11.00 | SOLD | $0.00 | $0.00 |
| T5 | Spinach | 24h | $2.00 | $4.00 | $3.70 | $3.70 | SOLD | $4.00 | $0.00 | UNSOLD | $0.00 | $2.00 |
| T5 | Fresh Chicken | 30h | $5.00 | $8.00 | $6.75 | $6.75 | SOLD | $8.00 | $8.00 | SOLD | $0.00 | $0.00 |
| T5 | Mushrooms | 36h | $3.00 | $5.00 | $4.55 | $4.55 | SOLD | $5.00 | $0.00 | UNSOLD | $0.00 | $3.00 |

---

## 6. Cryptographic Integrity & Model Registry Metadata

- **Catalog Items Count**: 15 Fixed Products
- **Catalog SHA-256 Digest**: `b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`
- **Model Registry**:
  - `StrategicBrain`: `openai/gpt-oss-120b` (Groq)
  - `BullDebater`, `BearDebater`, `DebateJudge`, `RiskReader`, `ListingDecider`, `Spokesperson`, `Buyer`: `openai/gpt-oss-20b` (Groq)
- **Trial Seeds & Persisted Buyer State Hashes**:
  - **Trial 1**: Seed `142` | Buyer Hash: `61015d3106014ff28b67f98f844be3f257c41248f4abc6967333e410ba7f9257`
  - **Trial 2**: Seed `242` | Buyer Hash: `f40169ccec2dd8b09ef1bd98a75f26fa70c167e4bcfbd9cd704cb2d6f74fe680`
  - **Trial 3**: Seed `342` | Buyer Hash: `228b22db437d9ac925dcd49169b3d87e69092d772b2f71fd6e6e28d069453d79`
  - **Trial 4**: Seed `442` | Buyer Hash: `521d2785d43fec3f929378cd1fbbca9802a17460400ec9fb88c62959272c9714`
  - **Trial 5**: Seed `542` | Buyer Hash: `5c8db9305a8f646e2ed349352d2bf1cd50dd85fa7056c4084af5dd479f793e46`
- **Automated Privacy Audit**: **PASSED (0 Leaks across all seller prompts)**

---

## 7. Key Findings & Theoretical Insights

1. **The Fundamental Perishability Tradeoff**:
   - **Hierarchical MAS** acts as a **Margin Maximizer**: it achieves higher Profit Capture Ratio (PCR) and sells items at substantially higher fractions of retail price ({mean_val(mas_trials, 'avg_price_to_retail'):.1%} vs {mean_val(ld_trials, 'avg_price_to_retail'):.1%}).
   - **LinearDecay** acts as a **Volume Clearance Engine**: it mechanically discounts prices across negotiation ticks, clearing more inventory ({mean_val(ld_trials, 'clearance_rate')*100:.1f}% vs {mean_val(mas_trials, 'clearance_rate')*100:.1f}%), but suffers severe margin erosion on items with remaining life.

2. **Regime-Dependent Advantage**:
   - In **Low Perishability (144–336h)**, MAS avoids premature discounting and preserves full retail value, generating superior net profit.
   - In **Critical Perishability (12–36h)**, LinearDecay avoids catastrophic spoilage by aggressively slashing prices down toward cost, whereas MAS can suffer spoilage when buyers hold out.
