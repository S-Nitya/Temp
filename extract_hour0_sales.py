import json

cp = json.load(open("final_output/ablation/checkpoints/metrics_Full_MAS_T1.json"))

print("=== TRIAL 1: STRATEGIC BRAIN OPENING BLACKBOARD / LOGS ===")
for log in cp.get("blackboard", {}).get("logs", []):
    if "STRATEGY DISCOVERY" in log:
        print(log)

print("\n=== TRIAL 1: ALL HOUR 0 SALES IN sales_data ===")
for s in cp.get("final_metrics", {}).get("sales_data", cp.get("blackboard", {}).get("sales_data", [])):
    if s.get("hour") == 0:
        print(s)

print("\n=== TRIAL 1: NEGOTIATION LOG FOR ALL HOUR 0 ITEMS ===")
target_items = ["Ground Beef_12", "Lettuce_10", "Bread_13", "Cod_3", "Tilapia_2"]
for entry in cp.get("negotiation_log", []):
    if entry.get("hour") == 0:
        print(json.dumps(entry, indent=2))
