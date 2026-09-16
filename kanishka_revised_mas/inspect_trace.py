import json

def inspect_mas_items():
    for trial_id in [1, 2]:
        with open(f'kanishka_revised_mas/results/checkpoints/MAS_T{trial_id}.json') as f:
            d = json.load(f)
        print(f"\n==============================================")
        print(f"MAS TRIAL {trial_id} ITEM-BY-ITEM TRACE")
        print(f"==============================================")
        for it in d['item_results']:
            print(f"\nItem: {it['product_name']} ({it['item_id']}) | Expiry: {it['starting_remaining_hours']}h ({it['expiry_regime']}) | Cost: ${it['cost_price']:.2f} | Retail: ${it['retail_reference']:.2f}")
            print(f"Starting Price: ${it['starting_price']:.2f} | Final Price: ${it['final_price']:.2f} | Status: {it['sale_status']} ({it['negotiation_status']}) | Exchanges: {it['number_of_exchanges']}")
            for entry in it.get('conversation_history', []):
                print(f"  [{entry.get('sender', 'Unknown')}]: {entry.get('message', '')} (Offer: {entry.get('offer_price', entry.get('counter_price', 'None'))})")

if __name__ == '__main__':
    inspect_mas_items()
