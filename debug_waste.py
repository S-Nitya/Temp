import json
from kanishka_src.main import calculate_metrics

with open("kanishka_output/Full_Llama-70B_Dominance/session_data.json", "r") as f:
    data = json.load(f)

for mode in ["kanishka_mas", "single_model_mas"]:
    raw = data["raw"][mode]
    sales = raw["blackboard"]["sales_data"]
    inventory = raw["blackboard"]["inventory"]
    sold_names = [s['product_name'] for s in sales]
    unsold_items = [i for i in inventory if i['product_name'] not in sold_names]
    
    print(f"--- {mode} ---")
    print(f"Items sold: {len(sold_names)}")
    print(f"Inventory size: {len(inventory)}")
    print(f"Unsold items: {unsold_items}")
