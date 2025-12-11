#!/usr/bin/env python3
"""
CLI for calling: unstakeAndBurn(bytes32[] hotkeys, uint256 netuid, uint256[] amounts)
Updated with detailed Gas Price debugging and overrides.
"""

import argparse
import os
import sys
import json
from pathlib import Path
import bittensor.utils

# Add the tools directory to sys.path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from utils.address_converter import h160_to_ss58
from utils.contract_loader import get_web3_provider, load_contract
from utils.staking_manager import fetch_validator_stakes

def main():
    parser = argparse.ArgumentParser(description="Batch unstake and burn helper")
    parser.add_argument("contract", help="Sink contract address (EVM 0x...)")
    parser.add_argument("--netuid", required=True, type=int)
    parser.add_argument("--network", default="finney", help="Bittensor network (test/finney)")
    parser.add_argument("--private-key", default=None)
    # New argument to manually force gas price if RPC is crazy
    parser.add_argument("--force-gas-price-gwei", type=float, help="Force a specific Gas Price in Gwei (e.g., 100)")
    args = parser.parse_args()

    _, rpc_url = bittensor.utils.determine_chain_endpoint_and_network(
        args.network,
    )

    private_key = args.private_key or os.getenv("PRIVATE_KEY")
    if not private_key:
        raise SystemExit("Error: Set PRIVATE_KEY env var or pass --private-key")

    # 1. Setup Web3 & Account & Check Balance
    try:
        w3 = get_web3_provider(rpc_url)
        account = w3.eth.account.from_key(private_key)
        balance_wei = w3.eth.get_balance(account.address)
        balance_eth = w3.from_wei(balance_wei, 'ether')

        print(f"--- WALLET INFO ---")
        print(f"Address: {account.address}")
        print(f"Balance: {balance_eth:.6f} TestTAO")

        if balance_wei == 0:
            print("\n[!] CRITICAL ERROR: Your wallet has 0 Balance.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"CRITICAL ERROR connecting to Web3: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Derive SS58 Coldkey
    try:
        derived_coldkey = h160_to_ss58(args.contract)
        print(f"Derived SS58 Coldkey from Contract: {derived_coldkey}")
    except ValueError as e:
        print(f"CRITICAL ERROR: Invalid contract address: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Fetch Stake Data
    try:
        hotkeys_bytes32, amounts_tao = fetch_validator_stakes(
            coldkey_ss58=derived_coldkey,
            netuid=args.netuid,
            network=args.network
        )
    except Exception as e:
        print(f"CRITICAL ERROR fetching stake: {e}", file=sys.stderr)
        sys.exit(1)

    if not hotkeys_bytes32:
        print(f"No valid stake found for {derived_coldkey} on NetUID {args.netuid}.")
        sys.exit(0)

    print(f"Found {len(hotkeys_bytes32)} validators. Total TAO to unstake: {sum(amounts_tao)}")

    # 4. Load Contract
    try:
        artifact_path = current_dir.parent / "out" / "SuperBurn.sol" / "SuperBurn.json"
        contract = load_contract(w3, args.contract, artifact_path)
    except Exception as e:
        print(f"CRITICAL ERROR loading contract: {e}", file=sys.stderr)
        sys.exit(1)

    # 5. Execute
    amounts_rao = [int(a * 1_000_000_000) for a in amounts_tao]
    fn = contract.functions.unstakeAndBurn(hotkeys_bytes32, args.netuid, amounts_rao)

    print("--- GAS & COST CALCULATION ---")
    try:
        # Estimate Gas Limit
        gas_estimate = fn.estimate_gas({"from": account.address})
        gas_limit = int(gas_estimate * 1.2) # 20% buffer
        print(f"Gas Limit (Estimated): {gas_limit}")

        # Get Gas Price
        if args.force_gas_price_gwei:
            gas_price = w3.to_wei(args.force_gas_price_gwei, 'gwei')
            print(f"Gas Price (FORCED):    {args.force_gas_price_gwei} Gwei")
        else:
            gas_price = w3.eth.gas_price
            print(f"Gas Price (Node):      {w3.from_wei(gas_price, 'gwei'):.2f} Gwei")

        # Calculate Total Cost
        total_cost_wei = gas_limit * gas_price
        total_cost_eth = w3.from_wei(total_cost_wei, 'ether')

        print(f"Total Cost (Max):      {total_cost_eth:.6f} TAO")

        if balance_wei < total_cost_wei:
            print(f"\n[!] ERROR: Insufficient funds based on current Gas Price.")
            print(f"[!] Balance: {balance_eth} < Cost: {total_cost_eth}")
            print(f"[!] TIP: Try running with --force-gas-price-gwei 100")
            sys.exit(1)

    except Exception as exc:
        print(f"Gas estimation warning: {exc}. Using fallback.", file=sys.stderr)
        gas_limit = 8_000_000
        gas_price = w3.to_wei(100, 'gwei')

    # FIX: Use 'pending' block to avoid "already known" nonce errors
    nonce = w3.eth.get_transaction_count(account.address, "pending")

    tx = fn.build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": gas_limit,
        "gasPrice": gas_price,
        "chainId": w3.eth.chain_id,
        "value": 0,
    })

    print(f"Sending transaction (Nonce: {nonce})...")
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)

    try:
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Sent tx: {tx_hash.hex()}")
    except Exception as e:
        print(f"Transaction failed locally: {e}")
        sys.exit(1)

    print("Waiting for receipt...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt["status"] == 1:
        print(f"SUCCESS! Block: {receipt['blockNumber']}, Gas Used: {receipt['gasUsed']}")
    else:
        print("FAILED!")
        # Try decoding revert
        try:
            tx_input = w3.eth.get_transaction(tx_hash)["input"]
            revert_data = w3.eth.call(
                {"to": receipt["to"], "from": receipt["from"], "data": tx_input},
                block_identifier=receipt["blockNumber"]
            )
            print(f"Revert Reason (Hex): {revert_data.hex()}")
        except Exception as e:
            print(f"Could not decode revert: {e}")

if __name__ == "__main__":
    main()
