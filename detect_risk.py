import json

DROP_THRESHOLD_PERCENT = 5  # flag if value drops more than 5% between hops

def load_trace(filename="trace_output.json"):
    with open(filename, "r") as f:
        return json.load(f)

def load_blacklist(filename="blacklist.json"):
    with open(filename, "r") as f:
        return json.load(f)

def analyze_trace(chain, blacklist):
    flagged_addresses = set(
        blacklist.get("known_mixers", []) + blacklist.get("known_exchange_deposit_addresses", [])
    )

    results = []
    previous_amount = None

    for step in chain:
        flags = []

        # Rule 1: value drop
        if previous_amount is not None:
            drop_percent = ((previous_amount - step["amount_btc"]) / previous_amount) * 100
            if drop_percent > DROP_THRESHOLD_PERCENT:
                flags.append(f"Value dropped {drop_percent:.1f}% from previous hop")

        # Rule 2: blacklist match
        if step["to_address"] in flagged_addresses:
            flags.append("Address matches known flagged list")

        # Rule 3: self-consolidation label
        if step.get("self"):
            flags.append("Self-consolidation (same-address reorganization)")

        results.append({
            **step,
            "flags": flags,
            "risk_level": "High" if any("flagged list" in f for f in flags) else
                          "Medium" if flags else "Low"
        })

        previous_amount = step["amount_btc"]

    return results

def print_report(results):
    print("\n===== RISK ANALYSIS REPORT =====\n")
    for step in results:
        print(f"Hop {step['hop']}: {step['from_address'][:12]}... → {step['to_address'][:12]}...")
        print(f"  Amount: {step['amount_btc']} BTC | Risk: {step['risk_level']}")
        if step["flags"]:
            for flag in step["flags"]:
                print(f"  ⚠ {flag}")
        print()

if __name__ == "__main__":
    chain = load_trace()
    blacklist = load_blacklist()
    results = analyze_trace(chain, blacklist)
    print_report(results)

    with open("risk_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Risk report saved to risk_report.json")