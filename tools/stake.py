#!/usr/bin/env python3
"""
CLI tool to manually stake TAO to the Sink contract.
Calls: Sink.stake(hotkey, netuid, amount)
"""

import argparse
import os
import sys
import json
from pathlib import Path

# Add the tools directory to sys.path to allow imports from utils
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from utils.contract_loader import get_web3_provider, load_contract

def main():
    parser = argparse.ArgumentParser(description="Helper script to manually stake TAO via Sink contract.")
    parser.add_argument("contract", help="Sink contract address (EVM 0x...)")
    parser.add_argument("--hotkey-bytes32", required=True, help="Hotkey as 32-byte hex string (0x...)")
    parser.add_argument("--netuid", required=True, type=int)
    parser.add_argument("--amount-tao", type=float, required=True, help="Amount of TAO to stake (e.g., 0.05)")
    parser.add_argument("--rpc-url", required=True)
    parser.add_argument("--private-key", default=None)
    args = parser.parse_args()

    # 1. Validation
    private_key = args.private_key or os.getenv("PRIVATE_KEY")
    if not private_key:
        print("Error: Set PRIVATE_KEY env var or pass --private-key", file=sys.stderr)
        sys.exit(1)

    try:
        hotkey_bytes = bytes.fromhex(args.hotkey_bytes32.lower().removeprefix("0x"))
        if len(hotkey_bytes) != 32:
            raise ValueError("Hotkey must be exactly 32 bytes")
    except ValueError as e:
        print(f"Error: Invalid hotkey format: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Setup Web3 & Contract
    try:
        w3 = get_web3_provider(args.rpc_url)
        # Path to the Foundry artifact: project_root/out/SuperBurn.sol/Sink.json
        artifact_path = current_dir.parent / "out" / "SuperBurn.sol" / "SuperBurn.json"
        contract = load_contract(w3, args.contract, artifact_path)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Prepare Transaction
    amount_rao = int(args.amount_tao * 1_000_000_000)  # Convert TAO to Rao
    account = w3.eth.account.from_key(private_key)

    fn = contract.functions.stake(hotkey_bytes, args.netuid, amount_rao)

    print(f"Preparing to stake {args.amount_tao} TAO to hotkey {args.hotkey_bytes32}...")

    # 4. Estimate Gas
    try:
        gas_limit = fn.estimate_gas({"from": account.address, "value": 0})
        gas_limit = int(gas_limit * 1.1) # Add 10% buffer
    except Exception as exc:
        print(f"Warning: Gas estimation failed ({exc}); using fallback 500,000", file=sys.stderr)
        gas_limit = 500_000

    tx = fn.build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "value": 0,
        "gas": gas_limit,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })

    # 5. Send Transaction
    print("Sending transaction...")
    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Sent tx: {tx_hash.hex()}")

    # 6. Wait for Receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    success = receipt.get("status") == 1

    print(f"Status: {'SUCCESS' if success else 'FAILED'}")
    print(f"Gas used: {receipt['gasUsed']}")
    print(f"Block: {receipt['blockNumber']}")

    if not success:
        print("\n--- REVERT INFO ---")
        try:
            tx_data = w3.eth.get_transaction(tx_hash)
            # Replay the transaction locally to get the revert reason
            revert_reason = w3.eth.call(
                {
                    "to": receipt["to"],
                    "from": receipt["from"],
                    "data": tx_data["input"],
                    "value": tx_data["value"],
                },
                block_identifier=receipt["blockNumber"]
            )
            print(f"Raw revert data: {revert_reason.hex()}")
        except Exception as exc:
            print(f"Could not retrieve revert reason: {exc}")

    print("\n--- FULL RECEIPT ---")
    print(json.dumps(dict(receipt), default=str, indent=2))

if __name__ == "__main__":
    main()