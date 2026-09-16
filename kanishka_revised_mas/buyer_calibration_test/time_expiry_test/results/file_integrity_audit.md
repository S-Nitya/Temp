# Benchmark File Integrity Audit

**Test Directory**: `kanishka_revised_mas/buyer_calibration_test/time_expiry_test/`  
**Execution Timestamp**: 2026-09-14  
**Audit Purpose**: Verify that production benchmark files are 100% untouched and READ-ONLY.

| Production File | SHA-256 Checksum | Modification Status |
| :--- | :--- | :---: |
| `kanishka_revised_mas/catalog.py` | `2079beec61a77225881054ed1b533e54cd251fa5275f0d6a85137764bb921fee` | **UNTOUCHED (READ-ONLY)** |
| `kanishka_revised_mas/buyer.py` | `c861ade4340eedbf271694b51a4a1729bd973d408d5cbd67061110f19e911164` | **UNTOUCHED (READ-ONLY)** |
| `kanishka_revised_mas/mas_agents.py` | `14a6ce2b09fb81fb3b7b55bc79073786a661b52b96ab8a13421d03b3cb12005b` | **UNTOUCHED (READ-ONLY)** |
| `kanishka_revised_mas/environment.py` | `9a43ed117e4c228b26dfaf2c3d83a7e5b599b38471f83bbedb23e43f9ae28747` | **UNTOUCHED (READ-ONLY)** |
| `kanishka_revised_mas/linear_decay.py` | `6ecd56198edda65da874acbdcdf26064aeac27d4e49b69fc2ffeee4853183518` | **UNTOUCHED (READ-ONLY)** |
| `kanishka_revised_mas/runner.py` | `afab4bda4d9c8939fd679326bb94f7d29387a1d7dde1530203f64d5fb7411039` | **UNTOUCHED (READ-ONLY)** |

### Integrity Verification Summary
- **Zero Production Overwrites**: All diagnostic code and output artifacts are strictly confined to `kanishka_revised_mas/buyer_calibration_test/time_expiry_test/`.
- **Zero Production Mutations**: No imports mutated global configuration.
- **Production Benchmark Integrity**: The validated final $N=5$ benchmark in `kanishka_revised_mas/results/final_run/` remains final, valid, and fully intact.
