import requests
import time
import json 

SEED_ADDRESS = "bc1qq2euq8pw950klpjcawuy4uj39ym43hs6cfsegq"
MAX_HOPS = 15
MIN_AMOUNT_BTC = 1  # ignore small/noise transactions

def get_transactions(address):
    url = f"https://blockstream.info/api/address/{address}/txs"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def find_next_hop(address, incoming_txid, visited):
    txs = get_transactions(address)
    best_external = None
    best_external_amount = 0
    best_self = None
    best_self_amount = 0

    for tx in txs:
        spends_our_utxo = False

        if incoming_txid is None:
            spends_our_utxo = True
        else:
            for vin in tx["vin"]:
                prevout = vin.get("prevout", {})
                prev_addr = prevout.get("scriptpubkey_address")
                prev_txid = vin.get("txid")
                if prev_addr == address and prev_txid == incoming_txid:
                    spends_our_utxo = True
                    break

        if not spends_our_utxo:
            continue

        for out in tx["vout"]:
            out_addr = out.get("scriptpubkey_address", "unknown")
            value_btc = out["value"] / 100_000_000

            if value_btc < MIN_AMOUNT_BTC:
                continue

            if out_addr == address:
                # Self-consolidation — track it as a fallback hop
                if value_btc > best_self_amount:
                    best_self_amount = value_btc
                    best_self = {"tx_id": tx["txid"], "to_address": out_addr, "amount_btc": value_btc, "self": True}
            else:
                if out_addr in visited:
                    continue
                if value_btc > best_external_amount:
                    best_external_amount = value_btc
                    best_external = {"tx_id": tx["txid"], "to_address": out_addr, "amount_btc": value_btc, "self": False}

    # Prefer a real external hop; fall back to self-consolidation if that's all there is
    return best_external if best_external else best_self


def trace_chain(seed_address, max_hops=MAX_HOPS):
    chain = []
    current_address = seed_address
    current_txid = None
    visited = {seed_address}

    print(f"Starting trace from: {seed_address}\n")

    for hop_number in range(1, max_hops + 1):
        print(f"Hop {hop_number}: checking {current_address} ...")
        next_hop = find_next_hop(current_address, current_txid, visited)

        if next_hop is None:
            print("  No further significant transfer found — trace ends here.\n")
            break

        label = "(self-consolidation)" if next_hop.get("self") else ""
        print(f"  → Found: {next_hop['amount_btc']} BTC to {next_hop['to_address']} {label}\n")

        chain.append({
            "hop": hop_number,
            "from_address": current_address,
            **next_hop
        })

        if not next_hop.get("self"):
            visited.add(next_hop["to_address"])

        current_address = next_hop["to_address"]
        current_txid = next_hop["tx_id"]

        time.sleep(1)

    return chain

def print_summary(chain):
    print("\n===== FULL TRACE SUMMARY =====")
    for step in chain:
        print(f"Hop {step['hop']}: {step['from_address'][:12]}... "
              f"→ {step['to_address'][:12]}...  ({step['amount_btc']} BTC)")

import json

def save_trace(chain, filename="trace_output.json"):
    with open(filename, "w") as f:
        json.dump(chain, f, indent=2)
    print(f"\nTrace saved to {filename}")

if __name__ == "__main__":
    result = trace_chain(SEED_ADDRESS)
    print_summary(result)
    save_trace(result)