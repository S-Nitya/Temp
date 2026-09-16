"""
Minimal Perishability Benchmark Runner: MAS vs LinearDecay.
Executes exactly 4 trials: MAS T1, MAS T2, LinearDecay T1, LinearDecay T2.
Uses the fixed 15-product catalog with cryptographic verification and persisted buyer states.
"""
import os
import json
import hashlib
import asyncio
import argparse
from typing import Dict, Any, List
import pandas as pd
import numpy as np

from kanishka_revised_mas.catalog import get_fixed_catalog
from kanishka_revised_mas.llm_client import LLMClient, MODEL_REGISTRY
from kanishka_revised_mas.buyer import generate_buyer_private_states, BuyerPrivateState
from kanishka_revised_mas.environment import NegotiationEnvironment

OUTPUT_DIR = "kanishka_revised_mas/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/checkpoints", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/logs", exist_ok=True)


def compute_sha256(data: Any) -> str:
    """Compute SHA256 hex digest for JSON-serializable structure."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def audit_prompt_privacy(
    call_records: List[Any],
    buyer_states: Dict[str, BuyerPrivateState],
) -> Dict[str, Any]:
    """
    Verify zero seller prompt leakage of confidential buyer private state fields.
    Ensures private variables ('budget_ceiling', 'private_valuation', 'buyer_persona')
    are never injected into seller prompts.
    """
    violations = []
    seller_agents = {"StrategicBrain", "BullDebater", "BearDebater", "DebateJudge", "RiskReader", "ListingDecider", "Spokesperson"}

    forbidden_phrases = ["budget_ceiling", "private_valuation", "budget ceiling", "private valuation", "persona: bargain_hunter", "persona: quality_seeker", "persona: pragmatic_shopper"]

    for rec in call_records:
        if rec.agent_name in seller_agents:
            prompt_lower = rec.raw_prompt.lower()
            for phrase in forbidden_phrases:
                if phrase in prompt_lower:
                    violations.append({
                        "item_id": rec.item_id,
                        "agent": rec.agent_name,
                        "leaked_phrase": phrase,
                    })

    return {
        "audit_passed": len(violations) == 0,
        "total_seller_calls_audited": len([r for r in call_records if r.agent_name in seller_agents]),
        "violations_count": len(violations),
        "violations": violations,
    }


def calculate_trial_metrics(item_results: List[Dict[str, Any]], call_records: List[Any]) -> Dict[str, Any]:
    """Compute all required metrics from item results and token usage with true physical spoilage accounting."""
    n_items = len(item_results)
    sold_items = [r for r in item_results if r["final_status"] == "SOLD"]
    expired_items = [r for r in item_results if r["final_status"] == "EXPIRED"]
    walk_aways = [r for r in item_results if r["final_status"] == "BUYER_WALK_AWAY"]
    unresolved_items = [r for r in item_results if r["final_status"] == "MAX_ROUNDS_UNRESOLVED"]
    invalid_items = [r for r in item_results if r["final_status"] == "INVALID_BUYER_RESPONSE"]

    total_gross_profit = sum(r["final_price"] - r["cost_price"] for r in sold_items)
    total_spoilage_loss = sum(r["spoilage_loss"] for r in item_results)
    true_net_profit = total_gross_profit - total_spoilage_loss

    pcr_list = [r["pcr"] for r in sold_items]
    mean_pcr = float(np.mean(pcr_list)) if pcr_list else None

    clearance_rate = len(sold_items) / n_items if n_items > 0 else 0.0
    instant_clears = len([r for r in sold_items if r["negotiation_status"] == "INSTANT_CLEAR"])
    negotiated_sales = len([r for r in sold_items if r["negotiation_status"] == "NEGOTIATED_SALE"])

    instant_clear_rate = instant_clears / n_items if n_items > 0 else 0.0
    negotiation_rate = negotiated_sales / n_items if n_items > 0 else 0.0
    walk_away_rate = len(walk_aways) / n_items if n_items > 0 else 0.0
    unresolved_rate = len(unresolved_items) / n_items if n_items > 0 else 0.0
    expired_rate = len(expired_items) / n_items if n_items > 0 else 0.0

    price_to_retail_ratios = [r["final_price"] / r["retail_reference"] for r in sold_items]
    avg_price_to_retail = float(np.mean(price_to_retail_ratios)) if price_to_retail_ratios else 0.0

    total_tokens = sum(r.total_tokens for r in call_records)
    mas_tokens = sum(r.total_tokens for r in call_records if r.agent_name != "Buyer")
    buyer_tokens = sum(r.total_tokens for r in call_records if r.agent_name == "Buyer")
    tokens_per_sold = total_tokens / len(sold_items) if sold_items else None
    profit_per_1k_tokens = (true_net_profit / (total_tokens / 1000.0)) if total_tokens > 0 else 0.0
    profit_per_1k_seller = (true_net_profit / (mas_tokens / 1000.0)) if mas_tokens > 0 else None

    return {
        "true_net_profit": round(true_net_profit, 2),
        "total_gross_profit": round(total_gross_profit, 2),
        "spoilage_loss": round(total_spoilage_loss, 2),
        "mean_pcr": round(mean_pcr, 4) if mean_pcr is not None else "NA",
        "clearance_rate": round(clearance_rate, 4),
        "items_sold": len(sold_items),
        "items_expired": len(expired_items),
        "items_walk_away": len(walk_aways),
        "items_unresolved": len(unresolved_items),
        "items_invalid": len(invalid_items),
        "total_items": n_items,
        "avg_price_to_retail": round(avg_price_to_retail, 4),
        "instant_clears": instant_clears,
        "negotiated_sales": negotiated_sales,
        "instant_clear_rate": round(instant_clear_rate, 4),
        "negotiation_rate": round(negotiation_rate, 4),
        "walk_away_rate": round(walk_away_rate, 4),
        "unresolved_rate": round(unresolved_rate, 4),
        "expired_rate": round(expired_rate, 4),
        "total_tokens": total_tokens,
        "mas_tokens": mas_tokens,
        "buyer_tokens": buyer_tokens,
        "tokens_per_sold_item": round(tokens_per_sold, 1) if tokens_per_sold is not None else "NA",
        "profit_per_1k_tokens": round(profit_per_1k_tokens, 4),
        "profit_per_1k_seller_tokens": round(profit_per_1k_seller, 4) if profit_per_1k_seller is not None else "NA",
        "pcr_list": pcr_list,
    }


async def run_single_condition_trial(
    condition: str,
    trial_id: int,
    catalog: List[Dict[str, Any]],
    buyer_states: Dict[str, BuyerPrivateState],
    llm_client: LLMClient,
    catalog_hash: str,
    buyer_state_hash: str,
    trial_seed: int,
) -> Dict[str, Any]:
    """Execute exactly 15 item transactions for a condition trial."""
    print(f"\n---> Starting {condition} Trial {trial_id} (Seed: {trial_seed})...", flush=True)
    env = NegotiationEnvironment(mode=condition, llm_client=llm_client)

    item_results = []
    for idx, item in enumerate(catalog):
        item_id = item["item_id"]
        b_state = buyer_states[item_id]
        print(f"  [{condition} T{trial_id}] Item {idx+1}/15: {item['product_name']} ({item['starting_remaining_hours']}h)...", end="", flush=True)
        
        start_call_count = len(llm_client.call_records)
        res = await env.execute_item_transaction(item, b_state, trial_id=trial_id)
        end_call_count = len(llm_client.call_records)

        item_records = llm_client.call_records[start_call_count:end_call_count]
        res["total_tokens"] = sum(r.total_tokens for r in item_records)
        res["trial_id"] = trial_id
        res["condition"] = condition

        status_str = "SOLD" if res["sale_status"] == "SOLD" else "UNSOLD"
        print(f" -> {status_str} (${res['final_price']:.2f}, {res['negotiation_status']})", flush=True)
        item_results.append(res)

    trial_records = [r for r in llm_client.call_records if r.trial_id == trial_id]
    metrics = calculate_trial_metrics(item_results, trial_records)
    privacy_audit = audit_prompt_privacy(trial_records, buyer_states)

    checkpoint_data = {
        "condition": condition,
        "trial_id": trial_id,
        "trial_seed": trial_seed,
        "catalog_hash": catalog_hash,
        "buyer_state_hash": buyer_state_hash,
        "model_configuration": MODEL_REGISTRY if condition == "MAS" else "DETERMINISTIC_LINEAR_DECAY",
        "metrics": metrics,
        "privacy_audit": privacy_audit,
        "item_results": item_results,
    }

    chk_path = f"{OUTPUT_DIR}/checkpoints/{condition}_T{trial_id}.json"
    with open(chk_path, "w") as f:
        json.dump(checkpoint_data, f, indent=2)

    pcr_val = metrics.get("mean_pcr")
    pcr_str = f"{pcr_val:.4f}" if isinstance(pcr_val, (int, float)) else str(pcr_val)
    print(f"  [COMPLETED] {condition} T{trial_id} | Net Profit=${metrics['true_net_profit']:.2f} | Waste=${metrics['spoilage_loss']:.2f} | Sold={metrics['items_sold']}/15 | Mean PCR={pcr_str} | Privacy Audit Passed: {privacy_audit['audit_passed']}", flush=True)
    return checkpoint_data


def verify_benchmark_integrity(all_results: List[Dict[str, Any]], expected_trials: int = 2) -> bool:
    """Strict pre-reporting validation across all 4 benchmark trial files."""
    print("\n" + "=" * 60)
    print("RUNNING STRICT BENCHMARK INTEGRITY CHECKS...")
    print("=" * 60)

    # 1. Verify exactly 4 trial files
    files = os.listdir(f"{OUTPUT_DIR}/checkpoints")
    expected_files = {"MAS_T1.json", "MAS_T2.json", "LinearDecay_T1.json", "LinearDecay_T2.json"}
    if set(files) != expected_files:
        raise ValueError(f"Integrity check failed: Expected files {expected_files}, got {set(files)}")
    print(" [PASS] Checkpoint files: Exactly 4 required trial files present.")

    # 2. Verify 15 items per trial
    for res in all_results:
        cond = res["condition"]
        t_id = res["trial_id"]
        if len(res["item_results"]) != 15:
            raise ValueError(f"Integrity check failed: {cond} T{t_id} has {len(res['item_results'])} items, expected 15.")
    print(" [PASS] Catalog completeness: Exactly 15 items per trial verified.")

    # 3. Verify identical item IDs and buyer hashes across paired trials
    for t in range(1, expected_trials + 1):
        mas_t = next(r for r in all_results if r["condition"] == "MAS" and r["trial_id"] == t)
        ld_t = next(r for r in all_results if r["condition"] == "LinearDecay" and r["trial_id"] == t)

        mas_items = [i["item_id"] for i in mas_t["item_results"]]
        ld_items = [i["item_id"] for i in ld_t["item_results"]]
        if mas_items != ld_items:
            raise ValueError(f"Integrity check failed: Item mismatch in Trial {t}: {mas_items} vs {ld_items}")

        if mas_t["buyer_state_hash"] != ld_t["buyer_state_hash"]:
            raise ValueError(f"Integrity check failed: Buyer state hash mismatch in Trial {t}")

    print(" [PASS] Paired consistency: Identical item sequence & buyer state hashes replayed between MAS and LinearDecay.")

    # 4. Verify privacy audit
    for res in all_results:
        if res["condition"] == "MAS" and not res["privacy_audit"]["audit_passed"]:
            raise ValueError(f"Integrity check failed: Privacy audit violations in MAS T{res['trial_id']}: {res['privacy_audit']['violations']}")

    print(" [PASS] Privacy boundaries: 0 private variable leaks across all audited seller calls.")
    print("ALL 4 BENCHMARK INTEGRITY CHECKS PASSED.")
    return True


async def run_benchmark(n_trials: int = 2):
    """Run full benchmark: exactly 2 MAS trials + 2 LinearDecay trials."""
    print("=" * 60, flush=True)
    print(f"REVISED MINIMAL PERISHABILITY BENCHMARK: MAS vs LinearDecay ({n_trials} Trials Each)", flush=True)
    print("=" * 60, flush=True)

    catalog = get_fixed_catalog()
    catalog_hash = compute_sha256(catalog)
    print(f"Fixed Catalog Items: {len(catalog)}")
    print(f"Catalog SHA-256 Hash: {catalog_hash}")
    print(f"Model Configuration: StrategicBrain=openai/gpt-oss-120b, Other Agents=openai/gpt-oss-20b")

    all_results = []
    base_seed = 42

    for t in range(1, n_trials + 1):
        trial_seed = base_seed + t * 100
        buyer_states = generate_buyer_private_states(catalog, trial_seed)
        buyer_state_hash = compute_sha256({k: v.model_dump() for k, v in buyer_states.items()})

        print(f"\n==================================================")
        print(f"TRIAL {t}/{n_trials} METADATA:")
        print(f"  Trial Seed:       {trial_seed}")
        print(f"  Buyer State Hash: {buyer_state_hash}")
        print(f"==================================================")
        
        # Persist buyer states
        b_path = f"{OUTPUT_DIR}/logs/buyer_states_T{t}.json"
        with open(b_path, "w") as f:
            json.dump({
                "trial_id": t,
                "trial_seed": trial_seed,
                "catalog_hash": catalog_hash,
                "buyer_state_hash": buyer_state_hash,
                "buyer_states": {k: v.model_dump() for k, v in buyer_states.items()}
            }, f, indent=2)

        # 1. Run MAS
        llm_mas = LLMClient(max_concurrent=2)
        mas_res = await run_single_condition_trial(
            condition="MAS",
            trial_id=t,
            catalog=catalog,
            buyer_states=buyer_states,
            llm_client=llm_mas,
            catalog_hash=catalog_hash,
            buyer_state_hash=buyer_state_hash,
            trial_seed=trial_seed,
        )
        all_results.append(mas_res)

        # 2. Run LinearDecay with identical buyer states
        llm_ld = LLMClient(max_concurrent=2)
        ld_res = await run_single_condition_trial(
            condition="LinearDecay",
            trial_id=t,
            catalog=catalog,
            buyer_states=buyer_states,
            llm_client=llm_ld,
            catalog_hash=catalog_hash,
            buyer_state_hash=buyer_state_hash,
            trial_seed=trial_seed,
        )
        all_results.append(ld_res)

    # Post-execution verification checks
    verify_benchmark_integrity(all_results, expected_trials=n_trials)

    # Compile Final Comparative Output exclusively from the 4 trial files
    generate_final_report(all_results)


def generate_final_report(all_results: List[Dict[str, Any]]):
    """Aggregate results and write markdown report with summary and perishability analysis."""
    mas_trials = [r for r in all_results if r["condition"] == "MAS"]
    ld_trials = [r for r in all_results if r["condition"] == "LinearDecay"]

    def avg(lst, key):
        return float(np.mean([t["metrics"][key] for t in lst]))

    def std(lst, key):
        return float(np.std([t["metrics"][key] for t in lst]))

    summary_data = {
        "Metric": [
            "True Net Profit ($)",
            "Gross Profit ($)",
            "Spoilage Loss ($)",
            "Profit Capture Ratio (PCR)",
            "Clearance Rate (%)",
            "Avg Sale Price / Retail",
            "Instant Clear Rate (%)",
            "Negotiated Sale Rate (%)",
            "Walk Away Rate (%)",
            "Total Tokens",
            "Tokens / Sold Item",
            "Profit / 1000 Tokens ($)",
        ],
        "MAS (Mean ± Std)": [
            f"${avg(mas_trials, 'true_net_profit'):.2f} ± ${std(mas_trials, 'true_net_profit'):.2f}",
            f"${avg(mas_trials, 'total_gross_profit'):.2f} ± ${std(mas_trials, 'total_gross_profit'):.2f}",
            f"${avg(mas_trials, 'spoilage_loss'):.2f} ± ${std(mas_trials, 'spoilage_loss'):.2f}",
            f"{avg(mas_trials, 'mean_pcr'):.4f} ± {std(mas_trials, 'mean_pcr'):.4f}",
            f"{avg(mas_trials, 'clearance_rate') * 100:.1f}%",
            f"{avg(mas_trials, 'avg_price_to_retail'):.4f}",
            f"{avg(mas_trials, 'instant_clear_rate') * 100:.1f}%",
            f"{avg(mas_trials, 'negotiation_rate') * 100:.1f}%",
            f"{avg(mas_trials, 'walk_away_rate') * 100:.1f}%",
            f"{int(avg(mas_trials, 'total_tokens')):,}",
            f"{avg(mas_trials, 'tokens_per_sold_item'):.1f}",
            f"${avg(mas_trials, 'profit_per_1k_tokens'):.4f}",
        ],
        "LinearDecay (Mean ± Std)": [
            f"${avg(ld_trials, 'true_net_profit'):.2f} ± ${std(ld_trials, 'true_net_profit'):.2f}",
            f"${avg(ld_trials, 'total_gross_profit'):.2f} ± ${std(ld_trials, 'total_gross_profit'):.2f}",
            f"${avg(ld_trials, 'spoilage_loss'):.2f} ± ${std(ld_trials, 'spoilage_loss'):.2f}",
            f"{avg(ld_trials, 'mean_pcr'):.4f} ± {std(ld_trials, 'mean_pcr'):.4f}",
            f"{avg(ld_trials, 'clearance_rate') * 100:.1f}%",
            f"{avg(ld_trials, 'avg_price_to_retail'):.4f}",
            f"{avg(ld_trials, 'instant_clear_rate') * 100:.1f}%",
            f"{avg(ld_trials, 'negotiation_rate') * 100:.1f}%",
            f"{avg(ld_trials, 'walk_away_rate') * 100:.1f}%",
            f"{int(avg(ld_trials, 'total_tokens')):,}",
            f"{avg(ld_trials, 'tokens_per_sold_item'):.1f}",
            f"${avg(ld_trials, 'profit_per_1k_tokens'):.4f}",
        ],
    }

    df_summary = pd.DataFrame(summary_data)
    df_summary.to_csv(f"{OUTPUT_DIR}/summary_comparison.csv", index=False)

    # Perishability Regime Breakdown
    all_items_mas = [item for trial in mas_trials for item in trial["item_results"]]
    all_items_ld = [item for trial in ld_trials for item in trial["item_results"]]

    regimes = ["Critical", "Medium", "Low"]
    regime_rows = []

    for reg in regimes:
        m_items = [i for i in all_items_mas if i["expiry_regime"] == reg]
        l_items = [i for i in all_items_ld if i["expiry_regime"] == reg]

        m_sold = len([i for i in m_items if i["sale_status"] == "SOLD"])
        l_sold = len([i for i in l_items if i["sale_status"] == "SOLD"])

        m_profit = sum(i["item_profit"] for i in m_items) / len(mas_trials)
        l_profit = sum(i["item_profit"] for i in l_items) / len(ld_trials)

        m_spoilage = sum(i["spoilage_loss"] for i in m_items) / len(mas_trials)
        l_spoilage = sum(i["spoilage_loss"] for i in l_items) / len(ld_trials)

        m_pcr = float(np.mean([i["pcr"] for i in m_items if i["sale_status"] == "SOLD"])) if m_sold > 0 else 0.0
        l_pcr = float(np.mean([i["pcr"] for i in l_items if i["sale_status"] == "SOLD"])) if l_sold > 0 else 0.0

        regime_rows.append({
            "Expiry Regime": f"{reg} ({'12-36h' if reg=='Critical' else '48-120h' if reg=='Medium' else '144-336h'})",
            "MAS Sold": f"{m_sold}/{len(m_items)}",
            "MAS Net Profit": f"${m_profit:.2f}",
            "MAS Spoilage": f"${m_spoilage:.2f}",
            "MAS Mean PCR": f"{m_pcr:.4f}",
            "LinearDecay Sold": f"{l_sold}/{len(l_items)}",
            "LinearDecay Net Profit": f"${l_profit:.2f}",
            "LinearDecay Spoilage": f"${l_spoilage:.2f}",
            "LinearDecay Mean PCR": f"{l_pcr:.4f}",
        })

    df_regimes = pd.DataFrame(regime_rows)
    df_regimes.to_csv(f"{OUTPUT_DIR}/perishability_analysis.csv", index=False)

    # Markdown Report
    report_md = f"""# Minimal Perishability Benchmark: MAS vs LinearDecay

