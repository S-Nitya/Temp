import os
import json
import numpy as np

def audit_checkpoints():
    files = ['MAS_T1.json', 'MAS_T2.json', 'LinearDecay_T1.json', 'LinearDecay_T2.json']
    chk_dir = "kanishka_revised_mas/results/checkpoints"
    
    for fname in files:
        fpath = os.path.join(chk_dir, fname)
        with open(fpath, "r") as f:
            data = json.load(f)
        
        cond = data["condition"]
        t_id = data["trial_id"]
        items = data["item_results"]
        metrics = data["metrics"]
        
        print(f"\n==========================================")
        print(f"AUDITING: {fname} (Condition: {cond}, Trial: {t_id})")
        print(f"==========================================")
        
        # 1. Item level recomputations
        recomputed_gross = 0.0
        recomputed_spoilage = 0.0
        recomputed_sold = 0
        pcr_list = []
        
        for item in items:
            p_sale = item["final_price"]
            p_cost = item["cost_price"]
            p_ret = item["retail_reference"]
            status = item["sale_status"]
            
            if status == "SOLD":
                recomputed_sold += 1
                recomputed_gross += (p_sale - p_cost)
                pcr = (p_sale - p_cost) / (p_ret - p_cost)
                pcr_list.append(pcr)
                assert abs(pcr - item["pcr"]) < 1e-4, f"PCR mismatch on item {item['item_id']}"
            else:
                recomputed_spoilage += p_cost
        
        recomputed_net = recomputed_gross - recomputed_spoilage
        recomputed_mean_pcr = np.mean(pcr_list) if pcr_list else None
        
        print(f"Items: Total={len(items)}, Sold={recomputed_sold}, Unsold={len(items) - recomputed_sold}")
        print(f"Gross Profit:  Stored={metrics['total_gross_profit']:.2f}, Recomputed={recomputed_gross:.2f}")
        print(f"Spoilage Loss: Stored={metrics['spoilage_loss']:.2f}, Recomputed={recomputed_spoilage:.2f}")
        print(f"True Net:      Stored={metrics['true_net_profit']:.2f}, Recomputed={recomputed_net:.2f}")
        print(f"Mean PCR:      Stored={metrics['mean_pcr']:.4f}, Recomputed={recomputed_mean_pcr if recomputed_mean_pcr is not None else 'NA'}")
        
        # Token audit
        tot_tok = metrics["total_tokens"]
        tok_per_sold = tot_tok / recomputed_sold if recomputed_sold > 0 else 'NA'
        profit_per_1k_tot = (recomputed_net / (tot_tok / 1000.0)) if tot_tok > 0 else 0.0
        
        mas_tok = metrics.get("mas_tokens", 0)
        buyer_tok = metrics.get("buyer_tokens", 0)
        profit_per_1k_seller = (recomputed_net / (mas_tok / 1000.0)) if mas_tok > 0 else 'NA'
        
        print(f"Tokens: Total={tot_tok}, Seller={mas_tok}, Buyer={buyer_tok}")
        print(f"Tokens / Sold Item (Trial-level): Stored={metrics['tokens_per_sold_item']}, Recomputed={tok_per_sold}")
        print(f"Profit / 1k Total Tokens:         Stored={metrics['profit_per_1k_tokens']}, Recomputed={profit_per_1k_tot:.4f}")
        print(f"Profit / 1k Seller Tokens:        Recomputed={profit_per_1k_seller if profit_per_1k_seller == 'NA' else f'{profit_per_1k_seller:.4f}'}")

if __name__ == "__main__":
    audit_checkpoints()
