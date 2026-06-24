import json
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_benchmark_chart():
    # File paths
    file_path = "kanishka_output/Full_Llama-70B_Dominance/session_data.json"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, "r") as f:
        data = json.load(f)

    labels = []
    sold_counts = []
    total_items = 0

    for mode_name, result in data["metrics"].items():
        # Shorten labels for chart
        if "mas" in mode_name.lower() and "single" not in mode_name.lower():
            labels.append("MAS")
        elif "single" in mode_name.lower():
            labels.append("Single Model LLM")
        elif "human" in mode_name.lower():
            labels.append("Human Baseline")
        else:
            labels.append(mode_name)
            
        sold_counts.append(result.get("Items Sold", 0))
        total_items = 14

    # Calculate Spoilage (Waste)
    spoilage = [total_items - s for s in sold_counts]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot bars
    rects1 = ax.bar(x - width/2, sold_counts, width, label='Items Sold (Success)', color='#2ecc71')
    rects2 = ax.bar(x + width/2, spoilage, width, label='Items Spoiled (Waste)', color='#e74c3c')

    # Add text and labels
    ax.set_ylabel('Number of Items')
    ax.set_title('B2B Negotiation Benchmark: Kanishka MAS vs Single Model (Gemini 3.5 Flash)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    # Add data labels
    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)

    fig.tight_layout()

    # Save to file
    output_path = "kanishka_output/mentor_update_chart.png"
    plt.savefig(output_path, dpi=300)
    print(f"[SUCCESS] Chart saved to {output_path}")

if __name__ == "__main__":
    generate_benchmark_chart()
