#!/usr/bin/env python3
"""
CLI for calling:
removeStakeAndBurnBatch(bytes32[] hotkeys, uint256 netuid, uint256[] amounts)
"""

import argparse
import os
import json
from web3 import Web3


def main():
    parser = argparse.ArgumentParser(description="Batch unstake helper")
    parser.add_argument("contract", help="UnstakeV2Test contract address")

    # Hotkeys list
    parser.add_argument(
        "--hotkeys", nargs="+", required=True,
        help="List of hotkeys as 32-byte hex strings (0x...)"
    )

    parser.add_argument("--netuid", required=True, type=int)

    # Amounts list (TAO)
    parser.add_argument(
        "--amounts", nargs="+", required=True, type=float,
        help="List of TAO amounts (e.g. 0.05 0.1 0.005)"
    )

    parser.add_argument("--rpc-url", required=True)
    parser.add_argument("--private-key", default=None)

    args = parser.parse_args()

    # Private key
    private_key = args.private_key or os.getenv("PRIVATE_KEY")
    if not private_key:
        raise SystemExit("Set PRIVATE_KEY env var or pass --private-key")

    # Web3 connection
    w3 = Web3(Web3.HTTPProvider(args.rpc_url))
    if not w3.is_connected():
        raise SystemExit(f"Failed to connect to {args.rpc_url}")

    from pathlib import Path

    artifact = Path(__file__).resolve().parents[1] / "out" / "ProperSink.sol" / "ProperSink.json"
    try:
        abi = json.loads(artifact.read_text())["abi"]
    except FileNotFoundError:
        raise SystemExit(f"Build artifact not found at {artifact}. Run `forge build`.")

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(args.contract),
        abi=abi
    )

    # ---- Hotkeys ----
    hotkeys_bytes32 = []
    for h in args.hotkeys:
        h_clean = h.lower().removeprefix("0x")
        b = bytes.fromhex(h_clean)
        if len(b) != 32:
            raise SystemExit(f"Hotkey {h} must be exactly 32 bytes")
        hotkeys_bytes32.append(b)

    # ---- Amounts ----
    if len(args.hotkeys) != len(args.amounts):
        raise SystemExit("hotkeys[] and amounts[] must have the same length")

    amounts_rao = [int(a * 1_000_000_000) for a in args.amounts]  # TAO → Rao

    # Prepare smart contract call
    account = w3.eth.account.from_key(private_key)

    fn = contract.functions.removeStakeAndBurnBatch(
        hotkeys_bytes32,
        args.netuid,
        amounts_rao
    )

    # Gas estimation
    try:
        gas_limit = fn.estimate_gas({"from": account.address})
    except Exception as exc:
        print(f"Gas estimation failed ({exc}); using fallback 8,000,000")
        gas_limit = 8_000_000

    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": gas_limit,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
            "value": 0,
        }
    )

    # Sign + send
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    print(f"Sent tx: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    success = receipt["status"] == 1

    print(f"Status: {'SUCCESS' if success else 'FAILED'}")
    print(f"Gas used: {receipt['gasUsed']}")
    print(f"Block: {receipt['blockNumber']}")

    # If failed → try to print revert reason
    if not success:
        print("\n--- REVERT INFO ---")
        try:
            tx_data = w3.eth.get_transaction(tx_hash)
            revert_data = w3.eth.call(
                {
                    "to": receipt["to"],
                    "from": receipt["from"],
                    "data": tx_data["input"],
                },
                block_identifier=receipt["blockNumber"],
            )
            print(f"Raw revert data: {revert_data.hex()}")
        except Exception as exc:
            print(f"Could not decode revert: {exc}")

    print("\n--- FULL RECEIPT ---")
    print(json.dumps(dict(receipt), default=str, indent=2))


if __name__ == "__main__":
    main()
