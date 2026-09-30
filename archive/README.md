# Legacy Archive

This directory contains historical, exploratory, and superseded artifacts from earlier stages of the project. These files are preserved for historical record, provenance, and auditability, but are **not** part of the active, production-ready research breakthrough.

---

## Active & Authoritative Research Locations

For all current, publication-ready code, data, and evaluations, please refer directly to the following root directories:

1. **Production MAS Codebase**: [`kanishka_revised_mas/`](../kanishka_revised_mas/)
   - Multi-Agent System (`mas_agents.py`)
   - Adaptive Environment (`environment.py`)
   - Heterogeneous Calibrated Buyer Population (`buyer.py`)
   - Perishable 15-Item Inventory Catalog (`catalog.py`)
   - Linear Decay Benchmark (`linear_decay.py`)
   - Production Runner & Benchmark Scripts (`runner.py`, `run_final_benchmark.py`, `replicate_n5.py`)
   - Buyer Calibration & Diagnostic Pilots (`buyer_calibration_test/`)

2. **Benchmark Results & Reports**: [`results/`](../results/)
   - Final Benchmark Executive Report (`final_benchmark_report.md`)
   - Cryptographic Integrity Audit (`final_integrity_audit.md`)
   - Final Summary Metrics (`final_summary.csv`)
   - Perishability & Expiry Diagnostics (`final_perishability_analysis.csv`, `final_mas_expiry_diagnostics.csv`)
   - Token & Efficiency Metrics (`final_token_analysis.csv`)

3. **Theoretical Positioning & Limitations**: [`docs/`](../docs/)
   - Research positioning, competitive benchmarks, and real-world system boundaries.

---

## Archived Contents Directory

| Subdirectory / File | Description | Reason for Archiving |
| :--- | :--- | :--- |
| `final_architecture/` | Early ablation and multi-agent implementation | Superseded by the modular, deterministic `kanishka_revised_mas/` architecture. |
| `kanishka_src/` | Intermediate experimental iterations (DSPy, listing agents, etc.) | Prototyping code superseded by the validated benchmark engine. |
| `src/` | Initial 6-agent / baseline setup | Superseded by the formal 3-agent MAS (RiskReader, StrategicBrain, DynamicPricer). |
| `legacy_results/` | Initial ablation runs and early checkpoints | Replaced by the clean, audited N=5 benchmark in `results/` and `kanishka_revised_mas/results/`. |
| `kanishka_output/` & `output/` | Legacy model traces, transcripts, and exploratory run dumps | Preserved for traceability; active runs output to `kanishka_revised_mas/`. |
| `perishable_goods_management.csv` | 21MB legacy synthetic dataset | Superseded by the standardized 15-item catalog in `catalog.py`. |
| `plotting.py` & `stats_analysis.py` | Legacy standalone analysis scripts | Replaced by integrated benchmark analytics and summary outputs. |
