### 📊 Empirical Summary Table ($N$ Trials)

| Condition            |   N |   PCR_Mean |   PCR_Std | PCR_95_CI      |   Profit_Mean |   Profit_Std | Profit_95_CI   |   Waste_Mean |   Items_Sold_Mean |
|:---------------------|----:|-----------:|----------:|:---------------|--------------:|-------------:|:---------------|-------------:|------------------:|
| Full_MAS             |   2 |    1.04865 |  0.024678 | [1.031, 1.066] |         90.31 |       58.803 | [48.7, 131.9]  |       322.72 |              10.5 |
| LinearDecay_Baseline |   1 |    1.2064  |  0        | [1.206, 1.206] |        120.03 |        0     | [120.0, 120.0] |       266.61 |              10   |
| No_RiskReader        |   1 |    1.0596  |  0        | [1.060, 1.060] |         38.75 |        0     | [38.8, 38.8]   |       421.15 |              10   |
| No_StrategicBrain    |   1 |    1.0435  |  0        | [1.044, 1.044] |        133.81 |        0     | [133.8, 133.8] |       241.09 |              12   |

### 🔬 Hypothesis Testing vs Full_MAS

| Comparison                       |   Delta_PCR |   Welch_p_PCR |   Wilcoxon_p_PCR |   Cohen_d_PCR |   Delta_Profit |   Welch_p_Profit |   Cohen_d_Profit |
|:---------------------------------|------------:|--------------:|-----------------:|--------------:|---------------:|-----------------:|-----------------:|
| Full_MAS vs LinearDecay_Baseline |    -0.15775 |             1 |                1 |             0 |         -29.72 |                1 |                0 |
| Full_MAS vs No_RiskReader        |    -0.01095 |             1 |                1 |             0 |          51.56 |                1 |                0 |
| Full_MAS vs No_StrategicBrain    |     0.00515 |             1 |                1 |             0 |         -43.5  |                1 |                0 |
