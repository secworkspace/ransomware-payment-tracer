import csv
import json

import re

import re

def is_valid_btc_address(addr):
    # Legacy (starts with 1 or 3) - 25 to 34 base58 characters
    legacy_pattern = r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"
    # Bech32 (starts with bc1) - 25 to 90 lowercase alphanumeric characters
    bech32_pattern = r"^bc1[a-z0-9]{25,90}$"

    return bool(re.match(legacy_pattern, addr)) or bool(re.match(bech32_pattern, addr))

def extract_btc_addresses(csv_file="sdn_list.csv"):
    addresses = []
    with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    pattern = r"Digital Currency Address - XBT ([a-zA-Z0-9]+)"
    matches = re.findall(pattern, content)

    seen = set()
    for addr in matches:
        if is_valid_btc_address(addr) and addr not in seen:
            seen.add(addr)
            addresses.append(addr)

    return addresses

if __name__ == "__main__":
    addresses = extract_btc_addresses()
    print(f"Found {len(addresses)} sanctioned Bitcoin addresses")

    blacklist = {
        "known_mixers": addresses,
        "known_exchange_deposit_addresses": []
    }

    with open("blacklist.json", "w") as f:
        json.dump(blacklist, f, indent=2)

    print("blacklist.json updated with real OFAC sanctions data")