#!/usr/bin/env python3
"""
Minimal CLI to call NeuronRegistrar.burnedRegisterNeuron(netuid, hotkey, amountToBurn).
"""
import argparse
import hashlib
import json
import os
import sys
import time
from requests.exceptions import HTTPError

from web3 import Web3
from utils.address_converter import h160_to_ss58

PRECOMPILE_BALANCE_TRANSFER = "0x0000000000000000000000000000000000000800"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58decode(data: str) -> bytes:
    num = 0
    for char in data:
        num *= 58
        if char not in BASE58_ALPHABET:
            raise ValueError(f"Character {char} is not valid base58")
        num += BASE58_ALPHABET.index(char)
    combined = num.to_bytes((num.bit_length() + 7) // 8, byteorder="big")
    leading = 0
    for char in data:
        if char == "1":
            leading += 1
        else:
            break
    return b"\x00" * leading + combined


def decode_ss58_address(ss58: str) -> bytes:
    decoded = b58decode(ss58)
    if len(decoded) < 34:
        raise SystemExit("SS58 address too short")
    format_byte = decoded[0]
    if format_byte >= 64:
        raise SystemExit("Unsupported SS58 format (>=64)")
    pubkey = decoded[1:-2]
    checksum = decoded[-2:]
    expected = hashlib.blake2b(b"SS58PRE" + decoded[:-2], digest_size=64).digest()[:2]
    if checksum != expected:
        raise SystemExit("Invalid SS58 checksum")
    if len(pubkey) != 32:
        raise SystemExit(f"Expected 32-byte address, got {len(pubkey)} bytes")
    return pubkey


def main():
    parser = argparse.ArgumentParser(description="Minimal burnedRegister helper")
    parser.add_argument("contract", help="NeuronRegistrar contract address")
    parser.add_argument("--netuid", required=True, type=int)
    parser.add_argument("--hotkey-bytes32", required=True, help="Hotkey as 32-byte public key hex string (0x...)")
    parser.add_argument("--value-tao", type=float, required=True, help="Total TAO to prefund the contract with (18 decimals assumed)")
    parser.add_argument(
        "--burn-tao",
        type=float,
        default=None,
        help="TAO to forward to burnedRegister (defaults to all of --value-tao)",
    )
    parser.add_argument("--ss58-format", type=int, default=42, help="SS58 format for mirror conversion (default: 42)")
    parser.add_argument("--rpc-url", help="RPC endpoint")
    parser.add_argument("--network", help="Optional network key to resolve RPC if --rpc-url is omitted")
    parser.add_argument("--private-key", default=None)
    args = parser.parse_args()

    private_key = args.private_key or os.getenv("PRIVATE_KEY")
    if not private_key:
        raise SystemExit("Set PRIVATE_KEY env var or pass --private-key")

    pubkey = bytes.fromhex(args.hotkey_bytes32.lower().removeprefix("0x"))
    if len(pubkey) != 32:
        raise SystemExit("Hotkey must be 32 bytes")

    rpc_url = args.rpc_url
    if not rpc_url:
        try:
            import bittensor.utils
        except ImportError as exc:
            raise SystemExit("Provide --rpc-url or install bittensor to resolve --network.") from exc
        if not args.network:
            raise SystemExit("Provide --rpc-url or --network.")
        _, rpc_url = bittensor.utils.determine_chain_endpoint_and_network(args.network)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise SystemExit(f"Failed to connect to {rpc_url}")

    from pathlib import Path

    artifact = Path(__file__).resolve().parents[1] / "out" / "SuperBurn.sol" / "SuperBurn.json"
    try:
        abi = json.loads(artifact.read_text())["abi"]
    except FileNotFoundError:
        raise SystemExit(f"Build artifact not found at {artifact}. Run `forge build`.")

    contract = w3.eth.contract(address=Web3.to_checksum_address(args.contract), abi=abi)

    value_wei = int(args.value_tao * 1_000_000_000_000_000_000)
    burn_tao = args.burn_tao if args.burn_tao is not None else args.value_tao
    burn_wei = int(burn_tao * 1_000_000_000_000_000_000)
    if burn_wei == 0:
        raise SystemExit("Burn amount must be greater than zero")
    if burn_wei > value_wei:
        raise SystemExit("Burn amount cannot exceed total value prefunded")

    account = w3.eth.account.from_key(private_key)
    nonce = w3.eth.get_transaction_count(account.address)

    # Prefund via the balance transfer precompile to the contract's SS58 mirror.
    contract_ss58 = h160_to_ss58(args.contract, args.ss58_format)
    print(f"Contract SS58 (mirror): {contract_ss58}")
    dest_pubkey = decode_ss58_address(contract_ss58)
    transfer_abi = [
        {
            "inputs": [{"internalType": "bytes32", "name": "data", "type": "bytes32"}],
            "name": "transfer",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function",
        }
    ]
    balance_precompile = w3.eth.contract(address=PRECOMPILE_BALANCE_TRANSFER, abi=transfer_abi)

    try:
        fund_gas = balance_precompile.functions.transfer(dest_pubkey).estimate_gas(
            {"from": account.address, "value": value_wei}
        )
    except Exception as exc:
        print(f"Fund gas estimation failed ({exc}); using fallback 120000")
        fund_gas = 120000

    fund_tx = balance_precompile.functions.transfer(dest_pubkey).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "value": value_wei,
            "gas": fund_gas,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )
    signed_fund = w3.eth.account.sign_transaction(fund_tx, account.key)
    fund_hash = w3.eth.send_raw_transaction(signed_fund.raw_transaction)
    print(f"Sent prefund tx via precompile: {fund_hash.hex()}")
    fund_receipt = w3.eth.wait_for_transaction_receipt(fund_hash, timeout=300, poll_latency=2)
    fund_status = fund_receipt.get("status") == 1
    print(f"Prefund tx status: {'SUCCESS' if fund_status else 'FAILED'}")
    if not fund_status:
        try:
            w3.eth.call(
                {
                    "to": PRECOMPILE_BALANCE_TRANSFER,
                    "from": account.address,
                    "data": fund_tx["data"],
                    "value": fund_tx["value"],
                },
                block_identifier=fund_receipt["blockNumber"],
            )
        except Exception as exc:
            print(f"Prefund revert info: {exc}")
        raise SystemExit(f"Prefund failed (tx {fund_hash.hex()})")
    balance_after_fund = w3.eth.get_balance(contract.address)
    print(f"Contract balance after prefund: {w3.from_wei(balance_after_fund, 'ether')} TAO ({balance_after_fund} wei)")
    if balance_after_fund == 0:
        print("WARNING: contract balance is zero after prefund; ensure the mirror SS58 is correct and the precompile honored the transfer before proceeding.")

    fn = contract.functions.burnedRegisterNeuron(args.netuid, pubkey, burn_wei)

    print(f"Burning {burn_tao} TAO (prefunded {args.value_tao} TAO; contract refunds leftover)")

    try:
        gas_limit = fn.estimate_gas({"from": account.address, "value": 0})
    except Exception as exc:
        print(f"Gas estimation failed ({exc}); using fallback 200000")
        gas_limit = 200000

    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": nonce + 1,
            "value": 0,
            "gas": gas_limit,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )

    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Sent register tx: {tx_hash.hex()}")

    receipt = None
    for attempt in range(20):
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300, poll_latency=2)
            break
        except HTTPError as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code == 429:
                delay = 3
                print(f"Rate limited while fetching receipt (429). Retrying in {delay}s...")
                time.sleep(delay)
                continue
            raise
    if receipt is None:
        raise SystemExit("Failed to fetch transaction receipt after multiple attempts (rate limited).")
    status = receipt.get("status") == 1
    print(f"Status: {'SUCCESS' if status else 'FAILED'} (tx status)")
    try:
        attempts = contract.events.RegisterAttempt().process_receipt(receipt)
        if attempts:
            attempt = attempts[0]["args"]
            print(f"RegisterAttempt success={attempt['success']} netuid={attempt['netuid']} burnWei={attempt['amountBurned']}")
        else:
            print("No RegisterAttempt event found; check contract balance and logs.")
    except Exception as exc:
        print(f"Failed to decode RegisterAttempt event: {exc}")
    print(f"Gas used: {receipt['gasUsed']}")
    print(f"Block: {receipt['blockNumber']}")
    if not status:
        tx_data = w3.eth.get_transaction(tx_hash)
        try:
            w3.eth.call(
                {
                    "to": receipt["to"],
                    "from": receipt["from"],
                    "data": tx_data["input"],
                    "value": tx_data["value"],
                },
                block_identifier=receipt["blockNumber"],
            )
        except Exception as exc:
            print(f"Call revert info: {exc}")
    print(json.dumps(dict(receipt), default=str, indent=2))


if __name__ == "__main__":
    main()
