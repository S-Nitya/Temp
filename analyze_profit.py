import json

with open("kanishka_output/Full_Llama-70B_Dominance/session_data.json", "r") as f:
    data = json.load(f)

sales_mas = data['raw']['kanishka_mas']['blackboard']['sales_data']
sales_single = data['raw']['single_model_mas']['blackboard']['sales_data']

print("--- KANISHKA MAS SALES ---")
for s in sales_mas:
    potential = s['initial_price'] - s['cost_price']
    actual = s['sale_price'] - s['cost_price']
    pcr = actual / potential if potential > 0 else 1.0
    print(f"{s['product_name']}: Cost=${s['cost_price']:.2f}, Sold=${s['sale_price']:.2f}, Profit=${actual:.2f}, PCR={pcr:.2f}")

print("\n--- SINGLE MODEL SALES ---")
for s in sales_single:
    potential = s['initial_price'] - s['cost_price']
    actual = s['sale_price'] - s['cost_price']
    pcr = actual / potential if potential > 0 else 1.0
    print(f"{s['product_name']}: Cost=${s['cost_price']:.2f}, Sold=${s['sale_price']:.2f}, Profit=${actual:.2f}, PCR={pcr:.2f}")
