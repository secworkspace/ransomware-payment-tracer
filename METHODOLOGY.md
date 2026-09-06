# Methodology

This document walks through a few of the key technical decisions behind the tracer, including two bugs that came up during development and how I found and fixed them. I'm including the messy parts on purpose, since the debugging is honestly the most interesting part of the project.

## 1. UTXO-level tracing (not naive address-based tracing)

**The naive approach, and why it fails**

The simplest way to "trace" a Bitcoin address is to look at its transaction history and just follow whichever transaction sent out the largest amount. That's how the first version of this tracer worked.

It broke almost immediately. Tracing the Colonial Pipeline seed address correctly followed the real 63.7 BTC ransom for the first three hops, then at hop four the traced amount suddenly jumped from ~63.7 BTC to 80 BTC, then 104 BTC, and kept climbing. The tracer wasn't following the ransom anymore. It had latched onto a completely different, unrelated transaction that just happened to pass through the same address.

The reason this happens is that Bitcoin addresses get reused for all kinds of unrelated things. An address that once received the ransom might later receive and send much larger sums that have nothing to do with the original payment. Just picking "the biggest thing this address ever sent" has no way to tell related money apart from coincidental money.

**The fix: UTXO-level matching**

Every Bitcoin transaction explicitly references the exact prior transaction and output it's spending. So instead of asking "what's the biggest thing this address ever sent," the tracer now asks "which transaction actually spends the specific coins I just traced here." It checks each candidate transaction's inputs for a direct reference to the incoming transaction ID.

This is the same basic principle real blockchain forensics tools use, and it's the difference between address-level tracing (unreliable) and UTXO-level tracing (accurate). After this fix, the trace stayed consistent, dropping only by small fee amounts, for the full length of the confirmed chain.

## 2. Self-consolidation detection

Even after the UTXO fix was working, I ran into a second problem: the tracer would sometimes stop at a hop even though the destination address's balance showed as fully spent on a block explorer. That's a contradiction. The tracer said "dead end," but the blockchain said otherwise.

To figure out why, I added some temporary debug prints and found the transaction the tracer was silently skipping: an address sending almost its entire balance back to itself, consolidated into a single new output, with just a tiny bit going elsewhere. The problem was that my filtering logic explicitly excluded any output going back to the same address, on the assumption that this always meant ordinary "change." That assumption was wrong here, and it meant the tracer was throwing away exactly the transaction it needed to follow.

A wallet consolidating its own coins into a fresh output is normal, everyday Bitcoin behavior, not evidence of money moving to someone new. But a forensic tool still needs to tell the two apart: treating a self-consolidation as if it were a real transfer would be misleading, and ignoring it completely (what the earlier version did) causes the trace to stop early and miss whatever happens next.

The fix was to track self-consolidation transactions as their own category, labeled as medium risk, but still followed so the trace keeps going past them. This showed up right away in testing: hop 4 of the Colonial Pipeline trace turned out to be a self-consolidation, and hop 5 (a real transfer to a new address) was only discoverable once this fix was in place.

![Self-consolidation detection](screenshots/self-consolidation-flag.png)
*Hop 4 is correctly labeled as self-consolidation instead of a real transfer, and the trace still continues on to hop 5.*

## 3. Sanctions blacklist: real data, not placeholders

The blacklist used for screening comes from the U.S. Treasury's live OFAC sanctions list, the actual list currently enforced by the U.S. government, which includes designated cryptocurrency addresses (for example, sanctioned mixers like Blender.io).

Getting this into a usable form took some real data cleaning. The raw government file buries addresses inside long, semicolon-separated text fields alongside aliases, other cryptocurrency addresses, and organizational details. I pulled out candidate addresses using a regex match on the "Digital Currency Address - XBT" marker, then added a validation step that checks each candidate against real Bitcoin address formats (legacy base58 and modern bech32) to throw out truncated fragments and non-Bitcoin addresses that slipped through the first pass. What's left is a clean list of around 240 confirmed, valid, currently-sanctioned Bitcoin addresses.

## Known limitations

- **Single-path tracing.** The tracer follows the single largest-value path at each hop. It doesn't yet show the full transaction graph, so smaller branching transfers at each hop aren't represented.
- **Bitcoin only.** No support yet for Ethereum or other chains.
- **No handling for cross-chain bridges or privacy-focused mixing.** Sufficiently sophisticated laundering would break the trace here, the same way it would for a real investigator without additional off-chain intelligence.
- **Point-in-time blacklist.** The sanctions data is a snapshot from whenever `build_blacklist.py` was last run. A production system would refresh this on a schedule.

I'm listing these on purpose rather than glossing over them. A forensic tool's real limitations matter just as much as what it can actually do.
