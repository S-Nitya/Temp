import json
import glob
import pandas as pd

checkpoints = sorted(glob.glob("final_output/ablation/checkpoints/*.json"))
mas_checkpoints = [json.load(open(f)) for f in checkpoints if "Full_MAS" in f]
ld_checkpoints = [json.load(open(f)) for f in checkpoints if "LinearDecay" in f]

target_cases = [
    (1, "Tomatoes_8", "Tomatoes"),
    (3, "Beef_11", "Beef"),
    (5, "Beef_11", "Beef"),
    (1, "Kombucha_1", "Kombucha"),
    (2, "Kombucha_1", "Kombucha"),
]

print("=== STATUS OF THE 5 PREVIOUSLY-EXPIRED ITEMS (70B Decider Run) ===")
for trial_id, item_id, item_name in target_cases:
    cp = next(c for c in mas_checkpoints if c["trial_id"] == trial_id)
    outcomes = cp.get("item_outcomes", {})
    res = outcomes.get(item_id, {})
    outcome = res.get("outcome", "UNKNOWN")
    hour = res.get("hour", 0.0)
    price = res.get("final_price", 0.0)
    print(f"Trial {trial_id} | {item_id} ({item_name}): Outcome = {outcome} | Hour = {hour} | Final Price = ${price:.2f}")

print("\n=== ALL EXPIRED ITEMS ACROSS ALL 5 TRIALS (Full_MAS with 70B Decider) ===")
for cp in mas_checkpoints:
    t = cp["trial_id"]
    for i_id, o in cp.get("item_outcomes", {}).items():
        if o.get("outcome") == "EXPIRED_UNSOLD":
            print(f"Trial {t}: {i_id} ({o.get('item')}) expired unsold.")

print("\n=== OVERALL SUMMARY COMPARISON (70B Decider vs LinearDecay) ===")
rows = []
for cp in mas_checkpoints:
    m = cp["final_metrics"]
    rows.append({"Condition": "Full_MAS", "Trial": cp["trial_id"], "PCR": m["pcr"], "Profit": m["total_profit"], "Waste": m["waste_loss"], "Sold": m["items_sold"]})
for cp in ld_checkpoints:
    m = cp["final_metrics"]
    rows.append({"Condition": "LinearDecay", "Trial": cp["trial_id"], "PCR": m["pcr"], "Profit": m["total_profit"], "Waste": m["waste_loss"], "Sold": m["items_sold"]})

df = pd.DataFrame(rows)
print(df.groupby("Condition")[["PCR", "Profit", "Waste", "Sold"]].agg(["mean", "std"]).to_string())
