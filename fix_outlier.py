import json
import os
from kanishka_src.main import calculate_metrics

file_path = "kanishka_output/Full_Llama-70B_Dominance/session_data.json"
with open(file_path, "r") as f:
    data = json.load(f)

# The item to remove
OUTLIER_ITEM = "Vaccines"

for mode in ["kanishka_mas", "single_model_mas", "human_baseline"]:
    raw_data = data["raw"][mode]
    
    # Filter inventory
    new_inventory = [i for i in raw_data["blackboard"]["inventory"] if i["product_name"] != OUTLIER_ITEM]
    raw_data["blackboard"]["inventory"] = new_inventory
    
    # Filter sales
    new_sales = [s for s in raw_data["blackboard"]["sales_data"] if s["product_name"] != OUTLIER_ITEM]
    raw_data["blackboard"]["sales_data"] = new_sales
    
    # Recalculate metrics
    new_metrics = calculate_metrics(raw_data)
    data["metrics"][mode] = new_metrics

# Save updated JSON
with open(file_path, "w") as f:
    json.dump(data, f, indent=4)

print("Metrics Recalculated! New Metrics:")
for mode, m in data["metrics"].items():
    if mode == "actual_historical": continue
    print(f"\n--- {mode} ---")
    for k, v in m.items():
        print(f"{k}: {v}")
