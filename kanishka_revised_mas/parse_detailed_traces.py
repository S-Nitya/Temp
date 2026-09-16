import json

def parse_detailed_traces():
    for trial_id in [1, 2]:
        with open(f'kanishka_revised_mas/results/checkpoints/MAS_T{trial_id}.json') as f:
            d = json.load(f)
        
        print(f"\n========================================================")
        print(f"DETAILED UNSOLD ITEMS DIAGNOSTICS: MAS TRIAL {trial_id}")
        print(f"========================================================")
        
        for it in d['item_results']:
            if it['sale_status'] == 'UNSOLD':
                print(f"\nItem: {it['product_name']} ({it['item_id']})")
                print(f"  Regime: {it['expiry_regime']} ({it['starting_remaining_hours']}h) | Cost: ${it['cost_price']:.2f} | Retail: ${it['retail_reference']:.2f}")
                print(f"  Opening Price: ${it['starting_price']:.2f} | Status: {it['negotiation_status']} | Exchanges: {it['number_of_exchanges']}")
                print(f"  Conversation Trace:")
                for step in it.get('conversation_history', []):
                    print(f"    Exchange {step.get('exchange')}:")
                    print(f"      Seller Quote: ${step.get('seller_quote')} | Msg: {step.get('seller_message')}")
                    print(f"      Buyer Action: {step.get('buyer_action')} | Offer: ${step.get('buyer_offer')} | Msg: {step.get('buyer_message')}")

if __name__ == '__main__':
    parse_detailed_traces()
