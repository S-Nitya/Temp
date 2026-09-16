# Minimal Perishability Benchmark: MAS vs LinearDecay

## 1. Executive Summary Table

| Metric                     | MAS (Mean ± Std)   | LinearDecay (Mean ± Std)   |
|:---------------------------|:-------------------|:---------------------------|
| True Net Profit ($)        | $-24.05 ± $28.65   | $-19.41 ± $1.93            |
| Gross Profit ($)           | $12.20 ± $10.89    | $9.59 ± $1.92              |
| Spoilage Loss ($)          | $36.25 ± $17.75    | $29.00 ± $0.00             |
| Profit Capture Ratio (PCR) | 0.7351 ± 0.0852    | 0.4704 ± 0.0779            |
| Clearance Rate (%)         | 36.7%              | 46.7%                      |
| Avg Sale Price / Retail    | 0.8916             | 0.7690                     |
| Instant Clear Rate (%)     | 26.7%              | 3.3%                       |
| Negotiated Sale Rate (%)   | 10.0%              | 43.3%                      |
| Walk Away Rate (%)         | 63.3%              | 53.3%                      |
| Total Tokens               | 59,767             | 5,495                      |
| Tokens / Sold Item         | 27772.5            | 785.0                      |
| Profit / 1000 Tokens ($)   | $-0.5118           | $-3.5246                   |

---

## 2. Perishability Regime Analysis

| Expiry Regime | MAS Sold Rate | MAS Net Profit | MAS Spoilage | MAS PCR | LinearDecay Sold Rate | LinearDecay Net Profit | LinearDecay Spoilage | LinearDecay PCR |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Critical (12-36h) | 3/10 | $-12.22 | $14.50 | 0.6750 | 4/10 | $-2.75 | $8.00 | 0.7291 |
| Medium (48-120h) | 5/10 | $-3.08 | $8.50 | 0.8333 | 6/10 | $-2.00 | $5.00 | 0.3333 |
| Low (144-336h) | 3/10 | $-8.76 | $13.25 | 0.8872 | 4/10 | $-14.66 | $16.00 | 0.4171 |

---

## 3. Cryptographic Hashes & Verification Metadata
- **Catalog Items Count**: 15 fixed items
- **Catalog SHA-256**: `b49a8fd50c2f8e7ee50eaec073056318bf306e5765c2b4b3fb51eaadc5469996`
- **Trial 1 Seed & Buyer Hash**: Seed `142`, Hash `61015d3106014ff28b67f98f844be3f257c41248f4abc6967333e410ba7f9257`
- **Trial 2 Seed & Buyer Hash**: Seed `242`, Hash `f40169ccec2dd8b09ef1bd98a75f26fa70c167e4bcfbd9cd704cb2d6f74fe680`
- **Privacy Audit Status**: **PASSED (0 Leaks Detected)**