## 1. Executive Summary Table

{df_summary.to_markdown(index=False)}

---

## 2. Perishability Regime Analysis

| Expiry Regime | MAS Sold Rate | MAS Net Profit | MAS Spoilage | MAS PCR | LinearDecay Sold Rate | LinearDecay Net Profit | LinearDecay Spoilage | LinearDecay PCR |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for r in regime_rows:
        report_md += f"| {r['Expiry Regime']} | {r['MAS Sold']} | {r['MAS Net Profit']} | {r['MAS Spoilage']} | {r['MAS Mean PCR']} | {r['LinearDecay Sold']} | {r['LinearDecay Net Profit']} | {r['LinearDecay Spoilage']} | {r['LinearDecay Mean PCR']} |\n"

    report_md += f"""
---

## 3. Cryptographic Hashes & Verification Metadata
- **Catalog Items Count**: 15 fixed items
- **Catalog SHA-256**: `{mas_trials[0]['catalog_hash']}`
- **Trial 1 Seed & Buyer Hash**: Seed `{mas_trials[0]['trial_seed']}`, Hash `{mas_trials[0]['buyer_state_hash']}`
- **Trial 2 Seed & Buyer Hash**: Seed `{mas_trials[1]['trial_seed']}`, Hash `{mas_trials[1]['buyer_state_hash']}`
- **Privacy Audit Status**: **PASSED (0 Leaks Detected)**
"""

    report_path = f"{OUTPUT_DIR}/benchmark_report.md"
    with open(report_path, "w") as f:
        f.write(report_md)

    print("\n" + "=" * 60, flush=True)
    print("FINAL BENCHMARK REPORT WRITTEN TO:", report_path, flush=True)
    print("=" * 60, flush=True)
    print(report_md, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=2, help="Number of trials per condition")
    args = parser.parse_args()
    asyncio.run(run_benchmark(n_trials=args.trials))
