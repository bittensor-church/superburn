#!/usr/bin/env python3
"""
Minimal CLI to call NeuronRegistrar.burnedRegisterNeuron(netuid, hotkey).
"""
import argparse
import hashlib
import json
import os
import sys

from web3 import Web3

def main():
    parser = argparse.ArgumentParser(description="Minimal burnedRegister helper")
    parser.add_argument("contract", help="NeuronRegistrar contract address")
    parser.add_argument("--netuid", required=True, type=int)
    parser.add_argument("--hotkey-bytes32", required=True, help="Hotkey as 32-byte hex string (0x...)")
    parser.add_argument("--value-tao", type=float, required=True, help="TAO to burn (e.g. 0.25)")
    parser.add_argument("--rpc-url", required=True)
    parser.add_argument("--private-key", default=None)
    args = parser.parse_args()

    private_key = args.private_key or os.getenv("PRIVATE_KEY")
    if not private_key:
        raise SystemExit("Set PRIVATE_KEY env var or pass --private-key")

    pubkey = bytes.fromhex(args.hotkey_bytes32.lower().removeprefix("0x"))
    if len(pubkey) != 32:
        raise SystemExit("Hotkey must be 32 bytes")

    w3 = Web3(Web3.HTTPProvider(args.rpc_url))
    if not w3.is_connected():
        raise SystemExit(f"Failed to connect to {args.rpc_url}")

    from pathlib import Path

    artifact = Path(__file__).resolve().parents[1] / "out" / "RegisterOnly.sol" / "RegisterOnly.json"
    try:
        abi = json.loads(artifact.read_text())["abi"]
    except FileNotFoundError:
        raise SystemExit(f"Build artifact not found at {artifact}. Run `forge build`.")

    contract = w3.eth.contract(address=Web3.to_checksum_address(args.contract), abi=abi)

    value_wei = int(args.value_tao * 1_000_000_000)
    account = w3.eth.account.from_key(private_key)

    tx = contract.functions.burnedRegisterNeuron(args.netuid, pubkey).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "value": value_wei,
            "gas": 200000,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )

    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Sent tx: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    success = receipt.get("status") == 1
    print(f"Status: {'SUCCESS' if success else 'FAILED'}")
    print(f"Gas used: {receipt['gasUsed']}")
    print(f"Block: {receipt['blockNumber']}")
    if not success:
        try:
            w3.eth.call(
                {
                    "to": receipt["to"],
                    "from": receipt["from"],
                    "data": w3.eth.get_transaction(tx_hash)["input"],
                    "value": w3.eth.get_transaction(tx_hash)["value"],
                },
                block_identifier=receipt["blockNumber"],
            )
        except Exception as exc:
            print(f"Call revert info: {exc}")
    print(json.dumps(dict(receipt), default=str, indent=2))


if __name__ == "__main__":
    main()
