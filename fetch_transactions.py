"""
fetch_transactions.py

Core blockchain tracing engine for the Ransomware Payment Tracer project.

Given a starting ("seed") Bitcoin address, this module follows the flow
of funds hop by hop using UTXO-level transaction matching — meaning each
hop is verified to actually spend the specific coins received in the
previous hop, rather than naively assuming an address's largest outgoing
transaction is the correct next step. This avoids false positives caused
by address reuse, which is a common pitfall in simplistic blockchain
tracing approaches.

Data is pulled live from the Blockstream Esplora public API.
"""

import requests
import time
import json

SEED_ADDRESS = "bc1qq2euq8pw950klpjcawuy4uj39ym43hs6cfsegq"
MAX_HOPS = 15
MIN_AMOUNT_BTC = 1  # Ignore small/incidental transactions (noise filtering)


def get_transactions(address):
    """
    Fetches the full transaction history for a given Bitcoin address
    from the Blockstream public API.

    Args:
        address (str): A Bitcoin address (legacy or bech32 format).

    Returns:
        list[dict]: Raw transaction data as returned by the API, each
        containing 'vin' (inputs) and 'vout' (outputs).
    """
    url = f"https://blockstream.info/api/address/{address}/txs"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def find_next_hop(address, incoming_txid, visited):
    """
    Determines the next hop in the fund trace from the given address.

    The function first looks for a transaction that provably spends the
    specific UTXO the address received via `incoming_txid` (true UTXO-level
    tracing). Among valid candidates, it prefers a transfer to a genuinely
    new address (an "external" hop) over one that sends funds back to the
    same address (a "self" hop, typically representing wallet consolidation
    or reorganization rather than real fund movement to a new party).

    Args:
        address (str): The address currently being traced.
        incoming_txid (str | None): The transaction ID that funded this
            address, used to confirm the next hop spends those exact coins.
            None only for the very first hop (the seed address), where no
            prior transaction exists to match against.
        visited (set[str]): Addresses already included in the trace, to
            prevent cycles.

    Returns:
        dict | None: The best candidate hop as
            {"tx_id", "to_address", "amount_btc", "self"}, or None if no
            qualifying transaction is found (a dead end).
    """
    txs = get_transactions(address)
    best_external = None
    best_external_amount = 0
    best_self = None
    best_self_amount = 0

    for tx in txs:
        spends_our_utxo = False

        if incoming_txid is None:
            # Seed address has no prior transaction to match against.
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
            continue  # This transaction is unrelated to our specific coins.

        for out in tx["vout"]:
            out_addr = out.get("scriptpubkey_address", "unknown")
            value_btc = out["value"] / 100_000_000

            if value_btc < MIN_AMOUNT_BTC:
                continue  # Filter out dust/noise.

            if out_addr == address:
                # Self-consolidation: track as a fallback hop only.
                if value_btc > best_self_amount:
                    best_self_amount = value_btc
                    best_self = {
                        "tx_id": tx["txid"],
                        "to_address": out_addr,
                        "amount_btc": value_btc,
                        "self": True,
                    }
            else:
                if out_addr in visited:
                    continue
                if value_btc > best_external_amount:
                    best_external_amount = value_btc
                    best_external = {
                        "tx_id": tx["txid"],
                        "to_address": out_addr,
                        "amount_btc": value_btc,
                        "self": False,
                    }

    # Prefer genuine external movement; fall back to self-consolidation.
    return best_external if best_external else best_self


def trace_chain(seed_address, max_hops=MAX_HOPS):
    """
    Follows the flow of funds from a seed address across multiple hops.

    Repeatedly calls `find_next_hop` to walk the transaction chain forward,
    stopping when either `max_hops` is reached or no further qualifying
    transfer is found (a genuine dead end, e.g. unspent funds).

    Args:
        seed_address (str): The starting Bitcoin address to trace from.
        max_hops (int): Maximum number of hops to follow before stopping.

    Returns:
        list[dict]: The ordered chain of hops, each containing
            "hop", "from_address", "to_address", "tx_id", "amount_btc",
            and "self".
    """
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

        time.sleep(1)  # Avoid hammering the free public API.

    return chain


def print_summary(chain):
    """Prints a concise, human-readable summary of a completed trace."""
    print("\n===== FULL TRACE SUMMARY =====")
    for step in chain:
        print(f"Hop {step['hop']}: {step['from_address'][:12]}... "
              f"→ {step['to_address'][:12]}...  ({step['amount_btc']} BTC)")


def save_trace(chain, filename="trace_output.json"):
    """Saves a completed trace to a JSON file for downstream analysis."""
    with open(filename, "w") as f:
        json.dump(chain, f, indent=2)
    print(f"\nTrace saved to {filename}")


if __name__ == "__main__":
    result = trace_chain(SEED_ADDRESS)
    print_summary(result)
    save_trace(result)