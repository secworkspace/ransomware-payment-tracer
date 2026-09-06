"""
detect_risk.py

Risk analysis layer for the Ransomware Payment Tracer project.

Takes a completed fund-flow trace (from fetch_transactions.py) and applies
a small set of rule-based heuristics to flag potentially notable hops:
large value drops between hops, matches against a sanctions/mixer
blacklist, and self-consolidation patterns. Produces a risk-annotated
report suitable for display in the dashboard.
"""

import json

DROP_THRESHOLD_PERCENT = 5  # Flag if value drops more than this % between hops


def load_trace(filename="trace_output.json"):
    """Loads a previously saved trace from disk."""
    with open(filename, "r") as f:
        return json.load(f)


def load_blacklist(filename="blacklist.json"):
    """
    Loads the address blacklist used for sanctions/mixer screening.

    The blacklist is built separately (see build_blacklist.py) from the
    U.S. Treasury's live OFAC SDN sanctions list, filtered and validated
    to confirmed Bitcoin addresses.
    """
    with open(filename, "r") as f:
        return json.load(f)


def analyze_trace(chain, blacklist):
    """
    Applies risk rules to each hop in a trace.

    Rules applied, in order:
      1. Value-drop anomaly — flags a hop if the transferred amount drops
         more than DROP_THRESHOLD_PERCENT from the previous hop.
      2. Blacklist match — flags a hop if its destination address appears
         in the sanctions/mixer blacklist.
      3. Self-consolidation — labels (does not penalize) hops where funds
         were reorganized within the same address rather than moved to
         a new party.

    Args:
        chain (list[dict]): The trace produced by trace_chain().
        blacklist (dict): Blacklist data from load_blacklist().

    Returns:
        list[dict]: The input chain, with "flags" (list[str]) and
            "risk_level" ("Low" | "Medium" | "High") added to each hop.
    """
    flagged_addresses = set(
        blacklist.get("known_mixers", []) + blacklist.get("known_exchange_deposit_addresses", [])
    )

    results = []
    previous_amount = None

    for step in chain:
        flags = []

        if previous_amount is not None:
            drop_percent = ((previous_amount - step["amount_btc"]) / previous_amount) * 100
            if drop_percent > DROP_THRESHOLD_PERCENT:
                flags.append(f"Value dropped {drop_percent:.1f}% from previous hop")

        if step["to_address"] in flagged_addresses:
            flags.append("Address matches known flagged list")

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
    """Prints a human-readable risk report to the console."""
    print("\n===== RISK ANALYSIS REPORT =====\n")
    for step in results:
        print(f"Hop {step['hop']}: {step['from_address'][:12]}... → {step['to_address'][:12]}...")
        print(f"  Amount: {step['amount_btc']} BTC | Risk: {step['risk_level']}")
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